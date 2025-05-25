import traceback
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import uvicorn
from loguru import logger
import numpy as np
import cv2
import pynng

import sys, time, os 
import base64, json
import asyncio
from pathlib import Path
from enum import Enum
from typing import List, Optional, Dict
from contextlib import asynccontextmanager

from utils import get_min_len_path
from motorManager import MotorManager, MotorManager_v2
from machineManager import MachineManager

# TODO: 軟體按下 EmgStop 處理程序呼叫需要有API
# TODO: 提供專門的API取得最近一次的拍照結果嗎?
# TODO: 確認需要一個從 Cam/Shot 到 Predict 打包好的API嗎
# TODO: 單獨開一個API保存setPoint清單
# TODO: 多開一個API POST /v2/mechine/resolve，會觸發機器自我檢測
# TODO: 更新motor的sp清單的shema
# TODO: 新加sp multi 的處裡
# TODO: 新加mechine GO_HOME state


# ----------- Pydantic Models -----------
class MotorSetPointReq(BaseModel):
    pos_list: List[float]
    pos_list_multiMotor: Optional[Dict[str, List[float]]] = {
        "motor0":[10,20.55,30],
        "motor1":[100,90,80.23]
    }
    sp_type: Optional[str] = "single"

class MotorMoveAbsReq(BaseModel):
    pos: float
class MotorMoveIncReq(BaseModel):
    pos: float

# ----------- 資源管理類 -----------
class ResourceManager:
    def __init__(self, motor_port: str, camera_configs: List[dict]):
        self.motor:MotorManager = MotorManager(motor_port)
        self.motorV2_list = [
            MotorManager_v2(0, 30),
            MotorManager_v2(1, 360-30)
        ]
        self.dataStop = False
        self.cameras_list = {}
        self.locks = {}
        
        # 初始化攝影機並設定參數
        for cfg in camera_configs:
            # cap = cv2.VideoCapture(cfg["dev"], cv2.CAP_V4L2)
            cap = cv2.VideoCapture(cfg["dev"])
            # 設定參數...
            cap.set(cv2.CAP_PROP_BUFFERSIZE     , 1)
            cap.set(cv2.CAP_PROP_FPS            , 30)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH    , 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT   , 480)
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE  , 1)
            cap.set(cv2.CAP_PROP_EXPOSURE       , int(300))
            if not cap.isOpened():
                logger.error(f"Camera {cfg['name']} open failed")
                continue
            self.cameras_list[cfg["name"]] = cap
            self.locks[cfg["name"]] = asyncio.Lock()
        
        with open('camData.json', 'r') as f:
            cam_data = json.load(f)
        Camera_matrix = np.array(cam_data['camera_matrix'])
        Distortion_coefficients = np.array(cam_data['distortion_coefficients'])
        self.camera_matrix = Camera_matrix
        self.distortion_coefficients = Distortion_coefficients
        
        # TODO:更新mechine manager
        self.machineGood = True
        self.machineManager = MachineManager(self.motorV2_list, self.cameras_list)

        
    
    async def initialize(self):
        """異步初始化方法"""
        # 初始化全部 MotorManager_v2
        try:
            for motor_v2 in self.motorV2_list:
                await motor_v2.startManager()
            await self.machineManager.startManager()
        except pynng.exceptions.ConnectionRefused as e:
            pass
        except Exception as e:
            pass

    async def cleanup(self):
        self.motor.closeManager()
        await self.machineManager.closeManager()
        for motor_v2 in self.motorV2_list:
            await motor_v2.closeManager()
        # 釋放攝影機資源
        for cap in self.cameras_list.values():
            cap.release()




