import pygame
import os
import json
import pandas as pd
import threading
from queue import Queue
import tkinter as tk
from tkinter import filedialog, messagebox

# Internal Modules
from settings import UITheme
from state_manager import state
from database.db_handler import DBHandler
from ui.elements import VersionTree
from ui.components import Button, draw_loading_overlay
from core.watcher import start_watcher
from engine.ai import ScienceAI
from engine.analytics import create_seaborn_surface
from core.processor import export_to_report

# --- INIT ---
pygame.init()
root = tk.Tk()
root.withdraw() 
screen = pygame.display.set_mode((1280, 720))
pygame.display.set_caption("SCI-GIT // Research Version Control")
clock = pygame.time.Clock()

# --- LOGO & WINDOW ICON ---
try:
    logo_raw = pygame.image.load("logo.jpg")
    pygame.display.set_icon(pygame.transform.scale(logo_raw, (32, 32)))
    logo_img = pygame.transform.smoothscale(logo_raw, (400, 300))
    logo_img.set_colorkey(logo_img.get_at((0,0)))
except:
    logo_img = None

# --- APP STATES ---
STATE_SPLASH = "SPLASH"
STATE_DASHBOARD = "DASHBOARD"
current_state = STATE_SPLASH
STATE_ONBOARDING = "ONBOARDING"

# --- SYSTEM COMPONENTS ---
db = None # Initialized per-selection
ai_engine = ScienceAI()
tree_ui = VersionTree()
event_queue = Queue()
watcher = None

# Fonts
font_main = pygame.font.SysFont("Consolas", 14)
font_bold = pygame.font.SysFont("Consolas", 18, bold=True)
font_header = pygame.font.SysFont("Consolas", 32, bold=True)

