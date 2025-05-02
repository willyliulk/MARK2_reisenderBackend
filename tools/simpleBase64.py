import  cv2

# read a image and show its jped base64 encoded string
import base64
import numpy as np
import cv2

def encode_image(image_path):
    # Read the image
    image = cv2.imread(image_path)
    # Convert the image to JPEG format
    _, jpeg_image = cv2.imencode('.jpg', image)
    # Encode the JPEG image as a base64 string
    base64_string = base64.b64encode(jpeg_image).decode('utf-8')
    return base64_string
# Example usage
image_path = r'D:\Code\mix\Vizuro\reisenderBackend\html\numPic\1.JPG'
base64_string = encode_image(image_path)
print(base64_string)