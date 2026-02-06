import pygame
from settings import UITheme

class VersionTree:
    def __init__(self):
        self.nodes = []  
        self.connections = []
        self.node_radius = 18
        
        # Camera & Navigation
        self.camera_offset = pygame.Vector2(60, 300)
        self.zoom_level = 1.0
        self.is_panning = False
        
        self.selected_node_id = None
        self.font = pygame.font.SysFont("Consolas", 12, bold=True)

    def handle_zoom(self, direction):
        """Adjusts the zoom level within limits."""
        if direction == "in":
            self.zoom_level = min(2.0, self.zoom_level + 0.1)
        else:
            self.zoom_level = max(0.4, self.zoom_level - 0.1)

    def update_tree(self, db_rows):
        """Processes DB rows into a visual map with Auto-Scroll."""
        self.nodes = []
        self.connections = []
        pos_map = {}
        
        branch_slots = {"main": 0}
        next_slot_y = 100 

        for row in db_rows:
            node_id, parent_id, branch, name = row
            
            if parent_id is None or parent_id not in pos_map:
                gen_x = 0
            else:
                gen_x = pos_map[parent_id]['gen'] + 1
            
            if branch not in branch_slots:
                branch_slots[branch] = len(branch_slots) * next_slot_y
            
            y_pos = branch_slots[branch]
            pos = pygame.Vector2(gen_x * 160, y_pos)
            pos_map[node_id] = {'pos': pos, 'gen': gen_x}
            
            self.nodes.append({
                "id": node_id,
                "pos": pos,
                "parent_id": parent_id,
                "name": name,
                "branch": branch
            })
            
            if parent_id in pos_map:
                parent_pos = pos_map[parent_id]['pos']
                self.connections.append((parent_pos, pos))

        # --- AUTO-SCROLL LOGIC ---
        if self.nodes:
            # Find the node with the furthest X (the latest generation)
            max_x = max(n['pos'].x for n in self.nodes)
            # Calculate where that node is with current zoom
            scaled_max_x = max_x * self.zoom_level
            # Set camera so the newest node is roughly 70% across the 800px panel
            # (600 is the focal point inside the 800px panel)
            self.camera_offset.x = 600 - scaled_max_x

    def draw(self, surface, mouse_pos):
        surface.fill((0, 0, 0, 0))

        # 1. Draw Connections (Scale by zoom)
        for start, end in self.connections:
            s = (start * self.zoom_level) + self.camera_offset
            e = (end * self.zoom_level) + self.camera_offset
            
            color = (70, 70, 80)
            mid_x = int(s.x + (e.x - s.x) // 2)
            
            pts = [
                (int(s.x), int(s.y)), 
                (mid_x, int(s.y)), 
                (mid_x, int(e.y)), 
                (int(e.x), int(e.y))
            ]
            pygame.draw.lines(surface, color, False, pts, 2)

        # 2. Draw Nodes (Scale by zoom)
        current_radius = int(self.node_radius * self.zoom_level)
        
        for node in self.nodes:
            draw_pos = (node["pos"] * self.zoom_level) + self.camera_offset
            ix, iy = int(draw_pos.x), int(draw_pos.y)
            
            # Optimization: Don't draw if off-screen
            if not (-100 < ix < 900): continue

            base_color = UITheme.NODE_MAIN if node["branch"] == "main" else UITheme.NODE_BRANCH
            
            # Selection Highlight
            if node["id"] == self.selected_node_id:
                pygame.draw.circle(surface, UITheme.ACCENT_ORANGE, (ix, iy), current_radius + 4, 2)

            # Node Body
            pygame.draw.circle(surface, UITheme.PANEL_GREY, (ix, iy), current_radius)
            pygame.draw.circle(surface, base_color, (ix, iy), current_radius, 2)
            
            # Only draw text if zoom is large enough to read it
            if self.zoom_level > 0.6:
                id_txt = self.font.render(str(node["id"]), True, UITheme.TEXT_OFF_WHITE)
                surface.blit(id_txt, id_txt.get_rect(center=(ix, iy)))

                name_txt = self.font.render(node["name"][:10], True, UITheme.TEXT_DIM)
                surface.blit(name_txt, (ix - 30, iy + current_radius + 5))

    def handle_click(self, mouse_pos, panel_rect):
        """Accounts for zoom and camera when clicking nodes."""
        # Convert global mouse to local panel coords
        local_x = mouse_pos[0] - panel_rect[0]
        local_y = mouse_pos[1] - panel_rect[1]
        local_mouse = pygame.Vector2(local_x, local_y)
        
        current_radius = self.node_radius * self.zoom_level

        for node in self.nodes:
            # Important: Use the same math used in draw()
            draw_pos = (node["pos"] * self.zoom_level) + self.camera_offset
            if draw_pos.distance_to(local_mouse) < current_radius + 5:
                self.selected_node_id = node["id"]
                return node["id"]
        return None