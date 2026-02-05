import pygame
import os
import json
import pandas as pd
import threading
from queue import Queue
import tkinter as tk # For File Explorer
from tkinter import filedialog

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

# --- CONFIGURATION & INIT ---
pygame.init()
screen = pygame.display.set_mode((1280, 720))
pygame.display.set_caption("SCI-GIT // Research Version Control")
clock = pygame.time.Clock()

# --- APP STATES ---
STATE_SPLASH = "SPLASH"
STATE_LOGIN = "LOGIN"
STATE_DASHBOARD = "DASHBOARD"
current_state = STATE_SPLASH
frame_count = 0

# --- SYSTEM COMPONENTS ---
# (Previously initialized at the top level, now ready for use)
db = DBHandler()
ai_engine = ScienceAI()
tree_ui = VersionTree()
event_queue = Queue()
# Watcher starts later once a project folder is selected
watcher = None 

# Fonts
font_main = pygame.font.SysFont("Consolas", 14)
font_bold = pygame.font.SysFont("Consolas", 18, bold=True)
font_header = pygame.font.SysFont("Consolas", 32, bold=True)

# --- LOGIN UI ELEMENTS ---
# These are used for the new Onboarding screens
btn_start_guest = Button(540, 450, 200, 50, "CONTINUE AS GUEST", UITheme.ACCENT_ORANGE)
researcher_name = "Researcher_1" # Default

# --- DASHBOARD UI ELEMENTS ---
# (From your original code)
btn_export = Button(850, 640, 180, 40, "GENERATE REPORT", UITheme.ACCENT_ORANGE)
btn_branch = Button(1050, 640, 180, 40, "NEW BRANCH", UITheme.NODE_BRANCH)

# --- LOGO LOADING ---
try:
    # Use logo.jpg as provided in your prompt
    logo_img = pygame.image.load("logo.jpg")
    logo_img = pygame.transform.smoothscale(logo_img, (300, 220))
except:
    logo_img = None

