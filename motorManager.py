
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
        
    def __init__(self, id=0, homePos=0, addres='ipc://tmp/motor.ipc'):
        '''ID由1開始'''
        self.id=id
        self.homePos=homePos
        self.addres=addres
        self.pub = Pub0()
        self.sub = Sub0()
        self.recv_task = None
        self.manageState = self.ManageState.STOP
        self.motorData = self.MotorData()
        self.motorState = self.MotorState.IDEL
        self.motorProximity = [False, False]
        
        
    async def startManger(self):
        logger.debug("startManger")
        self.manageState = self.ManageState.RUNNING
        try:
            self.pub.dial(self.addres)
            self.sub.dial(self.addres)
        except exceptions.ConnectionRefused as e:
            pass
        self.sub.subscribe(f'motor|{self.id}|angle')
        self.sub.subscribe(f'motor|{self.id}|speed')
        self.recv_task = asyncio.create_task(self.msg_recv_job())
        
    async def closeManager(self):
        logger.debug("closeManager")
        self.pub.close()
        self.sub.close()
        if self.recv_task and not self.recv_task.done():
            self.recv_task.cancel()
            try:
                await self.recv_task
            except asyncio.CancelledError:
                pass
        self.recv_task = None
        
        
    def goAbsPos(self, pos:int):
        logger.debug("goAbsPos")
        cmd = f'motor|{self.id}|goAbsPos:{pos}'
        self.pub_send_helper(cmd)
        
    def goIncPos(self, pos:int):
        logger.debug("goIncPos")
        cmd = f'motor|{self.id}|goIncPos:{pos}'
        self.pub_send_helper(cmd)
    
    def goHomePos(self):
        logger.debug("goHomePos")
        cmd = f'motor|{self.id}|goHomePos:'
        self.pub_send_helper(cmd)
        
    def motorStop(self):
        logger.debug("motorStop")
        cmd = f'motor|{self.id}|stop:'
        self.pub_send_helper(cmd)
        
    def get_motorData(self):
        return self.motorData
    
    def get_motorState(self):
        return self.motorState
        
    def get_proximitys(self):
        fakeProximity = [False, False]
        return fakeProximity
        # return self.motorProximity
    
    def is_home(self):
        '''return True if motor is at home position'''
        if abs(self.motorData.pos - self.homePos) < 1:
            return True
        else:
            return False

    def pub_send_helper(self, cmd:str):
        self.pub.send(cmd.encode())
        
    def sub_recv_helper(self, msg:str, topic:str, callback=None):
        if msg.startswith(topic):
            content = msg[len(topic):]
            if callback:
                callback(content)
            else:
                logger.debug("recv msg:", content)
    
    def __cb_prosimity(self, content:str):
        '''content = 00, 01, 10 , 11'''
        self.motorProximity[0] = content[0]==1
        self.motorProximity[1] = content[1]==1
        
    async def msg_recv_job(self):
        logger.debug("msg_recv_job start")
        try:
            while True:
                try:

                    if self.manageState == self.ManageState.STOP:
                        break
                    msg = await asyncio.wait_for(self.sub.arecv(), timeout=0.1) 
                    
                    if msg:
                        logger.debug("get msg:", msg)
                        msg = msg.decode()
                        self.sub_recv_helper(msg, f'motor|{self.id}|angle',
                                                lambda x: setattr(self.motorData, 'pos', float(x)))
                        self.sub_recv_helper(msg, f'motor|{self.id}|speed',
                                                    lambda x: setattr(self.motorData, 'vel', float(x)))
                        self.sub_recv_helper(msg, f'motor|{self.id}|proximity',self.__cb_prosimity)
                
                except asyncio.TimeoutError:
                    continue  # 超時後繼續檢查停止條件
                except IOError as e:
                    logger.error(f'[catch] => {e}')
                    break
                except Exception as e:
                    logger.error(f'[catch] => {e}')
                    break
        
        except asyncio.CancelledError:
            logger.debug("msg_recv_job cancelled")
        finally:
            logger.debug("msg_recv_job end")

    
    
        
        
               
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
