import pygame
from settings import UITheme

class Button:
    def __init__(self, x, y, w, h, text, color):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.color = color
        self.is_hovered = False

    def draw(self, surface, font):
        draw_color = self.color if not self.is_hovered else (min(self.color[0]+40, 255), min(self.color[1]+40, 255), min(self.color[2]+40, 255))
        pygame.draw.rect(surface, UITheme.PANEL_GREY, self.rect)
        pygame.draw.rect(surface, draw_color, self.rect, 2)
        
        txt_surf = font.render(self.text, True, UITheme.TEXT_OFF_WHITE)
        surface.blit(txt_surf, (self.rect.x + (self.rect.w - txt_surf.get_width())//2, self.rect.y + (self.rect.h - txt_surf.get_height())//2))

    def check_hover(self, mouse_pos):
        self.is_hovered = self.rect.collidepoint(mouse_pos)
        return self.is_hovered

def draw_loading_overlay(surface, font):
    """Draws a semi-transparent 'Processing' screen."""
    overlay = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.fill((10, 10, 12, 200)) # Dark transparent
    
    # Pulsing text logic could go here, but let's keep it simple
    msg = font.render(">> EXECUTING_ANALYSIS_PROTOCOL...", True, UITheme.ACCENT_ORANGE)
    surface.blit(overlay, (0,0))
    surface.blit(msg, (1280//2 - msg.get_width()//2, 720//2))
    
def draw_metadata_panel(surface, experiment_data):
    """Draws the [i] Information panel on the right."""
    panel_rect = pygame.Rect(850, 450, 380, 200)
    pygame.draw.rect(surface, (30, 30, 40), panel_rect)
    
    # Content
    notes = experiment_data.get('notes', 'No notes added...')
    temp = experiment_data.get('temperature', 'N/A')
    sid = experiment_data.get('sample_id', 'Unknown')

class TextInput:
    def __init__(self, x, y, w, h, label="", secret=False):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label
        self.text = ""
        self.active = False
        self.secret = secret
        self.font = pygame.font.SysFont("Consolas", 16)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        
        if self.active and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                self.active = False
            else:
                if event.unicode.isprintable():
                    self.text += event.unicode

    def draw(self, surface):
        color = UITheme.ACCENT_ORANGE if self.active else (100, 100, 110)
        pygame.draw.rect(surface, (10, 10, 15), self.rect)
        pygame.draw.rect(surface, color, self.rect, 1)
        
        # Label
        lbl = self.font.render(self.label, True, UITheme.TEXT_DIM)
        surface.blit(lbl, (self.rect.x, self.rect.y - 20))
        
        # Text
        display_text = "*" * len(self.text) if self.secret else self.text
        if self.active and pygame.time.get_ticks() % 1000 < 500:
            display_text += "|"
            
        txt_surf = self.font.render(display_text, True, (255, 255, 255))
        surface.blit(txt_surf, (self.rect.x + 10, self.rect.y + (self.rect.h - txt_surf.get_height())//2))