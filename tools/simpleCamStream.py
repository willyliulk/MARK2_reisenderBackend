import cv2
import numpy as np
import sys

arg_id = sys.argv[1]
id = f'/dev/video{arg_id}'
print(id)
cap = cv2.VideoCapture(id, cv2.CAP_V4L2)
if not cap.isOpened():
    print(f"Can't open camera: {id}")
    exit(1)    

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
cap.set(cv2.CAP_PROP_FPS, 120)
cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
cap.set(cv2.CAP_PROP_EXPOSURE, int(300))

print(cap.get(cv2.CAP_PROP_AUTO_EXPOSURE))
print(cap.get(cv2.CAP_PROP_EXPOSURE))
# cap.set(cv2.CAP_PROP_BRIGHTNESS, int(40))

    


while True:
    ret, frame = cap.read()
    if not ret:
        print(f"Can't receive frame: camera_{id}")
        break
    
    cv2.imshow(f"camera_{id}", frame)
    
    if cv2.waitKey(100) == ord('q'):
        break
    
cap.release()