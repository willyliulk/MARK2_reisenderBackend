import pygame
import sys
import os
import math
import threading
import paho.mqtt.client as mqtt
import json
from enum import Enum

class CameraState(Enum):
    IDLE = 0
    DRAGGING = 1
    ROTATING_TO_ANGLE = 2
    ROTATING = 3
    ERROR_HIT = 4

class Camera:
    def __init__(self, x, y, radius=20, color=(255, 0, 0), id=0, angle_limit=(0, 360)):
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color
        self.id = id
        self.state = CameraState.IDLE
        self.target_angle = None  # 目標角度（度）
        self.rotation_speed = 0  # 角度/秒
        self.rotation_angle = 0  # 當前角度（度）
        self.center_x = 0
        self.center_y = 0
        self.distance_from_center = 0
        self.angle_limit = angle_limit  # (min_angle, max_angle)，限制角度範圍，度數

        resPath = os.path.join(os.path.dirname(__file__), 'res/camera.png')
        self.image_orig = pygame.image.load(resPath)
        self.image_orig = pygame.transform.scale(self.image_orig, (radius*2, radius*2))
        self.imageRect = self.image_orig.get_rect()

    def update_center(self, center_x, center_y):
        self.center_x = center_x
        self.center_y = center_y
        self.distance_from_center = math.sqrt((self.x - center_x)**2 + (self.y - center_y)**2)
        # 計算當前角度(度)
        self.rotation_angle = math.degrees(math.atan2(self.y - center_y, self.x - center_x)) % 360

    def draw(self, screen:pygame.Surface):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius, 2)
        pygame.draw.line(screen, self.color, (int(self.x), int(self.y)), (int(self.center_x), int(self.center_y)), 2)
        font = pygame.font.SysFont(None, 24)
        id_text = font.render(str(self.id), True, (255, 255, 255))
        screen.blit(id_text, (int(self.x - 5), int(self.y - 10)))
        screen.blit(self.image, self.imageRect)

    def is_clicked(self, pos):
        dx = pos[0] - self.x
        dy = pos[1] - self.y
        return dx*dx + dy*dy <= self.radius*self.radius

    def rotate_to_angle(self, angle):
        # 限制角度在範圍內並轉換成0~360度
        angle = angle % 360
        min_angle, max_angle = self.angle_limit
        # 若最大角度小於最小角度，代表跨越0度，特別處理
        if min_angle <= max_angle:
            if angle < min_angle:
                angle = min_angle
            elif angle > max_angle:
                angle = max_angle
        else:
            # 跨越0度範圍，例如(350, 10)
            if not (angle >= min_angle or angle <= max_angle):
                # 不在允許範圍內，選擇離目標最近的邊界
                dist_min = (angle - min_angle) % 360
                dist_max = (max_angle - angle) % 360
                angle = min_angle if dist_min < dist_max else max_angle

        self.target_angle = angle
        self.state = CameraState.ROTATING_TO_ANGLE

    def set_rotation(self, speed):
        self.rotation_speed = speed
        if speed != 0:
            self.state = CameraState.ROTATING
        else:
            self.state = CameraState.IDLE

    def update(self, dt, other_camera=None):
        if self.state == CameraState.ROTATING_TO_ANGLE and self.target_angle is not None:
            # 計算角度差，考慮360度循環
            diff = (self.target_angle - self.rotation_angle + 360) % 360
            if diff > 180:
                diff -= 360  # 取最短路徑旋轉方向

            step = self.rotation_speed * dt if self.rotation_speed != 0 else 180 * dt  # 預設180度/秒
            if abs(diff) <= step:
                self.rotation_angle = self.target_angle
                self.state = CameraState.IDLE
                self.rotation_speed = 0
                self.target_angle = None
            else:
                self.rotation_angle = (self.rotation_angle + step * (1 if diff > 0 else -1)) % 360

        elif self.state == CameraState.ROTATING:
            self.rotation_angle = (self.rotation_angle + self.rotation_speed * dt) % 360

        # 限制角度上下限
        min_angle, max_angle = self.angle_limit
        if min_angle <= max_angle:
            if self.rotation_angle < min_angle:
                self.rotation_angle = min_angle
            elif self.rotation_angle > max_angle:
                self.rotation_angle = max_angle
        else:
            # 跨越0度範圍，例如(350, 10)
            if not (self.rotation_angle >= min_angle or self.rotation_angle <= max_angle):
                # 強制限制在最近邊界
                dist_min = (self.rotation_angle - min_angle) % 360
                dist_max = (max_angle - self.rotation_angle) % 360
                self.rotation_angle = min_angle if dist_min < dist_max else max_angle

        # 更新位置
        rad = math.radians(self.rotation_angle)
        new_x = self.center_x + math.cos(rad) * self.distance_from_center
        new_y = self.center_y + math.sin(rad) * self.distance_from_center

        # 碰撞檢查
        if other_camera:
            dx = new_x - other_camera.x
            dy = new_y - other_camera.y
            distance = math.sqrt(dx*dx + dy*dy)
            if distance < self.radius + other_camera.radius:
                self.rotation_speed = 0
                self.state = CameraState.ERROR_HIT
                return

        self.x = new_x
        self.y = new_y

        # 更新圖片角度和位置
        self.image = pygame.transform.rotate(self.image_orig, -self.rotation_angle + 90)
        self.imageRect = self.image.get_rect()
        self.imageRect.center = (self.x, self.y)

