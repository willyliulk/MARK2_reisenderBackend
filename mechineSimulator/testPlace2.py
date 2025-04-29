import pynng
import json
import time

def send_command(command):
    """發送指令到相機系統"""
    with pynng.Req0(dial="tcp://127.0.0.1:5555") as req:
        # 發送指令
        req.send(json.dumps(command).encode('utf-8'))
        
        # 接收回應
        response = json.loads(req.recv().decode('utf-8'))
        print(f"回應: {response}")
        return response

if __name__ == "__main__":
    # 示例1: 移動相機1到指定位置
    send_command({
        "type": "rotate_to",
        "camera_id": 1,
        "angle": 180.0
    })
    
    time.sleep(2)
    
    # 示例2: 設置相機2以固定速度旋轉
    send_command({
        "type": "rotate",
        "camera_id": 2,
        "speed": 1.0  # 弧度/秒
    })
    
    time.sleep(5)
    
    # 示例3: 停止相機2
    send_command({
        "type": "stop",
        "camera_id": 2
    })