# --- UI ALIGNMENT ---
SCREEN_CENTER_X = 1280 // 2
BTN_WIDTH = 280
BTN_X = SCREEN_CENTER_X - (BTN_WIDTH // 2)

# Centered Splash Buttons
btn_new = Button(BTN_X, 420, BTN_WIDTH, 45, "CREATE NEW PROJECT", UITheme.ACCENT_ORANGE)
btn_load = Button(BTN_X, 480, BTN_WIDTH, 45, "CONTINUE PROJECT", UITheme.ACCENT_ORANGE)
btn_import = Button(BTN_X, 540, BTN_WIDTH, 45, "UPLOAD PROJECT", UITheme.ACCENT_ORANGE)
btn_confirm = Button(BTN_X, 520, BTN_WIDTH, 45, "ENTER LABORATORY", (0, 180, 100))

# Dashboard Buttons
btn_export = Button(850, 640, 180, 40, "GENERATE REPORT", UITheme.ACCENT_ORANGE)
btn_branch = Button(1050, 640, 180, 40, "NEW BRANCH", UITheme.NODE_BRANCH)
btn_add_manual = Button(0, 0, 32, 32, "+", UITheme.ACCENT_ORANGE) 
btn_edit_meta = Button(0, 0, 32, 32, "i", UITheme.NODE_MAIN)

btn_skip_onboarding = Button(1150, 20, 100, 35, "SKIP >>", UITheme.TEXT_DIM)
btn_onboard_upload = Button(SCREEN_CENTER_X - 150, 450, 300, 50, "UPLOAD FIRST EXPERIMENT", UITheme.ACCENT_ORANGE)

# --- DATA LOGIC ---
researcher_name = ""
input_active = False
show_login_box = False
selected_project_path = ""
is_editing_metadata = False

# Metadata buffers
meta_input_notes = ""
meta_input_temp = ""
meta_input_sid = ""
active_field = "notes"

def init_project(path):
    """Safety: Only creates folders if they don't exist."""
    for folder in ["data", "exports", "logs"]:
        os.makedirs(os.path.join(path, folder), exist_ok=True)

# ------------------------------------------------------------------
# BACKGROUND WORKERS
# ------------------------------------------------------------------
def process_new_file_worker(file_path, parent_id, branch):
    try:
        state.is_processing = True
        state.status_msg = f"ANALYZING: {os.path.basename(file_path)}..."
        
        # Check database directly to see if it's a known file
        existing_id = db.get_id_by_path(file_path)
        if existing_id:
            # If it's already there, just select it instead of adding it
            state.selected_id = existing_id
            load_experiment_worker(existing_id) # Re-use existing loading logic
            state.status_msg = "FILE ALREADY TRACKED. SELECTING SNAPSHOT."
        else:
            analysis_data = ai_engine.analyze_csv_data(file_path)
            new_id = db.add_experiment(os.path.basename(file_path), file_path, analysis_data.dict(), parent_id, branch)
            if new_id:
                state.head_id = new_id
                state.selected_id = new_id
                state.current_analysis = analysis_data.dict()
                df = pd.read_csv(file_path)
                state.current_plot = create_seaborn_surface(df)
                state.needs_tree_update = True
                state.status_msg = f"SUCCESS: COMMITTED BY {researcher_name}"
    except Exception as e:
        state.status_msg = f"ERROR: {str(e)}"
    finally:
        state.is_processing = False
        state.needs_tree_update = True # Always refresh UI to clear bugs

def load_experiment_worker(exp_id):
    try:
        state.is_processing = True
        raw = db.get_experiment_by_id(exp_id)
        if raw:
            state.current_analysis = json.loads(raw[4])
            df = pd.read_csv(raw[3])
            state.current_plot = create_seaborn_surface(df)
            state.status_msg = f"LOADED: {raw[2]}"
            # Load metadata into buffers
            global meta_input_notes, meta_input_temp, meta_input_sid
            meta_input_notes = raw[7] if raw[7] else ""
            meta_input_temp = raw[8] if raw[8] else ""
            meta_input_sid = raw[9] if raw[9] else ""
    except Exception as e:
        state.status_msg = "FAILED TO LOAD DATA."
    finally:
        state.is_processing = False

# ------------------------------------------------------------------
# MAIN LOOP
# ------------------------------------------------------------------
running = True
while running:
    mouse_pos = pygame.mouse.get_pos()
    events = pygame.event.get()
    
    for event in events:
        if event.type == pygame.QUIT:
            running = False
        
        # Keyboard Routing
        if event.type == pygame.KEYDOWN:
            if current_state == STATE_SPLASH and show_login_box:
                if event.key == pygame.K_BACKSPACE: researcher_name = researcher_name[:-1]
                else: researcher_name += event.unicode
            
            elif is_editing_metadata:
                if event.key == pygame.K_BACKSPACE:
                    if active_field == "notes": meta_input_notes = meta_input_notes[:-1]
                    elif active_field == "temp": meta_input_temp = meta_input_temp[:-1]
                    elif active_field == "sid": meta_input_sid = meta_input_sid[:-1]
                elif event.key == pygame.K_TAB:
                    active_field = "temp" if active_field == "notes" else ("sid" if active_field == "temp" else "notes")
                else:
                    if event.unicode.isprintable():
                        if active_field == "notes": meta_input_notes += event.unicode
                        elif active_field == "temp": meta_input_temp += event.unicode
                        elif active_field == "sid": meta_input_sid += event.unicode

    # --- SCREEN: SPLASH (Project Selection) ---
    if current_state == STATE_SPLASH:
        screen.fill(UITheme.BG_LOGIN)
        if logo_img:
            screen.blit(logo_img, logo_img.get_rect(center=(SCREEN_CENTER_X, 230)))
        
        if not show_login_box:
            for btn in [btn_new, btn_load, btn_import]:
                btn.draw(screen, font_main)
                if btn.check_hover(mouse_pos) and pygame.mouse.get_pressed()[0]:
                    
                    if btn.text == "CREATE NEW PROJECT":
                        path = filedialog.askdirectory(title="Select Folder for New Project")
                        if path:
                            selected_project_path = path
                            init_project(path)
                            db = DBHandler(os.path.join(path, "project_vault.db"))
                            show_login_box = True

                    elif btn.text == "CONTINUE PROJECT":
                        path = filedialog.askdirectory(title="Open Existing Sci-Git Folder")
                        if path:
                            db_path = os.path.join(path, "project_vault.db")
                            if os.path.exists(db_path):
                                selected_project_path = path
                                db = DBHandler(db_path)
                                show_login_box = True
                            else:
                                messagebox.showwarning("Project Not Found", "This folder doesn't contain a Sci-Git database.")

                    elif btn.text == "UPLOAD PROJECT":
                        file_path = filedialog.askopenfilename(title="Open Portable Snapshot", filetypes=[("Sci-Git Database", "*.db")])
                        if file_path:
                            selected_project_path = os.path.dirname(file_path)
                            db = DBHandler(file_path)
                            show_login_box = True
        else:
            # Login/Identity Box
            box_rect = pygame.Rect(SCREEN_CENTER_X - 225, 380, 450, 240)
            pygame.draw.rect(screen, (20, 20, 35), box_rect, border_radius=10)
            UITheme.draw_bracket(screen, box_rect, UITheme.ACCENT_ORANGE)
            screen.blit(font_bold.render("RESEARCHER IDENTITY", True, (255, 255, 255)), (SCREEN_CENTER_X - 100, 410))
            
            input_rect = pygame.Rect(SCREEN_CENTER_X - 190, 450, 380, 45)
            pygame.draw.rect(screen, (10, 10, 20), input_rect)
            pygame.draw.rect(screen, UITheme.ACCENT_ORANGE, input_rect, 2)
            screen.blit(font_bold.render(researcher_name + "|", True, (255, 255, 255)), (input_rect.x + 10, input_rect.y + 12))
            
            btn_confirm.draw(screen, font_main)
            if btn_confirm.check_hover(mouse_pos) and pygame.mouse.get_pressed()[0]:
                if len(researcher_name) >= 2:
                    watcher = start_watcher(os.path.join(selected_project_path, "data"), event_queue)
                    
                    # Check if project is empty
                    tree_data = db.get_tree_data()
                    if not tree_data:
                        current_state = STATE_ONBOARDING
                    else:
                        tree_ui.update_tree(tree_data)
                        current_state = STATE_DASHBOARD

    elif current_state == STATE_ONBOARDING:
        screen.fill(UITheme.BG_DARK)
        UITheme.draw_grid(screen)
        
        # Draw Logo at top
        if logo_img:
            screen.blit(logo_img, logo_img.get_rect(center=(SCREEN_CENTER_X, 200)))
            
        # Instructional Text
        msg1 = font_header.render("WELCOME TO THE LAB", True, (255, 255, 255))
        msg2 = font_bold.render("To begin, please upload your first experimental CSV file.", True, UITheme.TEXT_DIM)
        screen.blit(msg1, (SCREEN_CENTER_X - msg1.get_width()//2, 320))
        screen.blit(msg2, (SCREEN_CENTER_X - msg2.get_width()//2, 370))
        
        # Primary Action Button
        btn_onboard_upload.draw(screen, font_main)
        if btn_onboard_upload.check_hover(mouse_pos) and pygame.mouse.get_pressed()[0]:
            path = filedialog.askopenfilename(title="Select Initial Data", filetypes=[("CSV", "*.csv")])
            if path:
                # Trigger existing worker logic (Functionality Preserved!)
                threading.Thread(target=process_new_file_worker, 
                                args=(path, None, "main"), 
                                daemon=True).start()
                current_state = STATE_DASHBOARD

        # Skip Button
        btn_skip_onboarding.draw(screen, font_main)
        if btn_skip_onboarding.check_hover(mouse_pos) and pygame.mouse.get_pressed()[0]:
            current_state = STATE_DASHBOARD

    # --- SCREEN: DASHBOARD ---
    elif current_state == STATE_DASHBOARD:
        if not event_queue.empty() and not state.is_processing:
            ev = event_queue.get()
            if ev["type"] == "NEW_FILE":
                threading.Thread(target=process_new_file_worker, args=(ev["path"], state.head_id, state.active_branch), daemon=True).start()

        if state.needs_tree_update:
            tree_ui.update_tree(db.get_tree_data())
            state.needs_tree_update = False

        for event in events:
            if event.type == pygame.MOUSEWHEEL: tree_ui.handle_zoom("in" if event.y > 0 else "out")
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2: tree_ui.is_panning = True
            if event.type == pygame.MOUSEBUTTONUP and event.button == 2: tree_ui.is_panning = False
            if event.type == pygame.MOUSEMOTION and tree_ui.is_panning: tree_ui.camera_offset += pygame.Vector2(event.rel)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Tree Menu Clicks
                if state.selected_id and btn_add_manual.check_hover(mouse_pos):
                    path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
                    if path: threading.Thread(target=process_new_file_worker, args=(path, state.selected_id, state.active_branch), daemon=True).start()
                elif state.selected_id and btn_edit_meta.check_hover(mouse_pos):
                    is_editing_metadata = not is_editing_metadata
                else:
                    cid = tree_ui.handle_click(event.pos, (20, 80, 800, 600))
                    if cid:
                        state.selected_id = cid
                        threading.Thread(target=load_experiment_worker, args=(cid,), daemon=True).start()

        # Rendering Dashboard
        screen.fill(UITheme.BG_DARK)
        UITheme.draw_grid(screen)
        
        # Header
        pygame.draw.rect(screen, UITheme.PANEL_GREY, (0, 0, 1280, 60))
        pygame.draw.line(screen, UITheme.ACCENT_ORANGE, (0, 60), (1280, 60), 2)
        screen.blit(font_bold.render(f"SCI-GIT // {os.path.basename(selected_project_path).upper()} // {researcher_name.upper()}", True, UITheme.ACCENT_ORANGE), (20, 20))
        screen.blit(font_main.render(f"> {state.status_msg}", True, UITheme.TEXT_DIM), (850, 22))

        # Version Tree
        tree_surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        tree_ui.draw(tree_surf, mouse_pos)
        screen.blit(tree_surf, (20, 80))
        UITheme.draw_bracket(screen, (20, 80, 800, 600), UITheme.ACCENT_ORANGE)

        # Context Icons
        if state.selected_id:
            for node in tree_ui.nodes:
                if node["id"] == state.selected_id:
                    pos = (node["pos"] * tree_ui.zoom_level) + tree_ui.camera_offset
                    mx, my = pos.x + 45, pos.y + 60
                    btn_add_manual.rect.topleft = (mx, my)
                    btn_edit_meta.rect.topleft = (mx, my + 40)
                    btn_add_manual.draw(screen, font_main)
                    btn_edit_meta.draw(screen, font_main)

        # Right Panel Toggle
        side_rect = (840, 80, 420, 600)
        pygame.draw.rect(screen, UITheme.PANEL_GREY, side_rect)
        UITheme.draw_bracket(screen, side_rect, (100, 100, 100))

        if not is_editing_metadata:
            # --- NORMAL MODE: SHOW PLOT AND AI ---
            if state.current_plot: 
                screen.blit(state.current_plot, (850, 100))
                pygame.draw.rect(screen, (50, 50, 55), (850, 100, 400, 300), 1)
            if state.current_analysis:
                UITheme.render_terminal_text(screen, state.current_analysis.get('summary', ""), (855, 420), font_main, UITheme.TEXT_OFF_WHITE, 390)
        else:
            # --- EDIT MODE: SHOW INPUT BOXES ---
            screen.blit(font_bold.render("MANUAL DATA ENTRY", True, UITheme.ACCENT_ORANGE), (855, 100))
            y_ptr = 150
            for label, key in [("NOTES:", "notes"), ("TEMP (°C):", "temp"), ("SAMPLE ID:", "sid")]:
                screen.blit(font_main.render(label, True, UITheme.TEXT_DIM), (855, y_ptr))
                rect = pygame.Rect(855, y_ptr + 20, 390, 35)
                pygame.draw.rect(screen, (10, 10, 15), rect)
                pygame.draw.rect(screen, (UITheme.ACCENT_ORANGE if active_field == key else (50, 50, 60)), rect, 1)
                
                val = meta_input_notes if key == "notes" else (meta_input_temp if key == "temp" else meta_input_sid)
                screen.blit(font_main.render(val + ("|" if active_field == key else ""), True, (255, 255, 255)), (860, y_ptr + 28))
                
                if pygame.mouse.get_pressed()[0] and rect.collidepoint(mouse_pos): 
                    active_field = key
                y_ptr += 80
            
            btn_save = Button(855, 500, 390, 40, "SAVE TO SNAPSHOT", (0, 150, 255))
            btn_save.draw(screen, font_main)
            if btn_save.check_hover(mouse_pos) and pygame.mouse.get_pressed()[0]:
                db.update_metadata(state.selected_id, meta_input_notes, meta_input_temp, meta_input_sid)
                is_editing_metadata = False

        # Dashboard Buttons
        btn_export.draw(screen, font_main)
        btn_branch.draw(screen, font_main)
        if state.is_processing: draw_loading_overlay(screen, font_bold)

    pygame.display.flip()
    clock.tick(60)
pygame.quit()