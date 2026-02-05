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
root.withdraw() # Hide the tiny tkinter window
screen = pygame.display.set_mode((1280, 720))
pygame.display.set_caption("SCI-GIT // Research Version Control")
clock = pygame.time.Clock()

# --- LOGO & WINDOW ICON ---
try:
    logo_raw = pygame.image.load("logo.jpg")
    # Set the small taskbar icon
    icon_surf = pygame.transform.scale(logo_raw, (32, 32))
    pygame.display.set_icon(icon_surf)
    # Scale for Splash Screen
    logo_img = pygame.transform.smoothscale(logo_raw, (400, 300))
    # Remove the box effect (Transparency based on top-left pixel)
    logo_img.set_colorkey(logo_img.get_at((0,0)))
except:
    logo_img = None

# --- APP STATES ---
STATE_SPLASH = "SPLASH"
STATE_DASHBOARD = "DASHBOARD"
current_state = STATE_SPLASH

# --- SYSTEM COMPONENTS ---
db = DBHandler()
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

# Main Screen Buttons (Centered)
btn_new = Button(BTN_X, 420, BTN_WIDTH, 45, "CREATE NEW PROJECT", UITheme.ACCENT_ORANGE)
btn_load = Button(BTN_X, 480, BTN_WIDTH, 45, "CONTINUE PROJECT", UITheme.ACCENT_ORANGE)
btn_import = Button(BTN_X, 540, BTN_WIDTH, 45, "UPLOAD PROJECT", UITheme.ACCENT_ORANGE)

# Login Confirmation (Green)
btn_confirm = Button(BTN_X, 520, BTN_WIDTH, 45, "ENTER LABORATORY", (0, 180, 100))

# Dashboard Buttons (Original Positions)
btn_export = Button(850, 640, 180, 40, "GENERATE REPORT", UITheme.ACCENT_ORANGE)
btn_branch = Button(1050, 640, 180, 40, "NEW BRANCH", UITheme.NODE_BRANCH)

# --- DATA LOGIC ---
researcher_name = ""
input_active = False
show_login_box = False
selected_project_path = ""

def init_project(path):
    for folder in ["data", "exports", "logs"]:
        os.makedirs(os.path.join(path, folder), exist_ok=True)

# ------------------------------------------------------------------
# BACKGROUND WORKERS
# ------------------------------------------------------------------
def process_new_file_worker(file_path, parent_id, branch):
    try:
        state.is_processing = True
        state.status_msg = f"ANALYZING: {os.path.basename(file_path)}..."
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

