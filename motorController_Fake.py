from singleton_decorator import singleton
from loguru import logger
import time
import random

@singleton
class FakeMotorController:
    def __init__(self, port: str = None, baud: int = 115200):
        """初始化假馬達控制器"""
        self.port = port
        self.baudrate = baud
        self.connected = False
        
        # 模擬馬達狀態
        self._position = 0
        self._velocity = 1000
        self._error_code = 0
        self._is_moving = False
        self._target_position = 0
        self._move_start_time = 0
        
        logger.info(f"Fake motor controller initialized with port:{port}, baud:{baud}")
        
    def connect(self, port: str = None, baud: int = 115200):
        """模擬連接到馬達控制器"""
        self.port = port or self.port
        self.baudrate = baud or self.baudrate
        logger.info(f"Fake connection setup port:{self.port}, baud:{self.baudrate}")
        
        # 模擬連接成功
        time.sleep(0.5)  # 模擬連接延遲
        self.connected = True
        logger.debug(f"Fake serial connection established with {self.port}")
        return True
        
    def disconnect(self):
        """模擬斷開連接"""
        if self.connected:
            time.sleep(0.1)  # 模擬斷開連接延遲
            self.connected = False
            logger.debug("Fake serial connection closed")
            
    def _send_command(self, cmd: str) -> str:
        """模擬發送命令並讀取回應"""
        if not self.connected:
            logger.error("Not connected to fake motor controller")
            return ""
            
        # 模擬通訊延遲
        time.sleep(0.01)
        
        # 處理移動命令
        if cmd.startswith("m") and len(cmd) > 1:
            try:
                target_pos = int(cmd[1:])
                self._target_position = target_pos
                self._is_moving = True
                self._move_start_time = time.time()
                return "OK"
            except ValueError:
                return "ERROR"
        # 獲取位置命令
        elif cmd == "m":
            self._update_position()
            return str(self._position)
        # 設置速度命令
        elif cmd.startswith("v") and len(cmd) > 1:
            try:
                self._velocity = float(cmd[1:])
                return "OK"
            except ValueError:
                return "ERROR"
        # 獲取速度命令
        elif cmd == "v":
            return str(self._velocity)
        # 停止命令
        elif cmd == "s":
            self._is_moving = False
            return "OK"
        # 清除錯誤命令
        elif cmd == "c":
            # 模擬按鈕狀態，隨機返回
            return f"{random.randint(0, 1)}{random.randint(0, 1)}"
        # 檢查錯誤命令
        elif cmd == "e":
            return str(self._error_code)
        else:
            return "UNKNOWN COMMAND"
            
    def _update_position(self):
        """根據當前時間更新位置"""
        if self._is_moving:
            # 計算從移動開始到現在經過的時間
            elapsed_time = time.time() - self._move_start_time
            
            # 計算應該移動的距離
            distance = self._target_position - self._position
            
            # 根據速度計算需要的時間
            required_time = abs(distance) / self._velocity
            
            if elapsed_time >= required_time:
                # 移動完成
                self._position = self._target_position
                self._is_moving = False
            else:
                # 移動中
                progress = elapsed_time / required_time
                self._position = int(self._position + distance * progress)
                
    def moveAbsPos(self, pos: int):
        """移動到絕對位置"""
        if pos > 2147483647 or pos < -2147483647:
            raise ValueError(f"pos value must between -2147483647~2147483647, now is {pos}")
        response = self._send_command(f"m{pos}")
        logger.debug('Moved abs')
        return response
        
    def moveIncPos(self, pos: int):
        """移動增量位置"""
        if pos > 2147483647 or pos < -2147483647:
            raise ValueError(f"pos value must between -2147483647~2147483647, now is {pos}")
            
        current_pos = self.getPos()
        target_pos = current_pos + pos
        
        response = self._send_command(f"m{target_pos}")
        logger.debug(f'Moved inc from {current_pos} to {target_pos} (delta: {pos})')
        return response
        
    def getPos(self) -> int:
        """獲取當前位置"""
        response = self._send_command("m")
        try:
            return int(response)
        except ValueError as e:
            logger.error(f"Invalid position value received: {response}:{len(response)}")
            raise IOError(f"Invalid data from fake motor: {e}")
            
    def getVel(self) -> float:
        """獲取當前速度"""
        response = self._send_command("v")
        try:
            return float(response)
        except ValueError as e:
            logger.error(f"Invalid velocity value received: {response}")
            raise IOError(f"Invalid data from fake motor: {e}")
            
    def setVel(self, vel: float):
        """設置速度"""
        response = self._send_command(f"v{vel}")
        logger.debug(f'Set velocity to {vel}')
        return response
        
    def setStop(self):
        """停止馬達"""
        response = self._send_command("s")
        logger.debug('Motor Stop')
        return response
        
    def clearError(self):
        """清除錯誤"""
        self._error_code = 0
        response = 'done'
        logger.debug('Motor clean error')
        return response
        
    def checkButton(self):
        """檢查按鈕狀態"""
        response = self._send_command("c")
        return response
        
    def checkError(self) -> int:
        """檢查錯誤狀態，0=OK, 6=Location out of tolerance"""
        return self._error_code


if __name__ == "__main__":
    # 設置日誌
    logger.add("fake_motor.log", rotation="10 MB")
    
    # 測試假馬達控制器
    motor = None
    try:
        motor = FakeMotorController('/dev/ttyUSB0', 500000)
        motor.connect()
        
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
        logger.debug("Moving to position 5000...")
        motor.moveAbsPos(5000)
        
        # 模擬等待移動完成
        for _ in range(10):
            time.sleep(0.3)
            current_pos = motor.getPos()
            logger.debug(f"Current position: {current_pos}")
            
        logger.debug("Moving back to position 0...")
        motor.moveAbsPos(0)
        
        # 模擬等待移動完成
        for _ in range(10):
            time.sleep(0.3)
            current_pos = motor.getPos()
            logger.debug(f"Current position: {current_pos}")
            
        # 測試增量移動
        logger.debug("Moving incrementally by 2000...")
        motor.moveIncPos(2000)
        time.sleep(2)
        logger.debug(f"Final position: {motor.getPos()}")
        
        motor.setStop()
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        if motor:
            motor.disconnect()
