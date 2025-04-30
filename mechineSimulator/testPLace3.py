import pygame
import sys
import os
import math
import threading
import asyncio
import pynng
import json
from enum import Enum

class CameraState(Enum):
    IDLE = 0
    DRAGGING = 1
    ROTATING_TO_ANGLE = 2
    ROTATING = 3

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
                self.state = CameraState.IDLE
                return

        self.x = new_x
        self.y = new_y

        # 更新圖片角度和位置
        self.image = pygame.transform.rotate(self.image_orig, -self.rotation_angle + 90)
        self.imageRect = self.image.get_rect()
        self.imageRect.center = (self.x, self.y)

class CameraSystem:
    def __init__(self):
        pygame.init()
        self.width, self.height = 800, 600
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("相機基座控制系統")

        self.base_x = self.width // 2
        self.base_y = self.height // 2
        self.base_radius = 50

        # 角度上下限設定（可自訂）
        angle_limit_cam1 = (0, 360)  # 可修改為其他範圍
        angle_limit_cam2 = (0, 360)

        self.cameras = [
            Camera(self.base_x - 150, self.base_y, color=(255, 0, 0), id=1, angle_limit=angle_limit_cam1),
            Camera(self.base_x + 150, self.base_y, color=(0, 0, 255), id=2, angle_limit=angle_limit_cam2)
        ]

        for camera in self.cameras:
            camera.update_center(self.base_x, self.base_y)

        self.dragging_camera = None
        self.clock = pygame.time.Clock()

        # 建立事件循環與async task
        self.loop = asyncio.new_event_loop()
        self.running = True

        # 改為訂閱模式的pynng socket
        self.sub = pynng.Sub0()
        self.sub.listen("tcp://127.0.0.1:5555")  # 連接到發佈端
        # 訂閱兩個鏡頭相關主題，根據MotorManager_v2格式
        
        topicList:list[str] = []
        for id in [0, 1]:
            topicList.append(f"motor|{id}|goAbsPos".encode())
            topicList.append(f"motor|{id}|goIncPos".encode())
            topicList.append(f"motor|{id}|goHomePos".encode())            
            topicList.append(f"motor|{id}|stop".encode())
        
        for topic in topicList:
            self.sub.subscribe(topic)
            

        # 啟動非同步接收任務
        self.recv_task = self.loop.create_task(self.receive_messages())
    
    async def receive_messages(self):
        while self.running:
            try:
                msg = await self.sub.arecv()
                msg_str = msg.decode()
                # 範例訊息格式: motor|1|goAbsPos:90
                # 解析主題與指令
                parts = msg_str.split('|')
                if len(parts) < 3:
                    continue
                prefix, cam_id_str, cmd_with_param = parts[0], parts[1], parts[2]
                if prefix != 'motor':
                    continue
                try:
                    cam_id = int(cam_id_str) + 1
                except:
                    continue
                camera = next((c for c in self.cameras if c.id == cam_id), None)
                if not camera:
                    continue

                # cmd_with_param 可能是 "goAbsPos:90" 或 "stop:"
                if ':' in cmd_with_param:
                    cmd, param = cmd_with_param.split(':', 1)
                else:
                    cmd, param = cmd_with_param, ''

                if cmd == "goAbsPos":
                    try:
                        angle = float(param)
                        camera.rotate_to_angle(angle)
                        camera.rotation_speed = 90  # 可調整速度
                    except:
                        pass
                elif cmd == "stop":
                    camera.state = CameraState.IDLE
                    camera.rotation_speed = 0

                # 可擴展其他指令...

            except Exception as e:
                print(f"接收錯誤: {e}")
                await asyncio.sleep(0.1)


    def communication_thread(self):
        try:
            with pynng.Sub0(listen="tcp://127.0.0.1:5555", recv_timeout=100) as sub:
                sub.subscribe("")
                print("通訊服務已啟動，監聽 tcp://127.0.0.1:5555")
                while self.running:
                    try:
                        msg = sub.recv()
                        command = json.loads(msg.decode('utf-8'))
                        response = self.process_command(command)
                        sub.send(json.dumps(response).encode('utf-8'))
                    except pynng.exceptions.Timeout:
                        continue
                    except json.JSONDecodeError:
                        sub.send(json.dumps({"status": "error", "message": "Invalid JSON"}).encode('utf-8'))
        except Exception as e:
            print(f"通訊線程錯誤: {e}")

    def process_command(self, command):
        try:
            cmd_type = command.get("type")
            camera_id = command.get("camera_id")

            camera = next((c for c in self.cameras if c.id == camera_id), None)
            if not camera:
                return {"status": "error", "message": f"Camera ID {camera_id} not found"}

            if cmd_type == "goAbsPos":  # 對應MotorManager_v2 goAbsPos指令
                angle = command.get("pos")
                if angle is None:
                    return {"status": "error", "message": "Missing 'pos' parameter"}
                camera.rotate_to_angle(angle)
                # 設定旋轉速度可依需求調整，這裡給一個預設值
                camera.rotation_speed = 90  # 90度/秒
                return {"status": "ok", "message": f"Camera {camera_id} rotating to {angle} degrees"}

            elif cmd_type == "stop":
                camera.state = CameraState.IDLE
                camera.rotation_speed = 0
                return {"status": "ok", "message": f"Camera {camera_id} stopped"}

            else:
                return {"status": "error", "message": f"Unknown command type: {cmd_type}"}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def run(self):
        # 啟動asyncio事件循環與pygame主迴圈並行
        import threading

        def loop_in_thread(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        t = threading.Thread(target=loop_in_thread, args=(self.loop,), daemon=True)
        t.start()

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

        # 停止非同步任務與事件循環
        self.running = False
        self.loop.call_soon_threadsafe(self.loop.stop)
        t.join()

    def cleanup(self):
        pygame.quit()

    def cleanup(self):
        pygame.quit()

if __name__ == "__main__":
    system = CameraSystem()
    try:
        system.run()
    finally:
        system.cleanup()
