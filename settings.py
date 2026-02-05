import pygame

class UITheme:
    # Color Palette - Industrial / Terminal Aesthetic
    BG_DARK = (10, 10, 12)
    BG_LOGIN = (0, 43, 100)
    PANEL_GREY = (22, 22, 26)
    ACCENT_ORANGE = (255, 120, 0)
    TEXT_OFF_WHITE = (210, 210, 215)
    TEXT_DIM = (120, 120, 130)
    GRID_COLOR = (28, 28, 32)
    NODE_MAIN = (0, 180, 255)
    NODE_BRANCH = (0, 255, 150)
    LOGO_CYAN = (0, 212, 255)

    @staticmethod
    def draw_bracket(surface, rect, color, length=12, thickness=2):
        """Draws sharp industrial corner brackets around a rect."""
        x, y, w, h = rect
        # Top Left
        pygame.draw.lines(surface, color, False, [(x, y + length), (x, y), (x + length, y)], thickness)
        # Top Right
        pygame.draw.lines(surface, color, False, [(x + w - length, y), (x + w, y), (x + w, y + length)], thickness)
        # Bottom Left
        pygame.draw.lines(surface, color, False, [(x, y + h - length), (x, y + h), (x + length, y + h)], thickness)
        # Bottom Right
        pygame.draw.lines(surface, color, False, [(x + w - length, y + h), (x + w, y + h), (x + w, y + h - length)], thickness)

    @staticmethod
    def draw_grid(surface):
        """Draws the background industrial grid."""
        width, height = surface.get_size()
        for x in range(0, width, 40):
            pygame.draw.line(surface, UITheme.GRID_COLOR, (x, 0), (x, height))
        for y in range(0, height, 40):
            pygame.draw.line(surface, UITheme.GRID_COLOR, (0, y), (width, height))

    @staticmethod
    def render_terminal_text(surface, text, pos, font, color, width_limit=400):
        """Helper to wrap text for the side panels."""
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            current_line.append(word)
            test_line = " ".join(current_line)
            if font.size(test_line)[0] > width_limit:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]
        lines.append(" ".join(current_line))

        y_offset = 0
        for line in lines:
            text_surf = font.render(line, True, color)
            surface.blit(text_surf, (pos[0], pos[1] + y_offset))
            y_offset += font.get_linesize()
        return y_offset
    
    @staticmethod
    def draw_orange_streaks(surface, frame_count):
        """Draws moving high-tech scanning lines."""
        width, height = surface.get_size()
        # A slow moving horizontal scan line
        y_pos = (frame_count * 2) % height
        pygame.draw.line(surface, (100, 50, 0), (0, y_pos), (width, y_pos), 1)
        # Static decorative streaks
        pygame.draw.line(surface, UITheme.ACCENT_ORANGE, (20, 0), (20, height), 1)
        pygame.draw.line(surface, UITheme.ACCENT_ORANGE, (width-20, 0), (width-20, height), 1)

    @staticmethod
    def draw_glass_panel(surface, rect, color=(30, 30, 35, 180)):
        """Draws a semi-transparent 'Glass' panel with the signature brackets."""
        shape_surf = pygame.Surface(pygame.Rect(rect).size, pygame.SRCALPHA)
        pygame.draw.rect(shape_surf, color, shape_surf.get_rect(), border_radius=4)
        surface.blit(shape_surf, rect[:2])
        UITheme.draw_bracket(surface, rect, UITheme.ACCENT_ORANGE)

    @staticmethod
    def draw_scanning_lines(surface, frame_count):
        """Draws moving high-tech scanning lines for the login screen."""
        width, height = surface.get_size()
        # A slow moving horizontal scan line
        y_pos = (frame_count * 2) % height
        
        # Create a faint glow effect
        scan_surf = pygame.Surface((width, 2), pygame.SRCALPHA)
        scan_surf.fill((255, 120, 0, 100)) # Transparent orange
        surface.blit(scan_surf, (0, y_pos))
        
        # Static side streaks (The orange lines you liked)
        pygame.draw.line(surface, (255, 120, 0), (20, 0), (20, height), 1)
        pygame.draw.line(surface, (255, 120, 0), (width-20, 0), (width-20, height), 1)