# 初始化鎖定變數
lock_cap1 = asyncio.Lock()
lock_cap2 = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # camera_configs = [
        #     {"dev": "/dev/video0", "name": "cam1"},
        #     {"dev": "/dev/video2", "name": "cam2"}
        # ]
        
        camera_configs = [
            {"dev": "./testRes/SampleVideo_720x480_5mb.mp4", "name": "cam0"},
            {"dev": "./testRes/SampleVideo_720x480_5mb.mp4", "name": "cam1"}
        ]
        
        resources = ResourceManager('/dev/ttyUSB3', camera_configs)
        # 執行異步初始化
        await resources.initialize()
        app.state.resources = resources
        logger.info("All resources initialized")
        
        yield
        
    finally:
        await app.state.resources.cleanup()
        logger.info("Resources cleaned up")


# ----------- FastAPI App -----------
app = FastAPI(lifespan=lifespan, title="ReisenderTECH MARK I",
              description='''MARK I API 包含馬達控制與影片串流 \n
              websocket端點：\n
              馬達資訊：/v2/ws/motor/{id}/data\n
              影像串流：/v2/ws/cam/{id}\n
              按鈕狀態：/v2/ws/machine''')
app.mount("/js"     , StaticFiles(directory="./html/js"))
app.mount("/css"    , StaticFiles(directory="./html/css"))
app.mount("/numPic" , StaticFiles(directory="./html/numPic"))
app.mount("/pics"   , StaticFiles(directory="./html/pics"))

