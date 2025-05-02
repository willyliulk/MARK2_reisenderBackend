#!/usr/bin/env python3
import os
import platform
import subprocess
import time
import signal
import sys
import stat

class ProcessManager:
    def __init__(self):
        self.processes = []
        self.system = platform.system()
        # 獲取當前工作目錄
        self.current_dir = os.getcwd()
        
        # 根據系統設定 MQTT Broker 指令
        if self.system == "Windows":
            self.mqtt_cmd = ["mqttBroker\\win64\\bin\\nanomq.exe", "start", "--conf", "mqttBroker\\win64\\nanomq.conf"]
            self.mqtt_path = "mqttBroker\\win64\\bin\\nanomq.exe"
        else:  # Linux/Ubuntu
            self.mqtt_cmd = ["./mqttBroker/ubuntu/nanomq", "start", "--conf", "mqttBroker/ubuntu/nanomq.conf"]
            self.mqtt_path = "mqttBroker/ubuntu/nanomq"
        
        self.machine_simulator_cmd = ["uv", "run", "./mechineSimulator/testPlace3.py"]
        self.app_cmd = ["uv", "run", "./app.py"]

    def ensure_executable(self, path):
        """確保文件具有執行權限"""
        if self.system != "Windows" and os.path.exists(path):
            current_mode = os.stat(path).st_mode
            os.chmod(path, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            print(f"已賦予 {path} 執行權限")

    def start_processes(self):
        print(f"使用工作目錄: {self.current_dir}")
        
        # 確保 MQTT Broker 有執行權限
        if self.system != "Windows":
            self.ensure_executable(self.mqtt_path)
            
        print("啟動 MQTT Broker...")
        try:
            mqtt_process = self.start_process(self.mqtt_cmd)
            self.processes.append(mqtt_process)
            print("MQTT Broker 已啟動，等待 2 秒...")
            time.sleep(2)
        except Exception as e:
            print(f"啟動 MQTT Broker 時發生錯誤: {e}")
            if self.system != "Windows":
                print("嘗試使用 sudo 啟動 MQTT Broker...")
                sudo_mqtt_cmd = ["sudo"] + self.mqtt_cmd
                mqtt_process = self.start_process(sudo_mqtt_cmd)
                self.processes.append(mqtt_process)
                print("MQTT Broker 已啟動，等待 2 秒...")
                time.sleep(2)

        print("啟動機器模擬器...")
        simulator_process = self.start_process(self.machine_simulator_cmd)
        self.processes.append(simulator_process)
        print("機器模擬器已啟動，等待 2 秒...")
        time.sleep(2)

        print("啟動應用程式...")
        app_process = self.start_process(self.app_cmd)
        self.processes.append(app_process)
        print("應用程式已啟動")

        print("\n所有程序已啟動。按 Ctrl+C 終止所有程序...")

    def start_process(self, cmd):
        # 在 Windows 上，使用 creationflags 參數創建新的控制台窗口
        if self.system == "Windows":
            return subprocess.Popen(
                cmd,
                cwd=self.current_dir,  # 設定工作目錄為當前目錄
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            # 在 Linux 上，使用標準方式啟動進程
            return subprocess.Popen(
                cmd,
                cwd=self.current_dir,  # 設定工作目錄為當前目錄
                stdout=subprocess.PIPE,  # 捕獲標準輸出
                stderr=subprocess.PIPE   # 捕獲標準錯誤
            )

    def terminate_processes(self):
        print("\n正在終止所有程序...")
        for process in reversed(self.processes):
            try:
                if self.system == "Windows":
                    # Windows 上使用 taskkill 確保子進程也被終止
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], 
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    # Linux 上發送 SIGTERM 信號
                    process.terminate()
                    process.wait(timeout=2)
            except Exception as e:
                print(f"終止進程時發生錯誤: {e}")
        
        print("所有程序已終止")

def signal_handler(sig, frame):
    process_manager.terminate_processes()
    sys.exit(0)

if __name__ == "__main__":
    process_manager = ProcessManager()
    
    # 註冊信號處理器以捕獲 Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        process_manager.start_processes()
        # 保持主進程運行，直到收到中斷信號
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        process_manager.terminate_processes()
