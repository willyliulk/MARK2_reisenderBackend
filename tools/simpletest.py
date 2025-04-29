# import requests
# import os

# def getPostFiles():
#     img_paths = os.listdir('motorImage')
#     files=[]
#     for i, img_path in enumerate(img_paths):
#         temp = (
#             'file', 
#             (f'img{i}.jpg', open(f'motorImage/{img_path}', 'rb') , 'image/jpeg')
#         )
#         files.append(temp)
#     return files

# files = getPostFiles()

# response = requests.post(
#     "http://localhost:5001/img_predict",
#     headers={
#         "accept": "application/json"
#     },
#     files=files
# )

# if response.status_code == 200:
#     print("請求成功!")
#     res = response.json()
#     # print("回應內容:", res)
#     for i in res:
#         print(i)
# else:
#     print("請求失敗。狀態碼:", response.status_code)
#     print("錯誤訊息:", response.text)


import serial.tools.list_ports
import subprocess

def list_usb_devices_and_tty():
    # 使用 pyserial 列出所有的串口裝置
    ports = list(serial.tools.list_ports.comports())
    
    if not ports:
        print("No USB serial devices found.")
        return
    
    desList = [port.device for port in ports if port.description=='USB Serial']

    if len(desList) == 0:
        raise Exception("no RS485 converter")

    print(f"RS485 converter is at:")
    print(desList[0])

    # for port in ports:
    #     # 獲取裝置名稱和描述
    #     device = port.device
    #     description = port.description
        
    #     # 嘗試找到更詳細的裝置名稱
    #     try:
    #         # 使用 lsusb 獲取裝置詳細資訊
    #         lsusb_output = subprocess.run(['lsusb'], stdout=subprocess.PIPE, text=True).stdout
    #         usb_devices = lsusb_output.splitlines()
            
    #         # 根據 VID 和 PID 嘗試匹配更詳細的名稱
    #         vid_pid = f"{port.vid:04x}:{port.pid:04x}" if port.vid and port.pid else ""
    #         detailed_name = next((line for line in usb_devices if vid_pid in line), "Unknown USB Device")
    #     except Exception as e:
    #         detailed_name = "Unknown USB Device"

    #     print(f"Device: {device}, Description: {description}, Detailed Name: {detailed_name}")

# import cv2
# from loguru import logger
# # from matplotlib import pyplot as plt

# def show_corp_image():
#     cap1  = cv2.VideoCapture(0, cv2.CAP_V4L2)
#     cap1.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
#     cap1.set(cv2.CAP_PROP_FPS,30)
#     cap1.set(cv2.CAP_PROP_FRAME_WIDTH,   1920)
#     cap1.set(cv2.CAP_PROP_FRAME_HEIGHT,  1080)
#     if not cap1:
#         logger.debug("Error opening video stream or file")
#         exit()
        
#     ret, frame = cap1.read()
#     if not ret:
#         return 
#     # 650 400 1300 900
#     frame = frame[400:1080,400:1500]
#     cv2.imwrite('win.jpg', frame)
#     # cv2.waitKey(5000)



if __name__ == "__main__":
    # print(serial.tools.list_ports.comports())
    list_usb_devices_and_tty()
    # show_corp_image()