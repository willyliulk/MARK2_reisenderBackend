import cv2
import numpy as np
import time

idList = [
          '/dev/video0',
          '/dev/video2',
        #   '/dev/video4',
        #   '/dev/video6',
          ]
capList = []
for i in idList:
    cap = cv2.VideoCapture(i)
    time.sleep(0.5)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    cap.set(cv2.CAP_PROP_FPS, 1)
    
    print("camera ID:   " + str(i) )
    print('width:       ' + str(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) )
    print('height:      ' + str(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) )
    print('fps:         ' + str(cap.get(cv2.CAP_PROP_FPS)) )
    
    
    if not cap.isOpened():
        print("Can't open camera")
        exit(1)    
        
    capList.append(cap)
    

while True:
    for i, cap in enumerate(capList):
            
        ret, frame = cap.read()
        if not ret:
            # print("Can't receive frame")
            break
        
        new_size = tuple(map(int, ( frame.shape[1]/2, frame.shape[0]/2 )))
        frame = cv2.resize(frame, new_size)
        
        cv2.imshow(f"camera_{idList[i]}", frame)
    
    if cv2.waitKey(100) == ord('q'):
        break
    
cv2.destroyAllWindows()

for i, cap in enumerate(capList):
  cap.release()

