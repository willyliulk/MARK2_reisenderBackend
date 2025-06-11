from dataclasses import dataclass, asdict
from copy import deepcopy
from enum import Enum
import asyncio
import base64, json
import traceback
from typing import Dict, List, Optional, Tuple
import time
from pathlib import Path
import sys, os

import cv2
from loguru import logger
import pynng

from utils import DualMotorPathOptimizer, spDict_to_pathList

class MachineState(Enum):
    IDLE = 0
    WORKING = 1
    HOMING = 2
    ERROR = 3

class LampState:
    def __init__(self, r=False, y=False, g=False):
        self.r = r
        self.y = y
        self.g = g
    
    @staticmethod
    def from_dict(data: dict) -> 'LampState':
        return LampState(
            r=bool(data.get('r', False)),
            y=bool(data.get('y', False)),
            g=bool(data.get('g', False))
        )
    
    def to_dict(self) -> dict:
        return {'r': self.r, 'y': self.y, 'g': self.g}

@dataclass
class ButtonState:
    emg     :bool = False
    shot    :bool = False
    home    :bool = False
    resolve :bool = False
    unknow  :bool = False


@dataclass
class MotorData:
    id:int = 0
    pos:float = 0
    spd:float = 0
    state:str = "IDLE"
    

class MachineManager:
    """
    管理機器狀態、攝像頭和通訊的非阻塞異步類
    支援FastAPI異步操作
    """
    def __init__(self, 
                 camera_configs: List[dict],
                 motor0_home_pos = 30, motor1_home_pos = 330,
                 cmd_addr: str = "tcp://127.0.0.1:8780" if sys.platform.startswith("win") else "ipc:///tmp/pico_cmd",
                 stat_addr: str = "tcp://127.0.0.1:8781" if sys.platform.startswith("win") else "ipc:///tmp/pico_stat"):
        
        # 基本設定
        self.cmd_addr = cmd_addr
        self.stat_addr = stat_addr
        self._cmd_id = 0
        self._is_running = False
        self._tasks = []
        
        # 狀態相關
        self._state = MachineState.IDLE
        self._error_reason = ""
        self._emergency = False
        self._lamp_state = LampState(g=True)  # 默認綠燈亮
        
        # 攝像頭
        self.camera_list: Dict[str, cv2.VideoCapture] = {}
        self.camera_locks: Dict[str, asyncio.Lock] = {}
        
        # 按鈕狀態 (供前端查詢)
        self.buttons = ButtonState()
        
        # 馬達狀態
        self.motor_data = [MotorData(id=id) for id in range(2)]
        self.motor0_home_pos = motor0_home_pos
        self.motor1_home_pos = motor1_home_pos
        self.motors_home_pos = [motor0_home_pos, motor1_home_pos]
        
        # 限位開關狀態
        self.limitSwitchs = [False for _ in range(2)]
        
        # 初始化攝像頭
        for cfg in camera_configs:
            self._init_camera(cfg)
    
    def _init_camera(self, config: dict):
        """初始化攝像頭並設定參數"""
        try:
            cap = cv2.VideoCapture(config["dev"])
            if not cap.isOpened():
                logger.error(f"無法打開攝像頭 {config['name']}")
                return
            
            # 設置攝像頭參數
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_FPS, 30)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            # 存儲攝像頭和對應的鎖
            self.camera_list[config["name"]] = cap
            self.camera_locks[config["name"]] = asyncio.Lock()
            logger.info(f"攝像頭 {config['name']} 初始化成功")
        except Exception as e:
            logger.error(f"攝像頭 {config['name']} 初始化失敗: {e}")
    
    async def start(self):
        """啟動MachineManager的所有異步任務"""
        if self._is_running:
            return
            
        self._is_running = True
        
        # 創建和啟動所有任務
        try:
            # 狀態監聽任務
            status_task = asyncio.create_task(self._status_listener())
            self._tasks.append(status_task)
            
            # 錯誤監控任務
            error_task = asyncio.create_task(self._error_monitor())
            self._tasks.append(error_task)
            
            # 三色燈控制任務
            lamp_task = asyncio.create_task(self._lamp_controller())
            self._tasks.append(lamp_task)
            
            btnMoni_task = asyncio.create_task(self._btnMoniTask())
            self._tasks.append(btnMoni_task)
            
            logger.info("MachineManager 已啟動")
            
            # 發送初始化命令，設置綠燈
            await self.set_lamp(r=False, y=True, g=False)
            
        except Exception as e:
            logger.error(f"MachineManager啟動失敗: {e}")
            logger.error(traceback.format_exc())
            await self.stop()
    
    async def stop(self):
        """停止所有任務並釋放資源"""
        self._is_running = False
        
        # 取消所有任務
        for task in self._tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self._tasks.clear()
        
        # 釋放攝像頭資源
        for name, cap in self.camera_list.items():
            cap.release()
            logger.info(f"攝像頭 {name} 已釋放")
        
        logger.info("MachineManager已停止")
    
    async def _status_listener(self):
        """監聽下位機狀態的異步任務"""
        try:
            with pynng.Sub0(dial=self.stat_addr) as sub:
                sub.subscribe(b"")
                logger.info(f"已連接到狀態通道: {self.stat_addr}")
                
                while self._is_running:
                    try:
                        # 非阻塞接收，超時後繼續循環
                        msg = await asyncio.wait_for(sub.arecv_msg(), timeout=0.5)
                        data = json.loads(msg.bytes.decode())
                        
                        # 處理狀態數據
                        await self._process_status_data(data)
                    except asyncio.TimeoutError:
                        continue
                    except json.JSONDecodeError:
                        logger.warning("收到無效的JSON數據")
                    except Exception as e:
                        logger.error(f"處理狀態數據時出錯: {e}")
                        await asyncio.sleep(0.5)  # 出錯後等待一段時間再繼續
        
        except Exception as e:
            logger.error(f"狀態監聽任務出錯: {e}")
            if self._is_running:
                # 嘗試重新啟動任務
                asyncio.create_task(self._status_listener())
    
    async def _process_status_data(self, data: dict):
        """處理從下位機接收的狀態數據"""
        # 處理馬達狀態
        if "m" in data and isinstance(data["m"], list):
            for i, motor in enumerate(data["m"]):
                if i < len(self.motor_data):
                    self.motor_data[i].pos = motor.get("pos", 0)
                    self.motor_data[i].spd = motor.get("spd", 0)
                    self.motor_data[i].state = motor.get("state", "IDLE")
        
        # 處理按鈕狀態
        if "btn" in data and isinstance(data["btn"], list):
            btn_list = data["btn"]
            # 按鈕腳位 (緊急, 拍攝, 紅、綠、藍)
            if len(btn_list) >= 4:
                self.buttons.emg = bool(btn_list[0])
                self.buttons.shot = bool(btn_list[1])
                self.buttons.home = bool(btn_list[2])
                self.buttons.resolve = bool(btn_list[3])
                self.buttons.unknow = bool(btn_list[4])
        
        # 處理限位開關狀態
        if "lim" in data and isinstance(data["lim"], list):
            lim_list = data["lim"]
            if len(lim_list) >= 2:
                self.limitSwitchs = [sw==1 for sw in lim_list ]
                if any(lim_list) and self._state != MachineState.HOMING:
                    await self._handle_error("限位開關觸發")
                    
        
        # 處理燈狀態同步
        if "lamp" in data:
            self._lamp_state = LampState.from_dict(data["lamp"])
    
    async def _error_monitor(self):
        """監控系統錯誤的異步任務"""
        while self._is_running:
            try:
                # 檢查馬達錯誤
                for i, motor in enumerate(self.motor_data):
                    if motor.state == "ERROR":
                        await self._handle_error(f"馬達 {i} 錯誤")
                
                # 檢查攝像頭錯誤
                for name, cap in self.camera_list.items():
                    if not cap.isOpened():
                        await self._handle_error(f"攝像頭 {name} 連接丟失")
                
                # 檢查緊急按鈕
                if self.buttons.emg:
                    await self._handle_error("緊急停止按鈕已按下")
                
                # 檢查解除錯誤
                if self.buttons.resolve and self._state == MachineState.ERROR:
                    await self.resolve_error()
                
                await asyncio.sleep(0.2)  # 定期檢查
            
            except Exception as e:
                logger.error(f"錯誤監控任務出錯: {e}")
                await asyncio.sleep(1)  # 出錯後等待較長時間
    
    async def _lamp_controller(self):
        """控制三色燈的異步任務"""
        prev_state = None
        
        while self._is_running:
            try:
                # 根據當前狀態設置燈光
                if self._state != prev_state:
                    if self._state == MachineState.IDLE:
                        await self.set_lamp(r=False, y=False, g=True)  # 綠燈
                    elif self._state == MachineState.ERROR:
                        await self.set_lamp(r=True, y=False, g=False)  # 紅燈
                    else:  # WORKING 或 HOMING
                        await self.set_lamp(r=False, y=True, g=False)  # 黃燈
                    
                    prev_state = self._state
                
                await asyncio.sleep(0.5)
            
            except Exception as e:
                logger.error(f"燈控制任務出錯: {e}")
                await asyncio.sleep(1)
    
    def getSPConfig(self):
        with open('SPconfig.json', 'r') as f:
            loaded_sp = json.load(f)
        if isinstance(loaded_sp, str):
            loaded_sp:Dict = json.loads(loaded_sp)
        return loaded_sp
    
    async def _btnMoniTask(self):
        btnStatePrev = deepcopy(self.buttons)
        shotElapseTime = time.time()
        while True:
            btnStateNow = deepcopy(self.buttons)
            tNow = time.time()
            # logger.debug((btnStateNow.__repr__()))
            
            if all([btnStatePrev.home == False,
                    btnStateNow.home  == True]):
                logger.debug("home button acivate")
                await self.motor_home()
            
            if all([btnStatePrev.resolve == False,
                    btnStateNow.resolve == True]):
                logger.debug("resolve button activate")
                await self.resolve_error()
            
            if all([btnStatePrev.emg == False,
                    btnStateNow.emg == True]):
                logger.debug("emergency button activate")
                self.trigger_emergency()
                
            await asyncio.sleep(0.05)
                
    
    async def _handle_error(self, reason: str):
        """處理錯誤狀態"""
        if self._state != MachineState.ERROR:
            logger.error(f"機器錯誤: {reason}")
            self._state = MachineState.ERROR
            self._error_reason = reason
            self._emergency = True
            
            # 設置紅燈
            await self.set_lamp(r=True, y=False, g=False)
            
            # 嘗試停止所有馬達
            for i in range(2):
                await self.motor_stop(i)
    
    async def resolve_error(self):
        """解除錯誤狀態"""
        # if self._state == MachineState.ERROR:
        logger.info("解除錯誤狀態")
        self._state = MachineState.HOMING
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.send_command({"cmd": "HOME", "m": 1}))
            tg.create_task(self.send_command({"cmd": "HOME", "m": 2}))
             
        self._state = MachineState.IDLE
        self._error_reason = ""
        self._emergency = False
        
        # 清除下位機錯誤
        # for i in range(2):
        #     # await self.send_command({"cmd": "STOP", "m": i+1})
        
        # 設置綠燈
        await self.set_lamp(r=False, y=False, g=True)
        
        return True
        return False
    
    async def send_command(self, cmd: dict) -> dict:
        """發送命令到下位機並等待回應"""
        try:
            # 增加命令ID
            self._cmd_id += 1
            cmd["cid"] = self._cmd_id
            
            with pynng.Req0(dial=self.cmd_addr, recv_timeout=10000) as req:
                await req.asend(json.dumps(cmd).encode())
                response = await req.arecv()
                return json.loads(response.decode())
        
        except pynng.exceptions.Timeout:
            logger.error(f"命令超時: {cmd}")
            return {"ok": False, "err": "Timeout"}
        
        except Exception as e:
            logger.error(f"發送命令時出錯: {cmd} - {e}")
            return {"ok": False, "err": str(e)}
    
        
    
    async def capture_image(self, camera_name: str, position_index:float) -> Optional[Tuple[bool, bytes]]:
        """捕獲指定攝像頭的圖像"""
        if camera_name not in self.camera_list:
            logger.error(f"未找到攝像頭: {camera_name}")
            return None
        # 確保圖片保存目錄存在
        save_dir = "motorImage"
        os.makedirs(save_dir, exist_ok=True)

        cap = self.camera_list[camera_name]
        lock = self.camera_locks[camera_name]
        
        async with lock:
            if not cap.isOpened():
                logger.error(f"攝像頭 {camera_name} 未打開")
                return None
            
            ret, frame = cap.read()
            if not ret:
                logger.error(f"從攝像頭 {camera_name} 讀取圖像失敗")
                return None
            
            # 保存原始圖片
            save_path = f'{save_dir}/{camera_name}_{position_index}.jpg'
            cv2.imwrite(save_path, frame)
            
            # 壓縮圖像以便傳輸
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                logger.error(f"壓縮圖像失敗: {camera_name}")
                return None
            jpegb64 = base64.b64encode(buffer).decode('utf-8')
            return (True, jpegb64)
    
    async def set_lamp(self, r: bool, y: bool, g: bool) -> bool:
        """設置三色燈狀態"""
        response = await self.send_command({
            "cmd": "LAMP",
            "r": int(r),
            "y": int(y),
            "g": int(g)
        })
        
        if response.get("ok", False):
            self._lamp_state = LampState(r=r, y=y, g=g)
            return True
        return False
    
    async def motor_move_abs(self, motor_id: int, position: float) -> bool:
        """控制馬達移動到絕對位置"""
        if self._state == MachineState.ERROR:
            logger.warning(f"機器處於錯誤狀態，無法移動馬達 {motor_id}")
            return False
        logger.info(f"motor_move_abs: id={motor_id}, pos={position}")
        await asyncio.sleep(0.1)
        # 更新狀態為工作中
        prev_state = self._state
        self._state = MachineState.WORKING
        
        response = await self.send_command({
            "cmd": "MOVE",
            "m": motor_id + 1,  # 下位機馬達編號從1開始
            "pos": position
        })
        
        if not response.get("ok", False):
            logger.error(f"馬達移動失敗: {response.get('err', 'Unknown error')}")
            if prev_state != MachineState.ERROR:  # 避免覆蓋已有的錯誤狀態
                self._state = prev_state
            return False
        
        return True
    
    async def motor_move_inc(self, motor_id: int, increment: float) -> bool:
        """控制馬達移動增量位置"""
        if self._state == MachineState.ERROR:
            return False
        
        # 計算新位置
        current_pos = self.motor_data[motor_id].pos
        new_pos = current_pos + increment
        
        return await self.motor_move_abs(motor_id, new_pos)
    
    async def motor_stop(self, motor_id: int) -> bool:
        """停止指定馬達"""
        response = await self.send_command({
            "cmd": "STOP",
            "m": motor_id + 1
        })
        
        return response.get("ok", False)
    
    async def motor_home(self, motor_id: int) -> bool:
        """馬達回原點"""
        if self._state == MachineState.ERROR:
            return False
        
        prev_state = self._state
        self._state = MachineState.HOMING
        
        response = await self.send_command({
            "cmd": "HOME",
            "m": motor_id + 1
        })
        
        if not response.get("ok", False):
            if prev_state != MachineState.ERROR:
                self._state = prev_state
            return False
        
        return True
    
    def motor_is_home(self, motor_id=0):
        if motor_id<0 or motor_id>1:
            raise Exception(f"motor_is_home: invalid motor_id: {motor_id}")

        if motor_id == 0:
            pos = self.motor0_home_pos
            home_pos = self.motor_data[0].pos
        else:
            pos = self.motor1_home_pos
            home_pos = self.motor_data[1].pos
        return  abs(pos - home_pos) < 0.5
        
    
    async def save_params(self) -> bool:
        """保存參數到下位機"""
        response = await self.send_command({
            "cmd": "SAVE"
        })
        
        return response.get("ok", False)
    
    async def load_params(self) -> bool:
        """從下位機加載參數"""
        response = await self.send_command({
            "cmd": "LOAD"
        })
        
        return response.get("ok", False)
    
    async def set_motor_params(self, motor_id: int, max_speed: Optional[float] = None, 
                              acceleration: Optional[float] = None) -> bool:
        """設置馬達參數"""
        cmd = {
            "cmd": "SET",
            "m": motor_id + 1
        }
        
        if max_speed is not None:
            cmd["max"] = max_speed
        
        if acceleration is not None:
            cmd["acc"] = acceleration
        
        response = await self.send_command(cmd)
        return response.get("ok", False)
    
    # 獲取當前狀態的方法 (用於前端API)
    def get_state(self) -> dict:
        """獲取機器當前狀態，用於前端API"""
        return {
            "state": self._state.name,
            "emergency": self._emergency,
            "reason": self._error_reason,
            "lamp": self._lamp_state.to_dict(),
            "motors": asdict(self.motor_data),
            "buttons": asdict(self.buttons)
        }
    
    def get_camera_list(self) -> List[str]:
        """獲取所有可用攝像頭名稱"""
        return list(self.camera_list.keys())
    
    def is_error(self) -> bool:
        """檢查是否處於錯誤狀態"""
        return self._state == MachineState.ERROR
    
    def get_error_reason(self) -> str:
        """獲取錯誤原因"""
        return self._error_reason if self._state == MachineState.ERROR else ""


    async def trigger_emergency(self):
        """觸發緊急停止"""
        logger.warning("觸發緊急停止")
        self._state = MachineState.ERROR
        self._emergency = True
        self._error_reason = "緊急停止觸發"
        
        # 設置紅燈
        await self.set_lamp(r=True, y=False, g=False)
        
        # 停止所有馬達
        for i in range(len(self.motor_data)):
            await self.motor_stop(i)

    def get_error_log(self) -> dict:
        """返回當前錯誤日誌"""
        return {
            "state": self._state.name,
            "emergency": self._emergency,
            "reason": self._error_reason,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        }

    def is_emergency(self) -> bool:
        """檢查機器是否處於緊急停止狀態"""
        return self._emergency

    def get_state_data(self) -> dict:
        """獲取機器當前狀態的完整數據"""
        # 確定目前的燈號顏色
        if self._lamp_state.r:
            light_color = "r"
        elif self._lamp_state.y:
            light_color = "y"
        elif self._lamp_state.g:
            light_color = "g"
        else:
            light_color = "off"
        
        # 確定機器狀態
        machine_state = self._state.name
        
        # 獲取按下的按鈕列表
        btn_on = []
        btn_on = []
        
        for btn, status in asdict(self.buttons).items():
            if status:
                btn_on.append(btn)
        
        return {
            'emergency': self._emergency,
            'reason': self._error_reason,
            'state': machine_state,
            'colorLight': light_color,
            'btn_on': btn_on
        }

    def get_btn_list(self) -> list:
        """獲取當前按下的按鈕列表"""
        return [btn for btn, status in asdict(self.buttons).items() if status]


    
    async def wait_motor_move_to_pos(self, motor_id: int, target_pos: float):
        start = time.time()
        while True:
            motor_pos = self.motor_data[motor_id].pos
            motor_proximity = self.limitSwitchs[motor_id]
            motor_stop = motor_proximity or self.motor_data[motor_id].state == "ERROR"
            mechineStop = self.is_emergency()

            # 抵達目標點或被停止
            if abs(motor_pos - target_pos) <= 5:
                logger.debug(f'Motor move to {motor_pos} success')
                break
            
            # 處理執行超時
            if time.time() - start > 8:
                logger.error(f"Motor {motor_id} move to pos {target_pos} timeout, now at {motor_pos}")
                raise Exception(f"Motor move timeout to target: {target_pos}")
            
            # 處理停止指令
            if motor_stop:
                print("STOP in app")
                raise Exception("STOP: motor_stop")
            
            if mechineStop:
                print("STOP in app")
                self.motor_stop(motor_id)
                raise Exception("STOP: mechineStop")
                
            await asyncio.sleep(0.01)

    async def handle_single_motor_sequence(self, motor_id=0, motor_pts=[30, 330], to_shot=False, cam_name='cam0'):
        """處理單個馬達的運動序列"""
        image_list = []
        for pt in motor_pts:
            ret = await self.motor_move_abs(motor_id, pt)
            if not ret:
                raise Exception(f"motor {motor_id} moving pt error")
            
            await self.wait_motor_move_to_pos(motor_id, pt)
            
            if to_shot:
                result = await self.capture_image(cam_name, pt)
                if result is not None:  # 檢查 result 是否為 None
                    _, img = result
                    image_list.append(img)
            else:
                await asyncio.sleep(0.5)
        ret = await self.motor_move_abs(motor_id, self.motors_home_pos[motor_id])
        if not ret:
            raise Exception(f"motor {motor_id} moving pt error")

        return image_list
                    
                    
    
    async def motors_move_points_shot(self, motor0_pts, motor1_pts, to_shot=False):
        """
        讓馬達移動到指定的點位列表
        """
        async with asyncio.TaskGroup() as tg:
            task1 = tg.create_task(self.handle_single_motor_sequence(0, motor0_pts, to_shot, 'cam0'))
            task2 = tg.create_task(self.handle_single_motor_sequence(1, motor1_pts, to_shot, 'cam1'))

        if to_shot:
            return (task1.result(), task2.result())
        return None