# ------------------------------------------------------------------
# BACKGROUND WORKERS (Kept identical to your original logic)
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
    frame_count += 1
    mouse_pos = pygame.mouse.get_pos()
    
    # 1. HANDLE GLOBAL EVENTS (Close App)
    events = pygame.event.get()
    for event in events:
        if event.type == pygame.QUIT:
            running = False

    # ------------------------------------------------------------------
    # SCREEN STATE: SPLASH (The "Blue Entrance")
    # ------------------------------------------------------------------
    if current_state == STATE_SPLASH:
        screen.fill(UITheme.BG_LOGIN)
        UITheme.draw_scanning_lines(screen, frame_count)
        
        if logo_img:
            screen.blit(logo_img, (1280//2 - 150, 720//2 - 150))
        
        title_surf = font_header.render("SCI-GIT.AI", True, (255, 255, 255))
        screen.blit(title_surf, (1280//2 - title_surf.get_width()//2, 500))
        
        # Automatically transition after 3 seconds
        if frame_count > 180:
            current_state = STATE_LOGIN

    # ------------------------------------------------------------------
    # SCREEN STATE: LOGIN (Project & Identity Setup)
    # ------------------------------------------------------------------
    elif current_state == STATE_LOGIN:
        screen.fill(UITheme.BG_LOGIN)
        UITheme.draw_scanning_lines(screen, frame_count)
        
        # Center Box
        login_rect = pygame.Rect(440, 200, 400, 350)
        pygame.draw.rect(screen, (20, 20, 35), login_rect, border_radius=10)
        UITheme.draw_bracket(screen, login_rect, UITheme.ACCENT_ORANGE)
        
        # Text Prompts
        msg = font_bold.render("PROJECT AUTHORIZATION", True, UITheme.ACCENT_ORANGE)
        screen.blit(msg, (460, 230))
        
        name_label = font_main.render(f"RESEARCHER: {researcher_name}", True, (200, 200, 200))
        screen.blit(name_label, (460, 300))
        
        # Button logic
        btn_start_guest.draw(screen, font_main)
        btn_start_guest.check_hover(mouse_pos)
        
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN:
                if btn_start_guest.is_hovered:
                    # Initialize Watcher and go to Dashboard
                    WATCH_FOLDER = "./my_experiments"
                    if not os.path.exists(WATCH_FOLDER): os.makedirs(WATCH_FOLDER)
                    watcher = start_watcher(WATCH_FOLDER, event_queue)
                    tree_ui.update_tree(db.get_tree_data())
                    current_state = STATE_DASHBOARD

    # ------------------------------------------------------------------
    # SCREEN STATE: DASHBOARD (Your existing logic)
    # ------------------------------------------------------------------
    elif current_state == STATE_DASHBOARD:
        # --- OLD main.py Logic Starts Here ---
        
        # 1. Handle Background Events
        if not event_queue.empty() and not state.is_processing:
            ev = event_queue.get()
            if ev["type"] == "NEW_FILE":
                threading.Thread(target=process_new_file_worker, args=(ev["path"], state.head_id, state.active_branch), daemon=True).start()

        # 2. UI Updates
        if state.needs_tree_update:
            tree_ui.update_tree(db.get_tree_data())
            state.needs_tree_update = False

        # 3. Handle Dashboard Clicks
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and not state.is_processing:
                # Tree Clicks
                clicked_id = tree_ui.handle_click(event.pos, (20, 80, 800, 600))
                if clicked_id:
                    state.selected_id = clicked_id
                    threading.Thread(target=load_experiment_worker, args=(clicked_id,), daemon=True).start()

                # Button: Export
                if btn_export.check_hover(mouse_pos) and state.current_analysis:
                    report_name = f"report_exp_{state.selected_id}.pdf"
                    export_to_report(report_name, state.current_analysis, state.active_branch)
                    state.status_msg = f"EXPORTED: {report_name}"

                # Button: Branch
                if btn_branch.check_hover(mouse_pos):
                    state.active_branch = "dev_branch" if state.active_branch == "main" else "main"
                    state.status_msg = f"SWITCHED TO BRANCH: {state.active_branch}"

        # 4. Rendering Dashboard
        screen.fill(UITheme.BG_DARK)
        UITheme.draw_grid(screen)
        
        # --- Header ---
        pygame.draw.rect(screen, UITheme.PANEL_GREY, (0, 0, 1280, 60))
        pygame.draw.line(screen, UITheme.ACCENT_ORANGE, (0, 60), (1280, 60), 2)
        title = font_bold.render(f"SCI-GIT // PROTOCOL: {state.active_branch.upper()} // USER: {researcher_name}", True, UITheme.ACCENT_ORANGE)
        screen.blit(title, (20, 20))
        
        status_surf = font_main.render(f"> {state.status_msg}", True, UITheme.TEXT_DIM)
        screen.blit(status_surf, (850, 22))

        # --- Tree Panel ---
        tree_rect = (20, 80, 800, 600)
        pygame.draw.rect(screen, UITheme.PANEL_GREY, tree_rect)
        UITheme.draw_bracket(screen, tree_rect, UITheme.ACCENT_ORANGE)
        tree_surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        tree_ui.draw(tree_surf, mouse_pos)
        screen.blit(tree_surf, (20, 80))

        # --- Analysis Panel ---
        side_rect = (840, 80, 420, 600)
        pygame.draw.rect(screen, UITheme.PANEL_GREY, side_rect)
        UITheme.draw_bracket(screen, side_rect, (100, 100, 100))
        
        if state.current_plot:
            screen.blit(state.current_plot, (850, 100))
        
        if state.current_analysis:
            UITheme.render_terminal_text(screen, state.current_analysis.get('summary', ""), (855, 450), font_main, UITheme.TEXT_OFF_WHITE, 390)

        # Draw Dashboard Buttons
        btn_export.draw(screen, font_main)
        btn_branch.draw(screen, font_main)
        btn_export.check_hover(mouse_pos)
        btn_branch.check_hover(mouse_pos)

        # Overlays
        if state.is_processing:
            draw_loading_overlay(screen, font_bold)

    pygame.display.flip()
    clock.tick(60)

# Cleanup
if watcher: watcher.stop()
db.close()
pygame.quit()