def load_experiment_worker(exp_id):
    try:
        state.is_processing = True
        raw = db.get_experiment_by_id(exp_id)
        if raw:
            state.current_analysis = json.loads(raw[4])
            df = pd.read_csv(raw[3])
            state.current_plot = create_seaborn_surface(df)
            state.status_msg = f"LOADED: {raw[2]}"
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
        
        # Name Input
        if event.type == pygame.KEYDOWN and input_active:
            if event.key == pygame.K_BACKSPACE:
                researcher_name = researcher_name[:-1]
            elif event.key == pygame.K_RETURN:
                input_active = False
            else:
                if len(researcher_name) < 20:
                    researcher_name += event.unicode

    # --- SCREEN: SPLASH / PROJECT SELECT ---
    if current_state == STATE_SPLASH:
        screen.fill(UITheme.BG_LOGIN)
        
        if logo_img:
            logo_rect = logo_img.get_rect(center=(SCREEN_CENTER_X, 230))
            screen.blit(logo_img, logo_rect)
        
        if not show_login_box:
            # Render Project Buttons
            for btn in [btn_new, btn_load, btn_import]:
                btn.draw(screen, font_main)
                if btn.check_hover(mouse_pos) and pygame.mouse.get_pressed()[0]:
                    if btn.text == "CREATE NEW PROJECT":
                        path = filedialog.askdirectory()
                        if path:
                            selected_project_path = path
                            init_project(path)
                            show_login_box = True
                    elif btn.text == "CONTINUE PROJECT":
                        path = filedialog.askdirectory()
                        if path:
                            selected_project_path = path
                            show_login_box = True
        else:
            # Login Box Layout
            box_rect = pygame.Rect(SCREEN_CENTER_X - 225, 380, 450, 240)
            pygame.draw.rect(screen, (20, 20, 35), box_rect, border_radius=10)
            UITheme.draw_bracket(screen, box_rect, UITheme.ACCENT_ORANGE)
            
            prompt = font_bold.render("RESEARCHER IDENTITY", True, (255, 255, 255))
            screen.blit(prompt, (SCREEN_CENTER_X - prompt.get_width()//2, 410))
            
            input_rect = pygame.Rect(SCREEN_CENTER_X - 190, 450, 380, 45)
            pygame.draw.rect(screen, (10, 10, 20), input_rect)
            border_col = UITheme.ACCENT_ORANGE if input_active else (100, 100, 100)
            pygame.draw.rect(screen, border_col, input_rect, 2)
            
            name_surf = font_bold.render(researcher_name + ("|" if input_active else ""), True, (255, 255, 255))
            screen.blit(name_surf, (input_rect.x + 10, input_rect.y + 12))
            
            if pygame.mouse.get_pressed()[0]:
                input_active = input_rect.collidepoint(mouse_pos)
            
            btn_confirm.draw(screen, font_main)
            if btn_confirm.check_hover(mouse_pos) and pygame.mouse.get_pressed()[0]:
                if len(researcher_name) >= 2:
                    watcher = start_watcher(os.path.join(selected_project_path, "data"), event_queue)
                    tree_ui.update_tree(db.get_tree_data())
                    current_state = STATE_DASHBOARD

    # --- SCREEN: DASHBOARD ---
    elif current_state == STATE_DASHBOARD:
        # 1. Background Logic
        if not event_queue.empty() and not state.is_processing:
            ev = event_queue.get()
            if ev["type"] == "NEW_FILE":
                threading.Thread(target=process_new_file_worker, args=(ev["path"], state.head_id, state.active_branch), daemon=True).start()

        if state.needs_tree_update:
            tree_ui.update_tree(db.get_tree_data())
            state.needs_tree_update = False

        # 2. Event Handling
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and not state.is_processing:
                # Tree Clicks
                clicked_id = tree_ui.handle_click(event.pos, (20, 80, 800, 600))
                if clicked_id:
                    state.selected_id = clicked_id
                    threading.Thread(target=load_experiment_worker, args=(clicked_id,), daemon=True).start()

                # Button Clicks
                if btn_export.check_hover(mouse_pos) and state.current_analysis:
                    report_name = f"report_exp_{state.selected_id}.pdf"
                    export_to_report(report_name, state.current_analysis, state.active_branch)
                    state.status_msg = f"EXPORTED: {report_name}"

                if btn_branch.check_hover(mouse_pos):
                    state.active_branch = "dev_branch" if state.active_branch == "main" else "main"
                    state.status_msg = f"SWITCHED TO BRANCH: {state.active_branch}"

        # 3. Rendering
        screen.fill(UITheme.BG_DARK)
        UITheme.draw_grid(screen)
        
        # Header
        pygame.draw.rect(screen, UITheme.PANEL_GREY, (0, 0, 1280, 60))
        pygame.draw.line(screen, UITheme.ACCENT_ORANGE, (0, 60), (1280, 60), 2)
        header_txt = f"SCI-GIT // PROJECT: {os.path.basename(selected_project_path).upper()} // USER: {researcher_name.upper()}"
        title = font_bold.render(header_txt, True, UITheme.ACCENT_ORANGE)
        screen.blit(title, (20, 20))
        
        status_surf = font_main.render(f"> {state.status_msg}", True, UITheme.TEXT_DIM)
        screen.blit(status_surf, (850, 22))

        # Version Tree Panel
        tree_rect = (20, 80, 800, 600)
        pygame.draw.rect(screen, UITheme.PANEL_GREY, tree_rect)
        UITheme.draw_bracket(screen, tree_rect, UITheme.ACCENT_ORANGE)
        tree_surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        tree_ui.draw(tree_surf, mouse_pos)
        screen.blit(tree_surf, (20, 80))

        # Analysis Panel
        side_rect = (840, 80, 420, 600)
        pygame.draw.rect(screen, UITheme.PANEL_GREY, side_rect)
        UITheme.draw_bracket(screen, side_rect, (100, 100, 100))
        
        if state.current_plot:
            screen.blit(state.current_plot, (850, 100))
            pygame.draw.rect(screen, (50, 50, 55), (850, 100, 400, 300), 1)
        
        if state.current_analysis:
            UITheme.render_terminal_text(screen, state.current_analysis.get('summary', ""), (855, 420), font_main, UITheme.TEXT_OFF_WHITE, 390)

        # Buttons
        btn_export.draw(screen, font_main)
        btn_branch.draw(screen, font_main)
        btn_export.check_hover(mouse_pos)
        btn_branch.check_hover(mouse_pos)

        if state.is_processing:
            draw_loading_overlay(screen, font_bold)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()