class CameraSystem:
    def __init__(self, broker="127.0.0.1", port=11883):
        pygame.init()
        self.width, self.height = 800, 600
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("相機基座控制系統")

        self.base_x = self.width // 2
        self.base_y = self.height // 2
        self.base_radius = 50

        # 角度上下限設定（可自訂）
        angle_limit_cam1 = (15, 345)  # 可修改為其他範圍
        angle_limit_cam2 = (15, 345)

        self.cameras = [
            Camera(self.base_x - 150, self.base_y, color=(255, 0, 0), id=1, angle_limit=angle_limit_cam1),
            Camera(self.base_x + 150, self.base_y, color=(0, 0, 255), id=2, angle_limit=angle_limit_cam2)
        ]

        for camera in self.cameras:
            camera.update_center(self.base_x, self.base_y)

        self.dragging_camera = None
        self.clock = pygame.time.Clock()
        self.running = True

        # 設置MQTT客戶端
        self.client = mqtt.Client(client_id="camera_system")
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        
        # 設置MQTT連接參數
        self.broker = broker
        self.port = port
        
        self.data_publish_thread = threading.Thread(target=self.publish_data_task) 
        # self.data_publish_thread.daemon = True
        self.data_publish_interval = 0.1  # 每秒發送一次數據

        # 啟動MQTT連接
        try:
            self.client.connect(self.broker, self.port, 60)
            print(f"已連接到MQTT代理: {broker}:{port}")
            
            # 為不同主題設置專用回調函數
            for motor_id in [0, 1]:  # 對應相機ID 1和2
                # 設置每個命令的回調函數
                self.client.message_callback_add(f"motor/{motor_id}/cmd/goAbsPos", self.on_go_abs_pos)
                self.client.message_callback_add(f"motor/{motor_id}/cmd/goIncPos", self.on_go_inc_pos)
                self.client.message_callback_add(f"motor/{motor_id}/cmd/goHomePos", self.on_go_home_pos)
                self.client.message_callback_add(f"motor/{motor_id}/cmd/stop", self.on_stop)
                            
            # 啟動MQTT背景處理執行緒
            self.client.loop_start()
            
            self.data_publish_thread.start()
            
        except Exception as e:
            print(f"MQTT連接失敗: {e}")
            self.running = False
    
    def on_connect(self, client, userdata, flags, rc):
        """MQTT連接回調函數"""
        if rc == 0:
            print("成功連接到MQTT代理")
            for motor_id in [0, 1]:  # 對應相機ID 1和2
                self.client.subscribe(f"motor/{motor_id}/cmd/goAbsPos")
                self.client.subscribe(f"motor/{motor_id}/cmd/goIncPos")
                self.client.subscribe(f"motor/{motor_id}/cmd/goHomePos")
                self.client.subscribe(f"motor/{motor_id}/cmd/stop")
        else:
            print(f"連接失敗，返回碼: {rc}")
            self.client.reconnect()
    
    def on_disconnect(self, client, userdata, rc):
        """MQTT斷開連接回調函數"""
        if rc != 0:
            print(f"意外斷開連接，返回碼: {rc}")
    
    def on_go_abs_pos(self, client, userdata, msg):
        """處理goAbsPos命令的回調函數"""
        try:
            # 從主題中提取電機ID
            topic_parts = msg.topic.split('/')
            if len(topic_parts) < 4:
                return
            
            motor_id = int(topic_parts[1])
            camera_id = motor_id + 1  # 相機ID = 電機ID + 1
            
            # 獲取角度參數
            angle = float(msg.payload.decode())
            
            # 找到對應的相機
            camera = next((c for c in self.cameras if c.id == camera_id), None)
            if camera:
                print(f"相機 {camera_id} 旋轉到 {angle} 度")
                camera.rotate_to_angle(angle)
                camera.rotation_speed = 90  # 可調整速度
        except Exception as e:
            print(f"處理goAbsPos命令時出錯: {e}")
    
    def on_go_inc_pos(self, client, userdata, msg):
        """處理goIncPos命令的回調函數"""
        try:
            # 從主題中提取電機ID
            topic_parts = msg.topic.split('/')
            if len(topic_parts) < 4:
                return
            
            motor_id = int(topic_parts[1])
            camera_id = motor_id + 1
            
            # 獲取增量角度參數
            inc_angle = float(msg.payload.decode())
            
            # 找到對應的相機
            camera = next((c for c in self.cameras if c.id == camera_id), None)
            if camera:
                print(f"相機 {camera_id} 增量旋轉 {inc_angle} 度")
                target_angle = (camera.rotation_angle + inc_angle) % 360
                camera.rotate_to_angle(target_angle)
                camera.rotation_speed = 90
        except Exception as e:
            print(f"處理goIncPos命令時出錯: {e}")
    
    def on_go_home_pos(self, client, userdata, msg):
        """處理goHomePos命令的回調函數"""
        try:
            # 從主題中提取電機ID
            topic_parts = msg.topic.split('/')
            if len(topic_parts) < 4:
                return
            
            motor_id = int(topic_parts[1])
            camera_id = motor_id + 1
            homePoint = float(msg.payload.decode())
            
            # 找到對應的相機
            camera = next((c for c in self.cameras if c.id == camera_id), None)
            if camera:
                print(f"相機 {camera_id} 返回原點")
                camera.rotate_to_angle(homePoint)  # 假設原點為0度
                if homePoint < 180:
                    camera.rotation_speed = 90
                else:
                    camera.rotation_speed = -90
                    
        except Exception as e:
            print(f"處理goHomePos命令時出錯: {e}")
    
    def on_stop(self, client, userdata, msg):
        """處理stop命令的回調函數"""
        try:
            # 從主題中提取電機ID
            topic_parts = msg.topic.split('/')
            if len(topic_parts) < 4:
                return
            
            motor_id = int(topic_parts[1])
            camera_id = motor_id + 1
            
            # 找到對應的相機
            camera = next((c for c in self.cameras if c.id == camera_id), None)
            if camera:
                print(f"相機 {camera_id} 停止")
                camera.state = CameraState.IDLE
                camera.rotation_speed = 0
        except Exception as e:
            print(f"處理stop命令時出錯: {e}")

    def run(self):
        last_time = pygame.time.get_ticks() / 1000.0
        while self.running:
            current_time = pygame.time.get_ticks() / 1000.0
            dt = current_time - last_time
            last_time = current_time

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        for camera in self.cameras:
                            if camera.is_clicked(event.pos):
                                self.dragging_camera = camera
                                camera.state = CameraState.DRAGGING
                                break
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1 and self.dragging_camera:
                        self.dragging_camera.state = CameraState.IDLE
                        self.dragging_camera = None
                elif event.type == pygame.MOUSEMOTION:
                    if self.dragging_camera:
                        self.dragging_camera.x = event.pos[0]
                        self.dragging_camera.y = event.pos[1]

            for i, camera in enumerate(self.cameras):
                other_camera = self.cameras[1 - i]
                camera.update(dt, other_camera)

            self.screen.fill((255, 255, 255))
            pygame.draw.circle(self.screen, (150, 150, 150), (self.base_x, self.base_y), self.base_radius)
            for camera in self.cameras:
                camera.draw(self.screen)
            pygame.display.flip()
            self.clock.tick(60)

    def cleanup(self):
        """清理資源"""
        self.running = False
        # 等待數據發布線程結束
        if self.data_publish_thread.is_alive():
            self.data_publish_thread.join()
        # 停止MQTT客戶端
        if hasattr(self, 'client'):
            self.client.loop_stop()
            self.client.disconnect()
        
        # 關閉pygame
        pygame.quit()

    def publish_data_task(self):
        import time
        while self.running:
            self.client.publish('motor/0/angle', str(self.cameras[0].rotation_angle))
            self.client.publish('motor/1/angle', str(self.cameras[1].rotation_angle))
            self.client.publish('motor/0/speed', str(self.cameras[0].rotation_speed))
            self.client.publish('motor/1/speed', str(self.cameras[1].rotation_speed))
            
            time.sleep(self.data_publish_interval)

if __name__ == "__main__":
    # 可以通過命令行參數或配置文件設置MQTT代理
    
    # client = mqtt.Client()
    # try:
    #     client.connect("localhost", 11883, 60)
    # except Exception as e:
    #     print(f"連接失敗: {e}")
    #     exit(1)
    # print("連接成功")
    # client.loop_forever()
    
    
    system = CameraSystem(broker="localhost", port=11883)
    try:
        system.run()
    finally:
        system.cleanup()
