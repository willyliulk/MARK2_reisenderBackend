import cv2
import numpy as np
from matplotlib import pyplot as plt

id = 6
cap = cv2.VideoCapture(id)

if not cap.isOpened():
    print("Can't open camera")
    exit(1)    
    


while True:
    ret, frame = cap.read()
    if not ret:
        print("Can't receive frame")
        break
    
    cv2.imshow(f"camera_{id}", frame)
    
    if cv2.waitKey(1) == ord('q'):
        break
    
cap.release()