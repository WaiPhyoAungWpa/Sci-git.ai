import pygame
from settings import UITheme
from state_manager import state  # Need state to access selected_ids

class VersionTree:
    def __init__(self):
        self.nodes = []  
        self.connections = []
        self.node_radius = 18
        
        # Camera & Navigation
        self.camera_offset = pygame.Vector2(60, 300)
        self.zoom_level = 1.0
        self.is_panning = False
        
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

        if self.nodes:
            max_x = max(n['pos'].x for n in self.nodes)
            scaled_max_x = max_x * self.zoom_level
            self.camera_offset.x = 600 - scaled_max_x

    def draw(self, surface, mouse_pos):
        surface.fill((0, 0, 0, 0))

        # 1. Draw Connections
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

        # 2. Draw Nodes
        current_radius = int(self.node_radius * self.zoom_level)
        
        for node in self.nodes:
            draw_pos = (node["pos"] * self.zoom_level) + self.camera_offset
            ix, iy = int(draw_pos.x), int(draw_pos.y)
            
            if not (-100 < ix < 900): continue

            base_color = UITheme.NODE_MAIN if node["branch"] == "main" else UITheme.NODE_BRANCH
            
            # --- SELECTION HIGHLIGHT LOGIC ---
            # Primary = Orange, Secondary = Cyan
            if node["id"] in state.selected_ids:
                idx = state.selected_ids.index(node["id"])
                # 0 = Primary (Orange), 1 = Secondary (Cyan)
                hl_color = UITheme.ACCENT_ORANGE if idx == 0 else (0, 255, 255)
                pygame.draw.circle(surface, hl_color, (ix, iy), current_radius + 4, 3)

            # Node Body
            pygame.draw.circle(surface, UITheme.PANEL_GREY, (ix, iy), current_radius)
            pygame.draw.circle(surface, base_color, (ix, iy), current_radius, 2)
            
            if self.zoom_level > 0.6:
                id_txt = self.font.render(str(node["id"]), True, UITheme.TEXT_OFF_WHITE)
                surface.blit(id_txt, id_txt.get_rect(center=(ix, iy)))

                name_txt = self.font.render(node["name"][:10], True, UITheme.TEXT_DIM)
                surface.blit(name_txt, (ix - 30, iy + current_radius + 5))

    def handle_click(self, mouse_pos, panel_rect):
        """Dual-Node Selection Logic with Ctrl support."""
        local_x = mouse_pos[0] - panel_rect[0]
        local_y = mouse_pos[1] - panel_rect[1]
        local_mouse = pygame.Vector2(local_x, local_y)
        
        current_radius = self.node_radius * self.zoom_level

        clicked_node = None
        for node in self.nodes:
            draw_pos = (node["pos"] * self.zoom_level) + self.camera_offset
            if draw_pos.distance_to(local_mouse) < current_radius + 5:
                clicked_node = node["id"]
                break
        
        if clicked_node:
            # Check for CTRL key
            keys = pygame.key.get_pressed()
            is_ctrl = keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]

            if is_ctrl:
                if clicked_node in state.selected_ids:
                    state.selected_ids.remove(clicked_node) # Toggle off
                else:
                    if len(state.selected_ids) < 2:
                        state.selected_ids.append(clicked_node) # Add second
                    else:
                        state.selected_ids = [clicked_node] # Reset on 3rd click
            else:
                # Standard click resets to single selection
                state.selected_ids = [clicked_node]

            return state.selected_ids
        return None