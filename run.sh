#!/bin/bash

# echo 等待結束，伺服器啟動

# # 激活虛擬環境
# source /home/ubuntu/Desktop/pythonBackend/.linuxenv/bin/activate

# # 執行你的 Python 腳本
# python /home/ubuntu/Desktop/pythonBackend/app.py
# /home/ubuntu/Desktop/pythonBackend/.linuxenv/bin/uvicorn app:app --host 0.0.0.0 --port 8800
# 如果需要，在這裡添加更多命令


source .vene/Scripts/activate
python /mechineSimulator/testPLace3.py
python app.py 