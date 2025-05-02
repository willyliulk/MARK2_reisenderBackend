
# from motorModbus import MyModbus as MyMotorController
# from motorNewController import MotorController as MyMotorController
from motorController_Fake import FakeMotorController as MyMotorController
from singleton_decorator import singleton
import time
from threading import Thread
from enum import Enum
from dataclasses import dataclass
from loguru import logger
import os, asyncio
import signal
import httpx
from pynng import Pub0, Sub0, exceptions
import paho.mqtt.client as mqtt
import json


class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class MotorManager():    
    __metaclass__ = Singleton    
    ManagerRequest = Enum('ManagerRequest', [
        'FINISH',
        'NORMAL',
        'MOVE_ABS',
        'MOVE_INC',
        'STOP',
        'RECONNECT',
        'HANDLE_ERROR',
    ], start=0)
    
    tries = 10
    
    @dataclass
    class MotorData:
        pos:int = 0
        vel:int = 0
        
    def motorJob(self):
        logger.debug("job start")
        logger.debug("Job Threead PID: " + str(os.getpid()))
        while not self.kill:
            try:
                for i in range(self.tries):
                    try:
                        self.modbusMotor.connect(self.port, 500000)
                        time.sleep(0.01)
                        self.modbusMotor.getPos()
                        self.modbusMotor.clearError()
                    except Exception as e:
                        logger.error(f"[get error] {e} trying #{i}")
                        continue
                    finally:
                        break     
                while (self.managerReq != self.ManagerRequest.FINISH) and (not self.kill):
                    if self.managerReq == self.ManagerRequest.NORMAL:
                        self.motorData.pos = self.modbusMotor.getPos()
                        self.motorData.vel = self.modbusMotor.getVel()
                        self.btnData = self.modbusMotor.checkButton()
                        if self.btnData[0] == 1 and self.preBtnData[0] == 0:
                            pass
                        if self.btnData[1] == 1 and self.preBtnData[1] == 0:
                            pass
                        
                        motorErr = self.modbusMotor.checkError()
                        self.preBtnData = self.btnData
                        if motorErr != 0:
                            logger.debug("Motor Error: Location out of tolerance")
                            self.paraPasser = motorErr
                            self.managerReq = self.ManagerRequest.HANDLE_ERROR
                        time.sleep(0.05)
                    
                    elif self.managerReq == self.ManagerRequest.MOVE_ABS:
                        logger.debug('motorJob', "MOVE_ABS")
                        self.modbusMotor.moveAbsPos(self.paraPasser)
                        time.sleep(0.1)
                        self.managerReq = self.ManagerRequest.NORMAL
                        
                    elif self.managerReq == self.ManagerRequest.MOVE_INC:
                        logger.debug('motorJob', "MOVE_INC")
                        self.modbusMotor.moveIncPos(self.paraPasser)
                        time.sleep(0.1)
                        self.managerReq = self.ManagerRequest.NORMAL
                        
                    elif self.managerReq == self.ManagerRequest.STOP:
                        logger.debug('motorJob', "STOP")
                        self.modbusMotor.setStop()
                        time.sleep(0.1)
                        self.managerReq = self.ManagerRequest.NORMAL
                        
                    elif self.managerReq == self.ManagerRequest.RECONNECT:
                        logger.debug('motorJob', "RECONNECT")
                        self.modbusMotor.connect(self.paraPasser, 500000)
                        time.sleep(0.1)
                        self.managerReq = self.ManagerRequest.NORMAL
                        
                    elif self.managerReq == self.ManagerRequest.HANDLE_ERROR:
                        logger.debug('motorJob', "HANDLE_ERROR: ", end='')
                        if self.paraPasser == 6:
                            logger.debug('Location out of tolerance : deal with clear error')
                            self.modbusMotor.clearError()
                        time.sleep(0.1)
                        self.managerReq = self.ManagerRequest.NORMAL
            except IOError as e:
                logger.error(f'[catch] => {e}')
                
            except Exception as e:
                self.modbusMotor.disconnect()
                logger.debug('job thread finish')
                self.kill = True
            finally: 
                self.modbusMotor.disconnect()
                logger.debug('job thread finish')
                break
        
        
    def __init__(self, port, baud=115200):
        self.managerReq = self.ManagerRequest.NORMAL
        self.paraPasser = 0
        self.port = port
        self.baud = baud
        self.kill = False
        
        self.modbusMotor = MyMotorController(port, baud)
        self.motorData = self.MotorData()
        self.jobThreead = Thread(target=self.motorJob)
        self.jobThreead.start()
        
        # signal.signal(signal.SIGINT, self.exit_gracefully)
        # signal.signal(signal.SIGTERM, self.exit_gracefully)
        # signal.signal(signal.SIGKILL, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.modbusMotor.disconnect()
        logger.debug('job thread finish')
        self.kill = True

    
    def goAbsPos(self, pos:int):
        self.paraPasser = pos
        self.managerReq = self.ManagerRequest.MOVE_ABS
    
    def goIncPos(self, pos:int):
        self.paraPasser = pos
        self.managerReq = self.ManagerRequest.MOVE_INC
        
    def motorStop(self):
        self.managerReq = self.ManagerRequest.STOP
    
    def getMotorData(self):
        '''        @dataclass
        MotorData:
        pos:int = 0
        vel:int = 0'''
        # logger.debug("getMotorData")
        return self.motorData
    
    def getMotorButton(self):
        ''' return a list of button state [stop, operate] '''
        return self.btnData

    
    def closeManager(self):
        self.managerReq = self.ManagerRequest.FINISH
        self.kill = True
        self.jobThreead.join()
        logger.debug("job end")

 
