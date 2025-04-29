import os
import math
from dataclasses import dataclass
from enum import Enum

import pygame

@dataclass
class CameraMotionConfig:
    angle_speed_max = 10  # deg/s
    angle_accel     = 2   # deg/s^2
    angle_daccel    = 2   # deg/s^2
    

class CameraState(Enum):
    IDLE        = 0
    ROTATING    = 1
    ERROR       = 2
    ROTOATE_TO  = 3
    

class MechineCamera_v2:
    def __init__(self, radius, motion_center, motion_radius, offsetAngle,
                 motion_config: CameraMotionConfig, 
                 id=0, clock: pygame.time.Clock=None):
        self.id = id
        self.radius = radius
        self.motion_center = motion_center
        self.motion_radius = motion_radius
        self.offsetAngle = offsetAngle
        self.motion_config = motion_config
        self.clock = clock
        
        self.state = CameraState.IDLE
        self.angle = 0
        self.angle_speed = 0
        self.target_angel = 0
        
        self.update()
        
    def update(self):
        if self.state == CameraState.ERROR:
            self.__lastActive = pygame.time.get_ticks()
            if(pygame.time.get_ticks() - self.__lastActive) > 3000:
                print("Camera Error!!!")
                
            return
        
        if self.state == CameraState.ROTATING:
            self.angle += self.angle_speed * self.clock.get_time() / 1000.0
            self.angle_speed += self.motion_config.angle_speed_max / self.motion_config.angle_accel_time * self.clock.get_time() / 1000.0
            if abs(self.angle_speed) > self.motion_config.angle_speed_max:
                self.angle_speed = self.motion_config.angle_speed_max * math.copysign(1, self.angle_speed)
            print(
                self.motion_config.angle_speed_max,
                self.angle_speed,
                abs(self.angle_speed) > self.motion_config.angle_speed_max,
                self.motion_config.angle_speed_max / self.motion_config.angle_accel_time * self.clock.get_time() / 1000.0
                  )
            
            if self.angle > 360:
                self.angle = 0
            elif self.angle < 0:
                self.angle = 360
                
        if self.state == CameraState.ROTOATE_TO:
            dt = self.clock.get_time() / 1000.0
            angle_error = self.target_angle - self.angle
            self.angle += self.angle_speed * dt
            # ang_speed = self.motion_config.angle_speed_max / self.motion_config.angle_accel_time * self.clock.get_time() / 1000.0
            
            v_decel = math.sqrt(2 * self.motion_config.angle_daccel * angle_error)
            v_accel = self.angle_speed + self.motion_config.angle_accel * dt
            ang_speed = min(
                    self.motion_config.angle_speed_max,
                    v_decel,
                    v_accel
                            )
            
            self.angle_speed = math.copysign(ang_speed, self.target_angle - self.angle)
            
            
            if abs(self.angle_speed) > self.motion_config.angle_speed_max:
                self.angle_speed =  math.copysign(self.motion_config.angle_speed_max,  self.angle_speed)
                
            if abs(self.angle - self.target_angle) < 0.2:
                self.angle_speed = 0
                self.state = CameraState.IDLE
                self.angle = self.target_angle
            elif self.angle > 360:
                self.angle = 0
            elif self.angle < 0:
                self.angle = 360
            
                
        self.x = self.motion_center[0] + self.motion_radius * math.cos(math.radians(self.angle + self.offsetAngle))
        self.y = self.motion_center[1] + self.motion_radius * math.sin(math.radians(self.angle + self.offsetAngle))
        
    def rotate_to(self, target_angle):
        if self.state == CameraState.ERROR:
            return
        
        self.state = CameraState.ROTOATE_TO
        self.target_angle = target_angle % 360
        
    def stop(self):
        if self.state == CameraState.ERROR:
            return
        
        self.angle_speed = 0
        self.state = CameraState.IDLE
        
    def resolve_error(self):
        print("ERROR Resolved ~~~")
        self.state = CameraState.IDLE
        self.angle_speed = 0
    
    def draw(self, screen):
        pygame.draw.circle(screen, (255, 0, 0), (self.x, self.y), 5)
        pygame.draw.circle(screen, (0, 255, 0), self.motion_center, self.motion_radius)
        
        # draw angle line
        pygame.draw.line(screen, (0, 0, 255), self.motion_center, (self.x, self.y), 2)
        
        # draw angle text
        font = pygame.font.SysFont(None, 30)
        text = font.render(f"{self.id}", True, (255, 255, 255))
        screen.blit(text, (self.x, self.y))
        text = font.render(f"Angle: {self.angle:.2f}", True, (255, 255, 255))
        screen.blit(text, (self.x, self.y+15))
        text = font.render(f"Speed: {self.angle_speed:.2f}", True, (255, 255, 255))
        screen.blit(text, (self.x, self.y+30))
        

        
if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Camera Motion")
    
    clock = pygame.time.Clock() 
    
    # create camera
    camera1 = MechineCamera_v2(100, (400, 300), 200, 0, 
                               CameraMotionConfig(), id=0, clock=clock)
    
    # main loop
    running = True
    tar_ang = 0
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
        
        if pygame.key.get_pressed()[pygame.K_LEFT]:
            tar_ang += 1
            print(tar_ang)
        elif pygame.key.get_pressed()[pygame.K_RIGHT]:
            tar_ang -= 1
            print(tar_ang)
        
        camera1.rotate_to(tar_ang)
            
            
        if pygame.key.get_pressed()[pygame.K_SPACE]:
            camera1.resolve_error()
        
        screen.fill((0, 0, 0))
        
        camera1.update()
        camera1.draw(screen)
        
        pygame.display.flip()
        clock.tick(60)
        
    pygame.quit()
    