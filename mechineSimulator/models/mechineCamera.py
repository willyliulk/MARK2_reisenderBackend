import os
import math

import pygame
from pygame import Rect

class MechineCamera:
    def __init__(self, pygameObj, width, height, motion_center, motion_radius, offsetAngle):
        self.pygameObj = pygameObj
        self.width = width
        self.height = height
        self.motion_center = motion_center
        self.motion_radius = motion_radius
        self.motion_angle = 0
        self.offsetAngle = offsetAngle - 90
        
        self.__angle = self.motion_angle + self.offsetAngle
        self.x = motion_center[0] + motion_radius*math.cos(math.radians(self.__angle))
        self.y = motion_center[1] + motion_radius*math.sin(math.radians(self.__angle))
        self.rect = pygame.Rect(self.x-width/2, self.y-height/2, width, height)
        
        
        resPath = os.path.join(os.path.dirname(__file__), '../res/camera.png')
        print(resPath)
        self.camPic = pygame.image.load(resPath)
        self.camPic = pygame.transform.scale(self.camPic, (width, height))
        self.update_position()
    
    def update_position(self):
        self.__angle = self.motion_angle + self.offsetAngle        
        self.x = self.motion_center[0] + self.motion_radius*math.cos(math.radians(self.__angle))
        self.y = self.motion_center[1] + self.motion_radius*math.sin(math.radians(self.__angle))
        
        angle_to_center = math.atan2(
                self.motion_center[1]-self.y, 
                self.motion_center[0]-self.x
            )
        angle_degrees = math.degrees(angle_to_center)
        self.image = pygame.transform.rotate(self.camPic, -angle_degrees)
        self.rect = self.image.get_rect(center=(self.x, self.y))
        
        
    def draw(self, surface: pygame.Surface):
        self.update_position()
        
        # debug
        pygame.draw.circle(surface, (255, 0, 0), self.motion_center, self.motion_radius, width=3)
        pygame.draw.circle(surface, (0, 0, 255), (self.x, self.y), 10)
        pygame.draw.line(surface, (0, 0, 0), self.motion_center, (self.x, self.y), width=3)
        
        surface.blit(self.image, self.rect)
        

        
        
if __name__ == "__main__":

    pygame.init()
    screen = pygame.display.set_mode((700, 600))
    clock = pygame.time.Clock()
    
    camera = MechineCamera(pygame, 80, 80, (360, 300), 220, 15)
    
    clock = pygame.time.Clock()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    running = False
            if event.type == pygame.MOUSEMOTION:
                camera.motion_angle = math.degrees(math.atan2(event.pos[1]-camera.motion_center[1], event.pos[0]-camera.motion_center[0]))
                camera.motion_angle = camera.motion_angle + 90 - 15
        
        screen.fill((255, 255, 255))
        camera.draw(screen)
        pygame.display.flip()
        clock.tick(60)
        
    pygame.quit()