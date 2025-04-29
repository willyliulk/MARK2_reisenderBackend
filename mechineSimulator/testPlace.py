import pygame
import sys
import os
import math
import threading
import pynng
import json
from enum import Enum

# 定義相機狀態枚舉
class CameraState(Enum):
    IDLE = 0
    DRAGGING = 1
    ROTATING_TO_ANGLE = 2
    ROTATING = 3

class Camera:
    def __init__(self, x, y, radius=20, color=(255, 0, 0), id=0):
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color
        self.id = id
        self.state = CameraState.IDLE
        self.target_x = x
        self.target_y = y
        self.rotation_speed = 0  # 角度/秒
        self.rotation_angle = 0  # 當前角度
        self.center_x = 0  # 基座中心 x 座標
        self.center_y = 0  # 基座中心 y 座標
        self.distance_from_center = 0  # 距離基座中心的距離
        
        resPath = os.path.join(os.path.dirname(__file__), 'res/camera.png')
        self.image_orig = pygame.image.load(resPath)
        self.image_orig = pygame.transform.scale(self.image_orig, (radius*2, radius*2))
        self.imageRect = self.image_orig.get_rect()
        
    def update_center(self, center_x, center_y):
        """更新基座中心座標"""
        self.center_x = center_x
        self.center_y = center_y
        # 計算與中心的距離
        self.distance_from_center = math.sqrt((self.x - center_x)**2 + (self.y - center_y)**2)
        # 計算當前角度
        self.rotation_angle = math.atan2(self.y - center_y, self.x - center_x)
        
    def draw(self, screen:pygame.Surface):
        # 繪製相機
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius, 2)
        
        # 繪製指向基座中心的線
        pygame.draw.line(screen, self.color, (int(self.x), int(self.y)), 
                        (int(self.center_x), int(self.center_y)), 2)
        
        # 繪製相機ID
        font = pygame.font.SysFont(None, 24)
        id_text = font.render(str(self.id), True, (255, 255, 255))
        screen.blit(id_text, (int(self.x - 5), int(self.y - 10)))

        # 繪製相機圖片
        screen.blit(self.image, self.imageRect)
        # pygame.draw.rect(screen, (0, 0, 0), self.imageRect, 1)
        
    def is_clicked(self, pos):
        """檢查滑鼠點擊是否在相機上"""
        dx = pos[0] - self.x
        dy = pos[1] - self.y
        return dx*dx + dy*dy <= self.radius*self.radius
        
    def rotate_to_angle(self, angle):
        """設置旋轉到指定角度"""
        self.rotation_angle = angle
        self.state = CameraState.ROTATING_TO_ANGLE
        
    def set_rotation(self, speed):
        """設置旋轉速度（角度/秒）"""
        self.rotation_speed = speed
        if speed != 0:
            self.state = CameraState.ROTATING
        else:
            self.state = CameraState.IDLE
            
    def update(self, dt, other_camera=None):
        """更新相機狀態"""
        if self.state == CameraState.ROTATING_TO_ANGLE:
            # 旋轉到指定角度
            angle_diff = self.rotation_angle - self.rotation_speed * dt
            if abs(angle_diff) < abs(self.rotation_speed * dt):
                # 到達指定角度，停止旋轉
                self.rotation_angle = angle_diff
                self.state = CameraState.IDLE
            else:
                # 未到達指定角度，繼續旋轉
                self.rotation_angle = angle_diff
                
            # 計算新位置
            new_x = self.center_x + math.cos(self.rotation_angle) * self.distance_from_center
            new_y = self.center_y + math.sin(self.rotation_angle) * self.distance_from_center
            
            # 檢查是否會與另一個相機碰撞
            if other_camera:
                dx = new_x - other_camera.x
                dy = new_y - other_camera.y
                distance = math.sqrt(dx*dx + dy*dy)
                
                if distance < self.radius + other_camera.radius:
                    # 碰撞，停止旋轉
                    self.rotation_speed = 0
                    self.state = CameraState.IDLE
                    return
                    
            # 更新位置
            self.x = new_x
            self.y = new_y

        elif self.state == CameraState.ROTATING:
            # 以固定角速度旋轉
            self.rotation_angle += self.rotation_speed * dt
            
            # 計算新位置
            new_x = self.center_x + math.cos(self.rotation_angle) * self.distance_from_center
            new_y = self.center_y + math.sin(self.rotation_angle) * self.distance_from_center
            
            # 檢查是否會與另一個相機碰撞
            if other_camera:
                dx = new_x - other_camera.x
                dy = new_y - other_camera.y
                distance = math.sqrt(dx*dx + dy*dy)
                
                if distance < self.radius + other_camera.radius:
                    # 碰撞，停止旋轉
                    self.rotation_speed = 0
                    self.state = CameraState.IDLE
                    return
                    
            # 更新位置
            self.x = new_x
            self.y = new_y
            
        # 更新與中心的距離
        self.distance_from_center = math.sqrt((self.x - self.center_x)**2 + (self.y - self.center_y)**2)
        # 更新與中心的角度
        self.rotation_angle = math.atan2(self.y - self.center_y, self.x - self.center_x)
        # 更新相機圖片角度
        self.image = pygame.transform.rotate(self.image_orig, -math.degrees(self.rotation_angle)+90)
        # 更新相機圖片位置
        self.imageRect = self.image.get_rect()
        self.imageRect.center = (self.x, self.y)

