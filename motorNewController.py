import serial
from serial.tools.list_ports import comports
from singleton_decorator import singleton
from loguru import logger
import time

@singleton
class MotorController:
    def __init__(self, port: str, baud: int = 115200):
        self.port = port
        self.baudrate = baud
        self.serial = None
        
        ports = list(comports())
        if not ports:
            raise IOError("No USB serial devices found.")
                
        # 尋找 Arduino 設備
        desList = [port.device for port in ports if 'CP2102 USB to UART Bridge Controller' in port.description]
        if len(desList) == 0:
            raise Exception("No motor controller device found")
        logger.debug(f"Found morot controller at: {desList[0]}")
        
    # self.connect(desList[0], baud)

    def connect(self, port: str = None, baud: int = 115200):
        self.port = port
        self.baudrate = baud
        logger.info(f"connection setup port:{port}, baud:{baud}")

        try:
            ports = list(comports())
            if not ports:
                raise IOError("No USB serial devices found.")
                    
            # 尋找 Arduino 設備
            desList = [port.device for port in ports if 'CP2102 USB to UART Bridge Controller' in port.description]
            if len(desList) == 0:
                raise Exception("No morot controller device found")
            logger.debug(f"Found morot controller at: {desList[0]}")
            self.port = desList[0]
            # self.port = "/tmp/ttyV0"
            # self.baudrate = 500000
            
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # 等待 Arduino 重置
            logger.debug(f"Serial connection established with {self.port}")
            
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            return True
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    def disconnect(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.debug("Serial connection closed")

    def _send_command(self, cmd: str) -> str:
        """發送命令並讀取回應"""
        try:
            self.serial.write(f"{cmd}\n".encode())
            # print(f"{cmd}\n".encode())
            # time.sleep(0.01)
            
            response = self.serial.read_until(b'\r\n').decode().strip()
            # self.serial.read_all()
            # print('res:', response)
            # self.serial.reset_input_buffer()  # 清空緩衝區
            # self.serial.reset_output_buffer()  # 清空緩衝區
            # time.sleep(0.05)
            return response
        except Exception as e:
            logger.error(f"Communication error: {e}")
            return ""

    def moveAbsPos(self, pos: int):
        if pos > 2147483647 or pos < -2147483647:
            raise ValueError(f"pos value must between -2147483647~2147483647, now is {pos}")
        response = self._send_command(f"m{pos}")
        # print(response)
        logger.debug('Moved abs')
        return response

    def moveIncPos(self, pos: int):
        if pos > 2147483647 or pos < -2147483647:
            raise ValueError(f"pos value must between -2147483647~2147483647, now is {pos}")
        
        current_pos = self.getPos()
        target_pos = current_pos + pos
        
        response = self._send_command(f"m{target_pos}")
        logger.debug(f'Moved inc from {current_pos} to {target_pos} (delta: {pos})')
        return response

    def getPos(self) -> int:
        response = self._send_command("m")
        try:
            return int(response)
        except ValueError as e:
            logger.error(f"Invalid position value received: {response}:{len(response)}")
            raise IOError(f"Invalid data from motor: {e}")

    def getVel(self) -> float:
        response = self._send_command("v")
        try:
            return float(response)
        except ValueError as e:
            logger.error(f"Invalid velocity value received: {response}")
            raise IOError(f"Invalid data from motor: {e}")

    def setVel(self, vel: float):
        response = self._send_command(f"v{vel}")
        logger.debug(f'Set velocity to {vel}')
        return response
    
    def setStop(self):
        response = self._send_command("s")
        logger.debug('Motor Stop')
        return response

    def clearError(self):
        # response = self._send_command("c")
        response = 'done'
        logger.debug('Motor clean error')
        return response

    def checkButton(self):
        response = self._send_command("c")
        # logger.debug(f'Button status: s:{response[0]}, o:{response[1]}')
        return response
    
    def checkError(self) -> int:
        """0=OK, 6=Location out of tolerance"""
        return 0
        response = self._send_command("e")
        try:
            return int(response)
        except ValueError as e:
            logger.error(f"Invalid error code received: {response}")
            raise IOError(f"Invalid error code from motor: {e}")


if __name__ == "__main__":
    
    # ports = list(comports())
    # desList = [(port.device, port.description) for port in ports]

    # print(desList)
    
    # exit()
    
    
    motor=None
    try:
        motor = MotorController('/dev/ttyUSB3', 500000)  # 根據實際串口調整
        motor.connect("/dev/ttyUSB3", 500000)
        # 測試基本功能
        motor.clearError()
        pos = motor.getPos()
        logger.debug(f'Current position: {pos}')
        
        motor.setVel(10000)
        vel = motor.getVel()
        logger.debug(f'Current velocity: {vel}')
        
        error = motor.checkError()
        logger.debug(f'Error status: {error}')
        
        # 測試移動
        motor.moveAbsPos(5000)
        time.sleep(3)
        motor.moveAbsPos(0)
        time.sleep(3)

        motor.setStop()
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        motor.disconnect()
