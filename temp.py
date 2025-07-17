import cv2
import multiprocessing as mp
from collections import deque
import numpy as np
import time

def video_capture_process(src, frame_deque, stop_event, deque_lock, maxlen):
    """
    在獨立進程中讀取影片幀
    src: 攝影機來源
    frame_deque: 用於傳遞幀的共享列表
    stop_event: 用於通知進程停止的事件
    deque_lock: 用於同步訪問列表的鎖
    maxlen: 最大幀數
    """
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        print("錯誤：無法打開攝影機")
        return
        
    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            print("錯誤：無法讀取幀")
            break
            
        # 使用鎖來安全地操作共享列表
        with deque_lock:
            # 如果列表已滿，移除最舊的幀
            if len(frame_deque) >= maxlen:
                frame_deque.pop(0)  # 移除最舊的幀
            frame_deque.append(frame)
            
    cap.release()
    print("影片擷取進程已結束")

class VideoCaptureProcess:
    def __init__(self, src="/dev/video1", maxlen=2):
        # 創建進程管理器
        self.manager = mp.Manager()
        # 用於儲存幀的共享列表
        self.frame_deque = self.manager.list()
        self.maxlen = maxlen
        # 用於同步訪問列表的鎖
        self.deque_lock = mp.Lock()
        # 用於控制進程停止的事件
        self.stop_event = mp.Event()
        # 攝影機來源
        self.src = src
        # 進程物件
        self.process = None
        
    def start(self):
        """啟動影片擷取進程"""
        self.stop_event.clear()
        self.process = mp.Process(
            target=video_capture_process,
            args=(self.src, self.frame_deque, self.stop_event, self.deque_lock, self.maxlen)
        )
        self.process.daemon = True
        self.process.start()
        
    def read(self):
        """從共享列表中獲取最新的幀"""
        with self.deque_lock:
            if len(self.frame_deque) > 0:
                # 獲取最新的幀（最後一個元素）
                return True, self.frame_deque[-1]
            return False, None
            
    def stop(self):
        """停止影片擷取進程"""
        self.stop_event.set()
        if self.process is not None:
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.kill()
        # 清空列表
        with self.deque_lock:
            self.frame_deque[:] = []  # 清空共享列表
        self.manager.shutdown()

# 使用範例
if __name__ == "__main__":
    # 初始化影片擷取進程 (0 代表預設攝影機)
    cap_process = VideoCaptureProcess(src=1, maxlen=2)
    cap_process.start()
    
    try:
        while True:
            # 從進程中獲取幀
            ret, frame = cap_process.read()
            if ret:
                # 在這裡處理幀，例如顯示
                cv2.imshow('Frame', frame)
                
            # 按 'q' 退出
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
            # 稍微延遲以避免過度使用 CPU
            time.sleep(0.01)
            
    finally:
        # 清理資源
        cap_process.stop()
        cv2.destroyAllWindows()