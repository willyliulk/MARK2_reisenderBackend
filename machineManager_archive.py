from dataclasses import dataclass  
from enum import Enum
import asyncio
import traceback

import cv2
import paho.mqtt.client as mqtt
from loguru import logger

from motorManager import MotorManager_v2

class MachineState(Enum):
    IDLE        = 0
    SHOTTING    = 1
    AI_PROC     = 2
    ERROR      = 3


class MachineManager:
    class ManageState(Enum):
        STOP = 0
        RUNNING = 1

    def __init__(self, MotorManager_list:list[MotorManager_v2],
                        camera_list:dict,
                        broker='localhost', port=11883):
        self.__MotorManager_list = MotorManager_list
        self.__camera_list:dict[str, cv2.VideoCapture] = camera_list
        self.__is_running = False
        
        self.__emergency   = False
        self.__reason      = ""
        self.__state       = MachineState.IDLE
        self.__colorLight  = "r"
        self.__btn_on:list[str] = []
        
        self.__errorMonitoring_tesk = None
        
        self.__broker = broker
        self.__port = port
        self.__client = mqtt.Client(client_id=f"mechine_manage", reconnect_on_failure=True)
        self.__client.reconnect_delay_set(1, 30)
        self.__client.on_connect = self.__mqtt_on_connect
        self.__client.on_disconnect = self.__mqtt_on_disconnect
        self.__client.message_callback_add("button/resolve", self.__on_button_resolve_cb)
        self.__client.message_callback_add("button/camShot", self.__on_button_camShot_cb)
        self.__client.message_callback_add("button/home", self.__on_button_home_cb)
        self.__client.message_callback_add("button/emg", self.__on_button_emg_cb)

        self.btn_resolve = False
        self.btn_camShot = False
        self.btn_home = False
        self.btn_emg = False
                
    async def startManager(self):
        self.__is_running = True
        try:
            self.__errorMonitoring_tesk = asyncio.create_task(self.__machineManageLoop())

            self.__client.connect_async(self.__broker, self.__port)
            self.__client.loop_start()
        except Exception as e:
            logger.error(f"mechineManager error: {e}")
            logger.error(traceback.format_exc())
            await self.closeManager()
        
    async def closeManager(self):
        self.__is_running = False
        if self.__errorMonitoring_tesk and not self.__errorMonitoring_tesk.done():
            self.__errorMonitoring_tesk.cancel()
            try:
                await self.__errorMonitoring_tesk
            except asyncio.CancelledError:
                pass
        self.__errorMonitoring_tesk = None
        
        self.__client.disconnect()
        self.__client.loop_stop()
    
    def __mqtt_on_connect(self, client, userdata, flags, rc):
        logger.debug("on_connect")
        if rc == 0:
            logger.debug(f"已連接到MQTT代理, 結果碼: {rc}")
            print("已連接到MQTT代理")
            self.__client.subscribe("button/resolve")
            self.__client.subscribe("button/camShot")
            self.__client.subscribe("button/home")
            self.__client.subscribe("button/emg")
        else:
            logger.error(f"連接失敗，結果碼: {rc}")

    def __mqtt_on_disconnect(self, client, userdata, rc):
        """從MQTT代理斷開連接時的回調函數"""
        if rc != 0:
            logger.warning(f"意外斷開連接，結果碼: {rc}")
        
        # 重新連接到代理
        if self.__is_running:
            self.__client.reconnect()

    def __on_button_resolve_cb(self, client, userdata, msg):
        self.btn_resolve = True if msg.payload.decode() == "1" else False
    
    def __on_button_camShot_cb(self, client, userdata, msg):
        self.btn_camShot = True if msg.payload.decode() == "1" else False
        
    def __on_button_home_cb(self, client, userdata, msg):
        self.btn_home = True if msg.payload.decode() == "1" else False
    
    def __on_button_emg_cb(self, client, userdata, msg):
        self.btn_emg = True if msg.payload.decode() == "1" else False
    
    async def __machineManageLoop(self):
        while self.__is_running:
            # hardware recving
             
            # check all errors
            motorErr = self.checkMotorError()
            if motorErr != "":
                self.__state = MachineState.ERROR
                self.__emergency = True
                self.__reason += motorErr
            
            cameraErr = self.checkCameraError()
            if cameraErr != "":
                self.__state = MachineState.ERROR
                self.__emergency = True
                self.__reason += cameraErr
            
            if self.btn_emg:
                self.__state = MachineState.ERROR
                self.__emergency = True
                self.__reason += "emergency button is pressed\n"
            
            # check button
            if self.btn_resolve:
                self.__state = MachineState.IDLE
                self.__emergency = False
                self.__reason = ""
                self.btn_resolve = False
                self.__MotorManager_list[0].resolve()
                self.__MotorManager_list[1].resolve()
            
            await asyncio.sleep(0.05)   
                        
            
    
    def checkMotorError(self):
        # chenck motor errors
        motorError = ""
        for motor in self.__MotorManager_list:
            if motor.motorState != MotorManager_v2.MotorState.ERROR:
                continue
            # check motor proximity sensor
            for id, prox_on in enumerate(motor.get_proximitys()):
                if prox_on:
                    motorError += f'motor_{motor.id}: proximity_{id}  is on\n'
            
            # not the error above, asy unknow error happen
            if motorError == "":
                motorError = f'motor_{motor.id}: unknow error happen \n'
        return motorError
    
    def checkCameraError(self):
        # check camera errors
        cameraError = ""
        for key, camera in self.__camera_list.items():
            if camera.isOpened():
                continue
            
            # check error can a cv2.VideoCapture object be opened
            if camera.get(cv2.CAP_PROP_POS_FRAMES) == 0:
                cameraError += f'camera_{key}: camera is not opened\n'
                continue
            
            # not the error above, asy unknow error happen
            if cameraError == "":
                cameraError += f'camera_{key}: unknow error happen \n'
            
            cameraError += f'camera_{key}: unknow error happen \n'

        return cameraError

                    
    def is_emergency(self):
        if self.__state == MachineState.ERROR:
            return True
        else:
            return False
    
    def get_reason(self):
        reasonLog = ""

        # chenck motor errors
        for motor in self.__MotorManager_list:
            if motor.motorState != MotorManager_v2.MotorState.ERROR:
                continue
            motorError = ""
            # check motor proximity sensor
            for id, prox_on in enumerate(motor.get_proximitys()):
                if prox_on:
                    motorError += f'motor_{motor.id}: proximity_{id}  is on\n'
            
            # not the error above, asy unknow error happen
            if motorError == "":
                motorError = f'motor_{motor.id}: unknow error happen \n'
            
            reasonLog += motorError
            
        # check camera errors
        for key, camera in self.__camera_list.items():
            if camera.isOpened():
                continue
            
            # check error can a cv2.VideoCapture object be opened
            if camera.get(cv2.CAP_PROP_POS_FRAMES) == 0:
                reasonLog += f'camera_{key}: camera is not opened\n'
                continue
            
            # not the error above, asy unknow error happen
            if reasonLog == "":
                reasonLog += f'camera_{key}: unknow error happen \n'
            
            reasonLog += f'camera_{key}: unknow error happen \n'
        
        return self.__reason
            
    
    def resolve_error(self):
        print("resolving")
        # self.__client.publish("machine/resolve", "")
        self.__MotorManager_list[0].resolve()
        
        self.__MotorManager_list[1].resolve()
        
    def raise_error(self):
        print("raising")
        for motor in self.__MotorManager_list:
            motor.motorState = MotorManager_v2.MotorState.ERROR

    def get_btn_list(self):
        btn_list = []
        if self.btn_resolve:
            btn_list.append("resolve")
        if self.btn_camShot:
            btn_list.append("camShot")
        if self.btn_home:
            btn_list.append("home")
        if self.btn_emg:
            btn_list.append("EMG")
        return btn_list