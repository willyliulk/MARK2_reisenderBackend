import pygame
import sys
import math

from models.mechineBase import MechineBase

# 初始化 Pygame
pygame.init()

# 設定視窗
WIDTH, HEIGHT = 700, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("物件拖拽模擬器")

# 顏色定義
WHITE = (255, 255, 255)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GREEN = (0, 255, 0)
BLACK = (0, 0, 0)

# 圓形軌道參數
CIRCLE_CENTER = (WIDTH // 2, HEIGHT // 2)
CIRCLE_RADIUS = 150
ORBIT_COLOR = (200, 200, 200)

# 物件類別 - 自由移動
class FreeObject:
    def __init__(self, x, y, width, height, color):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.dragging = False
        self.offset_x = 0
        self.offset_y = 0
        
    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect)
        pygame.draw.rect(surface, BLACK, self.rect, 2)  # 邊框
        
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # 左鍵
                if self.rect.collidepoint(event.pos):
                    self.dragging = True
                    self.offset_x = self.rect.x - event.pos[0]
                    self.offset_y = self.rect.y - event.pos[1]
                    return True
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.dragging = False
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                self.rect.x = event.pos[0] + self.offset_x
                self.rect.y = event.pos[1] + self.offset_y
                return True
        return False

# 物件類別 - 圓周移動
class CircularObject:
    def __init__(self, center, radius, angle, size, color):
        self.center = center  # 圓心
        self.radius = radius  # 軌道半徑
        self.angle = angle    # 角度 (弧度)
        self.size = size      # 物件大小
        self.color = color
        self.dragging = False
        
        # 計算初始位置
        self.x = self.center[0] + self.radius * math.cos(self.angle)
        self.y = self.center[1] + self.radius * math.sin(self.angle)
        self.rect = pygame.Rect(self.x - self.size//2, self.y - self.size//2, self.size, self.size)
        
    def draw(self, surface):
        # 更新位置
        self.x = self.center[0] + self.radius * math.cos(self.angle)
        self.y = self.center[1] + self.radius * math.sin(self.angle)
        self.rect = pygame.Rect(self.x - self.size//2, self.y - self.size//2, self.size, self.size)
        
        # 繪製物件
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.size//2)
        pygame.draw.circle(surface, BLACK, (int(self.x), int(self.y)), self.size//2, 2)  # 邊框
        
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # 左鍵
                mouse_x, mouse_y = event.pos
                # 檢查是否點擊到物件
                distance = math.sqrt((mouse_x - self.x) ** 2 + (mouse_y - self.y) ** 2)
                if distance <= self.size // 2:
                    self.dragging = True
                    return True
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.dragging = False
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                mouse_x, mouse_y = event.pos
                # 計算滑鼠位置相對於圓心的角度
                dx = mouse_x - self.center[0]
                dy = mouse_y - self.center[1]
                self.angle = math.atan2(dy, dx)
                return True
        return False

# 創建物件
free_objects = [
    FreeObject(100, 100, 50, 50, RED),
    FreeObject(200, 200, 70, 50, GREEN)
]

circular_objects = [
    CircularObject(CIRCLE_CENTER, CIRCLE_RADIUS, 0, 40, BLUE),
    CircularObject(CIRCLE_CENTER, CIRCLE_RADIUS, math.pi/2, 40, (255, 165, 0))  # 橙色
]

base_mechine = MechineBase(pygame, 0, 0, WIDTH, HEIGHT)

# 主遊戲迴圈
clock = pygame.time.Clock()
running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            
        # 處理物件事件
        handled = False
        for obj in free_objects:
            if obj.handle_event(event):
                handled = True
                break
                
        if not handled:
            for obj in circular_objects:
                if obj.handle_event(event):
                    break
    
    # 清空畫面
    screen.fill(WHITE)
    
    # 繪製圓形軌道
    pygame.draw.circle(screen, ORBIT_COLOR, CIRCLE_CENTER, CIRCLE_RADIUS, 2)
    
    # 繪製物件
    for obj in free_objects:
        obj.draw(screen)
        
    for obj in circular_objects:
        obj.draw(screen)
    
    base_mechine.draw(screen)
    
    # 更新畫面
    pygame.display.flip()
    clock.tick(60)  # 限制幀率為 60 FPS

# 退出 Pygame
pygame.quit()
sys.exit()