class CameraSystem:
    def __init__(self):
        pygame.init()
        self.width, self.height = 800, 600
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("相機基座控制系統")
        
        # 基座
        self.base_x = self.width // 2
        self.base_y = self.height // 2
        self.base_radius = 50
        
        # 創建兩個相機
        self.cameras = [
            Camera(self.base_x - 150, self.base_y, color=(255, 0, 0), id=1),
            Camera(self.base_x + 150, self.base_y, color=(0, 0, 255), id=2)
        ]
        
        # 更新相機的基座中心
        for camera in self.cameras:
            camera.update_center(self.base_x, self.base_y)
            
        self.dragging_camera = None
        self.clock = pygame.time.Clock()
        
        # 創建通訊線程
        self.running = True
        self.comm_thread = threading.Thread(target=self.communication_thread)
        self.comm_thread.daemon = True
        self.comm_thread.start()
        
    def communication_thread(self):
        """通訊線程，使用pynng接收外部指令"""
        try:
            with pynng.Rep0(listen="tcp://127.0.0.1:5555", recv_timeout=100) as rep:
                print("通訊服務已啟動，監聽 tcp://127.0.0.1:5555")
                
                while self.running:
                    try:
                        # 接收消息，設置超時以便能夠正常退出
                        msg = rep.recv()
                        
                        try:
                            # 解析JSON指令
                            command = json.loads(msg.decode('utf-8'))
                            response = self.process_command(command)
                            
                            # 回應
                            rep.send(json.dumps(response).encode('utf-8'))
                        except json.JSONDecodeError:
                            rep.send(json.dumps({"status": "error", "message": "Invalid JSON"}).encode('utf-8'))
                    except pynng.exceptions.Timeout:
                        # 超時，繼續循環
                        continue
        except Exception as e:
            print(f"通訊線程錯誤: {e}")
            
    def process_command(self, command):
        """處理接收到的指令"""
        try:
            cmd_type = command.get("type")
            camera_id = command.get("camera_id")
            
            # 檢查相機ID是否有效
            camera = None
            for cam in self.cameras:
                if cam.id == camera_id:
                    camera = cam
                    break
                    
            if not camera:
                return {"status": "error", "message": f"Camera ID {camera_id} not found"}
                
            if cmd_type == "rotate_to":
                # 移動到指定位置
                angle = command.get("angle")  # 角度
                camera.rotate_to_angle(angle=angle)
                return {"status": "ok", "message": f"Camera {camera_id} rotating to {angle} degrees"}
                
            elif cmd_type == "rotate":
                # 設置旋轉速度
                speed = command.get("speed")  # 角度/秒
                camera.set_rotation(speed)
                return {"status": "ok", "message": f"Camera {camera_id} rotating at {speed} rad/s"}
                
            elif cmd_type == "stop":
                # 停止相機
                camera.state = CameraState.IDLE
                camera.rotation_speed = 0
                return {"status": "ok", "message": f"Camera {camera_id} stopped"}
                
            else:
                return {"status": "error", "message": f"Unknown command type: {cmd_type}"}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}
            
    def run(self):
        """主循環"""
        last_time = pygame.time.get_ticks() / 1000.0
        
        while self.running:
            # 計算時間增量
            current_time = pygame.time.get_ticks() / 1000.0
            dt = current_time - last_time
            last_time = current_time
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # 左鍵
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
                        
            # 更新相機
            for i, camera in enumerate(self.cameras):
                other_camera = self.cameras[1 - i]  # 獲取另一個相機
                camera.update(dt, other_camera)
                
            # 繪製
            self.screen.fill((255, 255, 255))
            
            # 繪製基座
            pygame.draw.circle(self.screen, (150, 150, 150), (self.base_x, self.base_y), self.base_radius)
            
            # 繪製相機
            for camera in self.cameras:
                camera.draw(self.screen)
                
            pygame.display.flip()
            self.clock.tick(60)
            
    def cleanup(self):
        """清理資源"""
        pygame.quit()

if __name__ == "__main__":
    system = CameraSystem()
    try:
        system.run()
    finally:
        system.cleanup()