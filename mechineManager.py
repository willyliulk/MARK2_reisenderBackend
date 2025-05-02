from dataclasses import dataclass  
from enum import Enum
import asyncio

from motorManager import MotorManager_v2
import cv2

class MachineState(Enum):
    IDLE        = 0
    SHOTTING    = 1
    AI_PROC     = 2
    ERRROR      = 3


class MachineManager:
    def __init__(self, MotorManager_list:list[MotorManager_v2],
                        camera_list:list[cv2.VideoCapture]):
        self.__MotorManager_list = MotorManager_list
        self.__camera_list = camera_list
        
        self.__emergency   = False
        self.__reason      = ""
        self.__state       = MachineState.IDLE
        self.__colorLight  = "r"
        self.__btn_on:list[str] = []
        
        self.__errorMonitoring_tesk = None
        
    async def startManager(self):
        self.__errorMonitoring_tesk = asyncio.create_task(self.__machineManageLoop())
    
    async def closeManager(self):
        self.__errorMonitoring_tesk.cancel()
        if self.__errorMonitoring_tesk and not self.__errorMonitoring_tesk.done():
            self.__errorMonitoring_tesk.cancel()
            try:
                await self.__errorMonitoring_tesk
            except asyncio.CancelledError:
                pass
        self.__errorMonitoring_tesk = None
    
    def __machineManageLoop(self):
        while True:
            # hardware recving
             
            
            # check all errors
            motorErr = self.checkMotorError()
            if not motorErr:
                self.__state = MachineState.ERROR
                self.__emergency = True
                self.__reason += motorErr
            
            cameraErr = self.checkCameraError()
            if not cameraErr:
                self.__state = MachineState.ERROR
                self.__emergency = True
                self.__reason += cameraErr
                            
                        
            
    
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
        for camera in self.__camera_list:
            if camera.isOpened():
                continue
            
            # check error can a cv2.VideoCapture object be opened
            if camera.get(cv2.CAP_PROP_POS_FRAMES) == 0:
                cameraError += f'camera_{camera.id}: camera is not opened\n'
                continue
            
            # not the error above, asy unknow error happen
            if cameraError == "":
                cameraError += f'camera_{camera.id}: unknow error happen \n'
            
            cameraError += f'camera_{camera.id}: unknow error happen \n'

                    
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
        for camera in self.__camera_list:
            if camera.isOpened():
                continue
            
            # check error can a cv2.VideoCapture object be opened
            if camera.get(cv2.CAP_PROP_POS_FRAMES) == 0:
                reasonLog += f'camera_{camera.id}: camera is not opened\n'
                continue
            
            # not the error above, asy unknow error happen
            if reasonLog == "":
                reasonLog += f'camera_{camera.id}: unknow error happen \n'
            
            reasonLog += f'camera_{camera.id}: unknow error happen \n'
        
        return self.__reason
            
    
    def resolve_error():
        pass
        