class MotorManager_v2():
    # __metaclass__ = Singleton    
    class ManageState(Enum):
        STOP = 0
        RUNNING = 1
        
    class MotorState(Enum):
        IDEL = 0
        RUNNING = 1
        ERROR = 2

    
    @dataclass
    class MotorData:
        pos:int = 0
        vel:int = 0
        
    def __init__(self, id=0, homePos=0, broker='localhost', port=11883):
        '''ID由1開始'''
        self.id=id
        self.homePos=homePos
        self.motorData = self.MotorData()
        self.motorState = self.MotorState.IDEL
        self.motorProximity = [False, False]
        
        self.__managerState = self.ManageState.STOP
        
        # mqtt client
        self.broker=broker
        self.port = port
        
        # basic mqtt cb
        self.client = mqtt.Client(client_id=f"motorManager_v2_{self.id}")
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        
        self.topic_prefix = f'motor/{self.id}'
        
        
    async def startManger(self):
        logger.debug("startManger")
        self.__managerState = self.ManageState.RUNNING
        
        try:
            self.client.message_callback_add(f'{self.topic_prefix}/angle', self.__on_angle_cb)
            self.client.message_callback_add(f'{self.topic_prefix}/speed', self.__on_speed_cb)
            self.client.message_callback_add(f'{self.topic_prefix}/proximity', self.__on_proximity_cb)
            
            self.client.connect_async(self.broker, self.port)
            
            self.client.loop_start()

            await asyncio.sleep(0.1)
        
        except Exception as e:
            logger.error(f'Error: {e}')
            self.__managerState = self.ManageState.STOP
            self.client.loop_stop()
            self.client.disconnect()
            raise e
    
    async def closeManager(self):
        logger.debug(f"closeManager for motor_{self.id}")
        self.__managerState = self.ManageState.STOP

        # 停止背景執行緒
        self.client.loop_stop()

        # 斷開與代理的連接
        self.client.disconnect()
        
    def on_connect(self, client, userdata, flags, rc):
        logger.debug("on_connect")
        if rc == 0:
            logger.debug(f"已連接到MQTT代理, 結果碼: {rc}")
            self.client.subscribe(f'{self.topic_prefix}/angle')
            self.client.subscribe(f'{self.topic_prefix}/speed')
            self.client.subscribe(f'{self.topic_prefix}/proximity')
        else:
            logger.error(f"連接失敗，結果碼: {rc}")

    def on_disconnect(self, client, userdata, rc):
        """從MQTT代理斷開連接時的回調函數"""
        if rc != 0:
            logger.warning(f"意外斷開連接，結果碼: {rc}")
        
        # 重新連接到代理
        if self.__managerState != self.ManageState.STOP:
            self.client.reconnect()
    
    def __on_angle_cb(self, client, userdata, msg):
        """處理角度訊息的專用回調函數"""
        try:
            payload = msg.payload.decode()
            # logger.debug(f"收到角度訊息: {payload}")
            self.motorData.pos = float(payload)
        except Exception as e:
            logger.error(f"處理角度訊息時出錯: {e}")

    def __on_speed_cb(self, client, userdata, msg):
        """處理速度訊息的專用回調函數"""
        try:
            payload = msg.payload.decode()
            # logger.debug(f"收到速度訊息: {payload}")
            self.motorData.vel = float(payload)
        except Exception as e:
            logger.error(f"處理速度訊息時出錯: {e}")

    def __on_proximity_cb(self, client, userdata, msg):
        """處理接近開關訊息的專用回調函數"""
        try:
            payload = msg.payload.decode()
            logger.debug(f"收到接近開關訊息: {payload}")
            self.__cb_proximity(payload)
        except Exception as e:
            logger.error(f"處理接近開關訊息時出錯: {e}")
        
        
    def goAbsPos(self, pos: int):
        """移動到絕對位置"""
        logger.debug("goAbsPos")
        self.client.publish(f"{self.topic_prefix}/cmd/goAbsPos", str(pos))
        
    def goIncPos(self, pos: int):
        """移動增量位置"""
        logger.debug("goIncPos")
        self.client.publish(f"{self.topic_prefix}/cmd/goIncPos", str(pos))
    
    def goHomePos(self):
        """移動到原點位置"""
        logger.debug("goHomePos")
        self.client.publish(f"{self.topic_prefix}/cmd/goHomePos", str(self.homePos))
        # self.client.publish(f"{self.topic_prefix}/cmd/goAbsPos", str(self.homePos))
        
    def motorStop(self):
        """停止電機"""
        logger.debug("motorStop")
        self.client.publish(f"{self.topic_prefix}/cmd/stop", "")
    
    def get_motorData(self):
        """獲取電機數據"""
        return self.motorData
    
    def get_motorState(self):
        """獲取電機狀態"""
        return self.motorState
        
    def get_proximitys(self):
        """獲取接近開關狀態"""
        return self.motorProximity
    
    def is_home(self):
        '''return True if motor is at home position'''
        if abs(self.motorData.pos - self.homePos) < 1:
            return True
        else:
            return False

    def __cb_proximity(self, content: str):
        """處理接近開關數據"""
        try:
            # 假設內容格式為 "0,0" 或 "1,0" 等
            values = content.strip().split(',')
            if len(values) >= 2:
                self.motorProximity[0] = values[0] == '1'
                self.motorProximity[1] = values[1] == '1'
        except Exception as e:
            logger.error(f"處理接近開關數據時出錯: {e}")
        

    
    
        
        
               
if __name__ == "__main__":
    motorManager = MotorManager('/dev/ttyUSB3', 500000)
    
    a=0
    a+=1
    logger.debug(a) #1
    time.sleep(5)
    motorManager.goAbsPos(1000)
    a+=1
    logger.debug(a) #2
    time.sleep(5)
    motorManager.goAbsPos(-1000)
    a+=1
    logger.debug(a) #3
    time.sleep(5)
    ac = motorManager.getMotorData()
    print(ac.pos)
    print(ac.vel)
    a+=1
    logger.debug(a) #4
    time.sleep(5)

    motorManager.closeManager()
