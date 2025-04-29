import pygame
from pygame import Rect

class MechineBase:
    def __init__(self, pygameObj, x, y, width, height):
        self.rect = pygame.Rect(x, y, width, height)
        self.center_x = x + width / 2
        self.center_y = y + height / 2
        self.width = width
        self.height = height
        self.pygameObj = pygameObj
        
        self.mechineColor = (0, 162, 230)
        self.baseBox = Rect(330, 20, 50, 80)
        self.mainPlate = {'center':(360, 300), 'radius':220}
        
        
    def draw(self, surface: pygame.Surface):
        pygame.draw.rect(surface, self.mechineColor, self.baseBox)
        pygame.draw.circle(surface, self.mechineColor, self.mainPlate['center'], self.mainPlate['radius'])
        
        
if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((700, 600))
    clock = pygame.time.Clock()
    
    mechine = MechineBase(pygame, 100, 100, 50, 50)
    
    clock = pygame.time.Clock()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    running = False
        
        screen.fill((255, 255, 255))
        mechine.draw(screen)
        pygame.display.flip()
        clock.tick(60)
        
    pygame.quit()