origins = [
    "http://localhost",
    "http://localhost:8080",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------- 依賴注入 -----------
def get_resources(request: Request) -> ResourceManager:
    return request.app.state.resources

# ----------- 路由 -----------
#region MAKR1_deprecated

@app.get("/", deprecated=True)
def get_root():
    return FileResponse(path="html/index.html")

@app.get("/motor/data", deprecated=True)
async def get_motor_data(resources: ResourceManager = Depends(get_resources)):
        data = resources.motor.getMotorData()
        return JSONResponse({
            "pos":data.pos,
            "vel":data.vel,
        })


@app.websocket("/ws/motor/data")
async def ws_motorData(websocket: WebSocket, 
                       resources: ResourceManager = Depends(get_resources)):
    await websocket.accept()
    try:
        while True:
            data = resources.motor.getMotorData()
            data2 = resources.motor.getMotorButton()
            if data2[0] == 1:
                resources.dataStop = True
                print("stop!!!")
            if data2[1] == 1:
                print("operate!!!")
                
            motorDataJson = {
                "pos":data.pos,
                "vel":data.vel,
                "btnShot":data2[1]
            }
            
            await websocket.send_json(motorDataJson)
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        logger.debug("Client motor/data disconnected")


@app.websocket("/ws/cam/1")
async def ws_cam1(websocket: WebSocket):
    global cap1
    await websocket.accept()
    
    # cap1  = cv2.VideoCapture(0)
    
    # if not cap1:
    #     logger.debug("Error opening video stream or file")

    try:
        while True:
            async with lock_cap1:
                ret, frame = cap1.read() # type: ignore
            
            if not ret:
                break
            
            #frame = cv2.undistort(frame, Camera_matrix, Distortion_coefficients)

            
            frame = cv2.resize(frame, (240, 180))
            ret, buffer = cv2.imencode('.webp', frame, [cv2.IMWRITE_WEBP_QUALITY, 50])
            if not ret:
                break
            jpegb64 = base64.b64encode(buffer).decode('utf-8')
            
            await websocket.send_text(jpegb64)
            await asyncio.sleep(0.1)
            
    except WebSocketDisconnect:
        logger.debug("Client cam1          disconnected")
    except Exception as e:
        logger.debug(f"連接中斷： {e}")
        
    finally:
        pass
        cap1.release() # type: ignore
        lock_cap1.release()
        await websocket.close()

@app.websocket("/ws/cam/2")
async def ws_cam2(websocket: WebSocket):
    global cap2
    await websocket.accept()
    
    # cap2  = cv2.VideoCapture(r"C:\Users\liuwilly\Videos\2024-08-13 11-23-50.mp4")
    
    # if not cap2:
    #     logger.debug("Error opening video stream or file")

    try:
        while True:
            async with lock_cap2:
                # logger.info('cam2 say hi')
                ret, frame = cap2.read() # type: ignore
            
            if not ret:
                break
            
            
            #frame = cv2.undistort(frame, Camera_matrix, Distortion_coefficients)
            
            frame = cv2.resize(frame, (240, 180))
            ret, buffer = cv2.imencode('.webp', frame, [cv2.IMWRITE_WEBP_QUALITY, 50])
            if not ret:
                break
            jpegb64 = base64.b64encode(buffer).decode('utf-8')
            
            await websocket.send_text(jpegb64)
            await asyncio.sleep(0.1)
            
    except WebSocketDisconnect:
        logger.debug("Client cam2          disconnected")
        
    except Exception as e:
        logger.debug(f"連接中斷： {e}")
        
    finally:
        cap2.release() # type: ignore
        lock_cap2.release()
        await websocket.close()



@app.get('/motor/move/stop', deprecated=True)
def motor_move_stop():
    global motorManager
    logger.debug('motor move stop')
    motorManager.motorStop() # type: ignore
    return "OK"

@app.get('/motor/move/inc/{value}', deprecated=True)
def motor_move_inc(value:int):
    global motorManager
    logger.debug(f'motor move inc {value}')
    motorManager.goIncPos(value) # type: ignore
    return "OK"

@app.get('/motor/move/abs/{value}', deprecated=True)
def motor_move_abs(value:int):
    global motorManager
    logger.debug(f'motor move abs {value}')
    motorManager.goAbsPos(value) # type: ignore
    return "OK"

@app.post('/motor/move/sp', deprecated=True)
async def motor_move_sp(req: MotorSetPointReq, 
                  resources: ResourceManager = Depends(get_resources)):
    global motorManager, dataStop
    logger.debug(f'motor move sp: {req.pos_list}')
    # motorManager.
    for target_pos in req.pos_list:
        resources.motor.goAbsPos(target_pos) # type: ignore
        start = time.time()

        # 等待運行到目標點
        while True:
            motor_pos = resources.motor.getMotorData().pos
            motor_stop = resources.motor.getMotorButton()[0]
            
            # 抵達目標點
            if abs(motor_pos - target_pos) > 5 or motor_stop == 1:
                break
            
            # 處理執行超時
            if time.time() - start > 10:
                raise HTTPException(status_code=408, detail="Motor move timeout")
            
            # 處理停止指令
            if dataStop == True:
                print("STOP in app")
                dataStop=False
                raise Exception("STOP")
                
            await asyncio.sleep(0.01)
        
        await asyncio.sleep(0.5)
    
    if len(req.pos_list) != 0:
        with open('SPconfig.json', 'w') as f:
            json.dump(req.pos_list, f)
            
    return "OK"


@app.post('/cam/shot', deprecated=True)
async def cam_shot(listSP: List[int]):
    global motorManager, cap1, cap2, dataStop
    logger.debug("capture photo with pos", listSP)
    imageList = {
        "cam1": [],
        "cam2": [],
    }
    
    # 清理舊檔案
    dirs = os.listdir('motorImage')
    for file in dirs:
        filePath = os.path.join('motorImage', file)
        if os.path.isfile(filePath):
            os.remove(filePath)
            
    if listSP == []:
        with open('./SPconfig.json', 'r') as f:
            listSP = json.load(f)
    
    # plan new optimal path
    curPos = motorManager.getMotorData().pos # type: ignore
    disList = [abs(curPos - sp) for sp in listSP]
    minDis = min(disList)
    minDisIndex = disList.index(minDis)
    minDisSp = listSP[minDisIndex]    
    minLen_SpList, _  = get_min_len_path(listSP, minDisIndex)
            
    # apply the path
    listSP_new = [listSP[i] for i in minLen_SpList] # type: ignore

    for i in range(0, len(minLen_SpList)): # type: ignore
        motorManager.goAbsPos(listSP_new[i]) # type: ignore
    
        start_time = time.time()
        while abs(motorManager.getMotorData().pos - listSP_new[i]) > 5: # type: ignore
            if dataStop == True:
                print("STOP in app")
                dataStop=False
                raise Exception("STOP")
            await asyncio.sleep(0.01)
            if time.time() - start_time > 5:  # Timeout after 5 seconds
                logger.warning(f"Movement timeout at position {listSP_new[i]}")
                break
        await asyncio.sleep(1)
        
        # 使用所有鎖同時擷取圖像
        async with lock_cap1, lock_cap2:
            cameras = [
                (cap1, "cam1"), # type: ignore
                (cap2, "cam2"), # type: ignore
            ]
            
            for cap, cam_name in cameras:
                ret, frame = cap.read()
                try:
                    if not ret:
                        continue
                    
                    frame_toSave = frame
                    cv2.imwrite(f'/home/ubuntu/Desktop/pythonBackend/motorImage/{cam_name}_{i}.jpg', frame_toSave)
                    
                    ret, buffer = cv2.imencode('.webp', frame, [cv2.IMWRITE_WEBP_QUALITY, 80])
                    if not ret:
                        continue
                    jpegb64 = base64.b64encode(buffer).decode('utf-8')
                    imageList[cam_name].append(jpegb64)
                except Exception as e:
                    logger.error(f"{cam_name} 處理失敗: {str(e)}")
                    continue

            await asyncio.sleep(0.5)
            
    if len(listSP) != 0:
        with open('SPconfig.json', 'w') as f:
            json.dump(listSP, f)

    return JSONResponse(imageList)

@app.get('/motors/spInit', deprecated=True)
def get_motor_spInit():
    with open('SPconfig.json', 'r') as f:
        loaded_list = json.load(f)
    
    if len(loaded_list) != 0:
        return JSONResponse(loaded_list)
    else:
        return JSONResponse([x for x in range(0, 60001, 1000)])


def getPostFiles():
    img_paths = os.listdir('motorImage')
    files=[]
    for i, img_path in enumerate(img_paths):
        temp = (
            'file', 
            (f'img{i}.jpg', open(f'/home/ubuntu/Desktop/pythonBackend/motorImage/{img_path}', 'rb') , 'image/jpeg')
        )
        files.append(temp)
    return files

@app.get('/result/upload', deprecated=True)
def result_upload():
    global motorManager
    global curSavePath

    logger.debug('result upload')

    files = getPostFiles()
    response = requests.post(
        "http://localhost:5001/img_predict",
        headers={
            "accept": "application/json"
        },
        files=files,
        timeout=10
    )

    result=dict()
    if response.status_code == 200:
        logger.debug("請求成功!")
        res = response.json()
        logger.debug("前三高結果為:")
        for i in range(3):
            logger.debug(res[i])
        
        counter = 0
        result["result"] = list()
        for i in range(len(res)):
            cur = res[i]
            if cur['part'] != "torque_converter":
                continue
            result["result"].append(cur)
            counter += 1
            if counter == 3:
                break
            
        # result["result"] = res[0:3]
              
        # save feature
        # Create folder to store results
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        result_folder = f"/home/ubuntu/Desktop/resultsFromReisender/{timestamp}"
        os.makedirs(result_folder, exist_ok=True)
        
        # Save images
        img_paths = os.listdir('motorImage')
        for img_path in img_paths:
            src = f'/home/ubuntu/Desktop/pythonBackend/motorImage/{img_path}'
            dst = f'{result_folder}/{img_path}'
            os.system(f'cp {src} {dst}')

        # Save prediction results
        results_json = {
            "timestamp": timestamp,
            "all_predictions": res,
        }
        
        with open(f"{result_folder}/prediction_results.json", "w") as f:
            json.dump(results_json, f, indent=4)
        
        print("結果已保存至 JSON 文件->", result_folder)
        
        curSavePath = timestamp
        result["savePlace"] = curSavePath
    return result


@app.post("/correctLabel", deprecated=True)
def post_correctLabel(correctLabel:str):
    print("hohohohohoho")
    print(correctLabel)
    try:
        global curSavePath
        savePathPrefix = r"/home/ubuntu/Desktop/resultsFromReisender"
        ppp = f"{savePathPrefix}/{curSavePath}/correct.txt"
        print(ppp)
        with open(ppp, "w") as correctLabel_file:
            correctLabel_file.write(correctLabel)
        return True
    
    except Exception as e:
        return e
#endregion


#region MARK2

@app.get('/v2/machine/emergency')
def v2_get_machine_emergency(resources: ResourceManager = Depends(get_resources)):
    return {'emergency':not resources.machineGood}

@app.get('/v2/machine/health')
def v2_get_machine_health(resources: ResourceManager = Depends(get_resources)):
    # {'health':'ok'} 
    # 馬達問題回傳 "motor"
    # 鏡頭問題回傳 "camera"
    if resources.machineGood:
        return {'health':'ok'}
    else:
        raise HTTPException(status_code=500, detail="Motor error")

@app.get('/v2/machine/error_log')
def v2_get_machine_error_log(resources: ResourceManager = Depends(get_resources)):
    return {'error_log':"randomPlaceholder"}

@app.post('/v2/machine/raise_error')
async def v2_post_machine_raise_error(resources: ResourceManager = Depends(get_resources)):
    resources.machineGood = False
    resources.machineManager.raise_error()
    return {'error':'Error raised by user.'}

@app.post('/v2/machine/resolve')
async def v2_post_machine_resolve(resources: ResourceManager = Depends(get_resources)):
    resources.machineGood = True
    await resources.machineManager.resolve_error()
    return {'statue':'ok'}

@app.get('/v2/motor/{id}/data')
def v2_get_motor_data(id:int, resources: ResourceManager = Depends(get_resources)):
    if id >= len(resources.motorV2_list):
        return JSONResponse(status_code=404, content={"error": "Motor not found"})
    data = resources.motorV2_list[id].get_motorData()
    state = resources.motorV2_list[id].get_motorState()
    proximitys = resources.motorV2_list[id].get_proximitys()
    is_home = resources.motorV2_list[id].is_home()
    return {
        'id':id,
        'pos':data.pos,
        'vel':data.vel,
        'state':state.name,
        'proximitys':proximitys,
        'is_home':is_home,
    }

@app.websocket('/v2/ws/motor/{id}/data')
async def v2_ws_motor_data(websocket:WebSocket ,id:int):
    await websocket.accept()
    resources: ResourceManager = websocket.app.state.resources

    if id >= len(resources.motorV2_list):
        return JSONResponse(status_code=404, content={"error": "Motor not found"})

    try:
        while True:
            # data = resources.motorV2_list[id].get_motorData()
            data = resources.motorV2_list[id].get_motorData()
            state = resources.motorV2_list[id].get_motorState()
            proximitys = resources.motorV2_list[id].get_proximitys()
            is_home = resources.motorV2_list[id].is_home()
            motorDataJson =  {
                'id':id,
                'pos':data.pos,
                'vel':data.vel,
                'state':state.name,
                'proximitys':proximitys,
                'is_home':is_home,
            }
            await websocket.send_json(motorDataJson)
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        logger.info(f"WebSocket connection closed for motor {id}")
        
@app.websocket('/v2/ws/cam/{id}')
async def v2_ws_cam(websocket:WebSocket ,id:int):
    await websocket.accept()
    resources :ResourceManager = websocket.app.state.resources

    try:
        while True:
            cap:cv2.VideoCapture = resources.cameras_list[f"cam{id}"]
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            jpegb64 = base64.b64encode(buffer).decode('utf-8')
            await websocket.send_text(jpegb64)
            await asyncio.sleep(0.01)
    except WebSocketDisconnect:
        logger.info(f"WebSocket connection closed for cam {id}")


def get_machien_state(resources: ResourceManager):
    # IDEL: 如果所有軸都處於正常狀態
    # SHOTTING : 拍照中返回
    # AI_PROC : AI處理中
    # ERROR : 如果有軸處於異常狀態
    # 如果有軸處於異常狀態，則返回 ERROR
    # TODO 補齊功能
    return 'IDLE' # fake foro debug
    for motor in resources.motorV2_list:
        if motor.get_motorState() == 'error':
            return 'ERROR'

def get_machine_btn(resources: ResourceManager) -> list[str]:
    # 可能包含 ["shot", 'home', "EMG"]
    # TODO 補齊功能
    return resources.machineManager.get_btn_list()
    
@app.websocket('/v2/ws/machine')
async def v2_ws_machine(websocket:WebSocket):
    await websocket.accept()
    # 從 websocket.state 獲取 resources
    resources :ResourceManager = websocket.app.state.resources

    try:
        while True:
            # data = resources.motorV2_list[id].get_motorData()
            staet = get_machien_state(resources)
            btn_on = get_machine_btn(resources)
            machineDataJson = {
                'emergency':False,
                'reason':'random Placeholder',
                'state':staet,
                'colorLight':'y',
                'btn_on':btn_on
            }
            await websocket.send_json(machineDataJson)
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        logger.info(f"WebSocket connection closed for machine")


@app.post('/v2/motor/{id}/move/stop')
def v2_motor_move_stop(id:int,
                    resources: ResourceManager = Depends(get_resources)):
    if id >= len(resources.motorV2_list):
        return JSONResponse(status_code=404, content={"error": "Motor not found"})
    motor = resources.motorV2_list[id]
    motor.motorStop()
    return {"status": "OK"}

@app.post('/v2/motor/{id}/move/abs')
def v2_motor_move_abs(id:int, moveAbsReq:MotorMoveAbsReq,
                   resources: ResourceManager = Depends(get_resources)):
    if id >= len(resources.motorV2_list):
        return JSONResponse(status_code=404, content={"error": "Motor not found"})
    motor = resources.motorV2_list[id]
    pos = moveAbsReq.pos
    motor.goAbsPos(pos)
    return {"status": "OK"}

@app.post('/v2/motor/{id}/move/home')
def v2_motor_move_home(id:int, resources: ResourceManager = Depends(get_resources)):
    if id >= len(resources.motorV2_list):
        return JSONResponse(status_code=404, content={"error": "Motor not found"})
    motor = resources.motorV2_list[id]
    motor.goHomePos()
    return {"status": "OK"}

@app.post('/v2/motor/{id}/move/inc')
def v2_motor_move_inc(id:int, moveIncReq:MotorMoveIncReq,
                   resources: ResourceManager = Depends(get_resources)):
    motor = resources.motorV2_list[id]
    pos = moveIncReq.pos
    motor.goIncPos(pos)
    return {"status": "OK"}
    
async def wait_motor_move_to_pos(motor:MotorManager_v2, motor_id: int, target_pos: float):
    start = time.time()
    while True:
        motor_pos = motor.get_motorData().pos
        motor_proximity = motor.get_proximitys()
        motor_stop = any(motor_proximity) or motor.motorState==MotorManager_v2.MotorState.ERROR

        # 抵達目標點或被停止
        if abs(motor_pos - target_pos) <= 5:
            logger.debug(f'Motor move to {motor_pos} success')
            break
        
        # 處理執行超時
        if time.time() - start > 8:
            logger.error(f"Motor {motor_id} move to pos {target_pos} timeout, now at {motor_pos}")
            raise HTTPException(status_code=408, detail=f"Motor move timeout to target: {target_pos}")
        
        # 處理停止指令
        if motor_stop:
            print("STOP in app")
            # motor_stop = False
            raise Exception("STOP")
            
        await asyncio.sleep(0.01)
        
async def capture_images(resources: ResourceManager, cam_name:str, position_index: str) -> dict|None:
    """擷取兩個相機的圖片並返回編碼後的數據"""
    image_data = None
    
    # 確保圖片保存目錄存在
    save_dir = "motorImage"
    os.makedirs(save_dir, exist_ok=True)

    cap = resources.cameras_list[cam_name]
    async with resources.locks[cam_name]:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
        # 保存原始圖片
        save_path = f'{save_dir}/{cam_name}_{position_index}.jpg'
        cv2.imwrite(save_path, frame)
        
        # 編碼圖片用於網頁傳輸
        ret, buffer = cv2.imencode('.jpg', frame)
        if ret:
            jpegb64 = base64.b64encode(buffer).decode('utf-8')
            image_data = {cam_name:jpegb64}

    return image_data

async def handle_single_motor_sequence(resources: ResourceManager, motor_id: int, cam_name:str,
                                       positions: List[float], to_reverse = False, 
                                       to_shot: bool = False) -> List[dict]:
    """處理單個馬達的移動和拍照序列"""
    motor = resources.motorV2_list[motor_id]
    image_results = []
    
    # for pos in positions:
    while positions:
        if to_reverse:
            target_pos = positions.pop(-1)
        else:
            target_pos = positions.pop(0)
        
        # 移動到指定位置
        motor.goAbsPos(target_pos)
        await wait_motor_move_to_pos(motor, motor_id, target_pos)
        await asyncio.sleep(0.5)  # 穩定等待
        
        # 如果需要拍照
        if to_shot:
            images = await capture_images(resources, cam_name, f"{motor_id}_{target_pos}")
            image_results.append(images)
    
    motor.goHomePos()
    
    return image_results

async def sp_move_helper(resources: ResourceManager, sp_list: List[float], to_shot: bool = False) -> dict:
    """協調兩個馬達同時執行各自的移動和拍照序列"""
    sp_queue = sorted(sp_list)  # 排序位置列表
    
    # 創建兩個並行任務，一個從小到大，一個從大到小
    # task1 = asyncio.create_task(
    #     handle_single_motor_sequence(resources, 0, sp_queue, to_shot)
    # )
    # task2 = asyncio.create_task(
    #     handle_single_motor_sequence(resources, 1, sp_queue, to_shot, to_reverse=True)
    # )
    
    # 等待兩個任務完成並獲取結果
    results1, results2 = await asyncio.gather(
        handle_single_motor_sequence(resources, 0, 'cam0', sp_queue, False, to_shot), 
        handle_single_motor_sequence(resources, 1, 'cam1', sp_queue, True , to_shot)
    )
    
    if not to_shot:
        return {"status": "OK"}
    
    # 如果有拍照，整理照片結果
    image_results = {
        "cam0": [],
        "cam1": []
    }
    
    # 合併兩個馬達的結果
    for result in results1 + results2:
        for cam_name, image_data in result.items():
            image_results[cam_name].append(image_data)
    
    return image_results

@app.post('/v2/motors/move/sp')
async def v2_motors_move_sp(spReq: MotorSetPointReq,
                          resources: ResourceManager = Depends(get_resources)):
    """處理多點移動請求並返回拍攝的圖片"""
    try:
        # 清理舊檔案
        # save_dir = "motorImage"
        # if os.path.exists(save_dir):
        #     for file in os.listdir(save_dir):
        #         os.remove(os.path.join(save_dir, file))
        # os.makedirs(save_dir, exist_ok=True)
        
        # 執行移動和拍照
        image_results = await sp_move_helper(resources, spReq.pos_list, to_shot=False)
        
        # 保存設定點位置
        if spReq.pos_list:
            with open('SPconfig.json', 'w') as f:
                json.dump(spReq.model_dump_json(), f)
            logger.info(f"Saved SPconfig.json: {spReq.pos_list}")
            
        return JSONResponse(content=image_results)
        
    except Exception as e:
        logger.error(f"Error in v2_motors_move_sp: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/v2/motors/spSim')
async def v2_motors_spSim(spReq: MotorSetPointReq,
                          resources: ResourceManager = Depends(get_resources)):
    """處理多點移動請求並返回拍攝的圖片"""
    
    simData = {
            "motor0":[0,10,20,40,50],
            "motor1":[180,170,160,150]
        }
    return simData

# 新增一個拍照的端點
@app.post('/v2/cam/shot', description="目前暫時回傳固定測試資料")
async def v2_cam_shot(spReq: MotorSetPointReq,
                        resources: ResourceManager = Depends(get_resources)):
    """執行拍照序列"""
    # test data
    # with open("./tools/testImgData.json") as f:
    #     json_data = json.load(f)
    
    # with open('SPconfig.json', 'w') as f:
    #     momdelJson = shotReq.model_dump_json()
    #     momdelJson = json.loads(momdelJson)
    #     json.dump(momdelJson, f)
    #     logger.info(f"Saved SPconfig.json: {shotReq.pos_list}")

    
    # return json_data
    
    try:
        # 清理舊檔案
        save_dir = "motorImage"
        if os.path.exists(save_dir):
            for file in os.listdir(save_dir):
                os.remove(os.path.join(save_dir, file))
        os.makedirs(save_dir, exist_ok=True)
        
        # 執行移動和拍照
        image_results = await sp_move_helper(resources, spReq.pos_list, to_shot=True)
        
        # 保存設定點位置
        if spReq.pos_list:
            with open('SPconfig.json', 'w') as f:
                json.dump(spReq.model_dump_json(), f)
            logger.info(f"Saved SPconfig.json: {spReq.pos_list}")
            
        return JSONResponse(content=image_results)
        
    except Exception as e:
        logger.error(f"Error in v2_cam_shot: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        raise HTTPException(status_code=500, detail=str(e))
        
        logger.error(f"Error in v2_cam_shot: {str(e)}")
        
        raise HTTPException(status_code=500, detail=str(e))



@app.get('/v2/motor/spInit')
def v2_get_motor_spInit():
    """
    Get the initial set points for motors. If SPconfig.json exists and contains data,
    return those points. Otherwise return default points from 0 to 60000 with 1000 step.
    """
    try:
        with open('SPconfig.json', 'r') as f:
            loaded_list = json.load(f)
        
        if len(loaded_list) != 0:
            return JSONResponse(loaded_list)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
        
    # Return default points if no valid config found
    return JSONResponse([x for x in range(0, 60001, 1000)])


@app.post('/v2/result/upload')
def v2_result_upload(resources: ResourceManager = Depends(get_resources)):
    """
    Upload the result to the server. The result is a list of dictionaries, each containing
    the image data and the corresponding motor positions.
    """
    # TODO 補齊功能

    return {'result':   [
    {
        "directory": "VO10 Volvo BM14 Transfer",
        "family": "ZF4HP22",
        "index": 244,
        "label": "vo10_volvo_bm14_transfer",
        "make": "VOLVO",
        "part": "torque_converter",
        "probability": 0,
        "subcategory": "2.3L 740 GLE"
    },
    {
        "directory": "VW8 VW RE9 Transfer",
        "family": "095, 096, 097",
        "index": 249,
        "label": "vw8_vw_re9_transfer",
        "make": "VW",
        "part": "torque_converter",
        "probability": 0,
        "subcategory": "2.0L Passat"
    },
    {
        "directory": "Honda PYRA Transfer",
        "family": "PYRA",
        "index": 415,
        "label": "honda_pyra_transfer",
        "make": "HONDA",
        "part": "transmission_case",
        "probability": 0,
        "subcategory": "14-17 ODYSSEY"
    }
    ]}


#endregion 


if __name__ == "__main__":
    logger.remove()
    # 子模塊也都只顯示info leve; 訊息
    logger.add(sys.stdout, level="DEBUG")
    logger.add("log/app.log", level="INFO", rotation="10 MB", compression="zip")
    logger.configure(handlers=[{"sink": sys.stderr, "level": "INFO"}])
    print('hello')
    uvicorn.run(app='app:app', host="0.0.0.0", port=8800)

