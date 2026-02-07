import pygame
import os
import json
import pandas as pd
import threading
import shutil
import sys
from queue import Queue
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

from settings import UITheme
from state_manager import state
from database.db_handler import DBHandler
from ui.elements import VersionTree
from ui.components import Button, draw_loading_overlay
from core.watcher import start_watcher
from engine.ai import ScienceAI
from engine.analytics import create_seaborn_surface, HeaderScanner
from core.processor import export_to_report

# --- ENV LOADING ---
if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ[k] = v

# --- INIT ---
pygame.init()
root = tk.Tk()
root.withdraw() 
screen = pygame.display.set_mode((1280, 720))
pygame.display.set_caption("SCI-GIT // Research Version Control")
clock = pygame.time.Clock()

try:
    logo_raw = pygame.image.load("logo.jpg")
    pygame.display.set_icon(pygame.transform.scale(logo_raw, (32, 32)))
    logo_img = pygame.transform.smoothscale(logo_raw, (400, 300))
    logo_img.set_colorkey(logo_img.get_at((0,0)))
except: logo_img = None

# --- STATES ---
STATE_SPLASH = "SPLASH"
STATE_DASHBOARD = "DASHBOARD"
STATE_ONBOARDING = "ONBOARDING"
STATE_EDITOR = "EDITOR" # NEW: Spreadsheet Editor State
current_state = STATE_SPLASH

db = None 
ai_engine = ScienceAI()
tree_ui = VersionTree()
event_queue = Queue()
watcher = None

font_main = pygame.font.SysFont("Consolas", 14)
font_bold = pygame.font.SysFont("Consolas", 18, bold=True)
font_header = pygame.font.SysFont("Consolas", 32, bold=True)
font_small = pygame.font.SysFont("Consolas", 10)

SCREEN_CENTER_X = 1280 // 2
BTN_WIDTH = 280
BTN_X = SCREEN_CENTER_X - (BTN_WIDTH // 2)

# BUTTONS
btn_new = Button(BTN_X, 420, BTN_WIDTH, 45, "CREATE NEW PROJECT", UITheme.ACCENT_ORANGE)
btn_load = Button(BTN_X, 480, BTN_WIDTH, 45, "CONTINUE PROJECT", UITheme.ACCENT_ORANGE)
btn_import = Button(BTN_X, 540, BTN_WIDTH, 45, "UPLOAD PROJECT", UITheme.ACCENT_ORANGE)
btn_confirm = Button(BTN_X, 520, BTN_WIDTH, 45, "ENTER LABORATORY", (0, 180, 100))

btn_export = Button(850, 640, 180, 40, "GENERATE REPORT", UITheme.ACCENT_ORANGE)
btn_branch = Button(1050, 640, 180, 40, "NEW BRANCH", UITheme.NODE_BRANCH)
btn_snapshot_export = Button(1100, 5, 160, 25, "EXPORT PROJECT", (50, 50, 60))
btn_add_manual = Button(0, 0, 32, 32, "+", UITheme.ACCENT_ORANGE) 
btn_edit_meta = Button(0, 0, 32, 32, "i", UITheme.NODE_MAIN)
btn_save_meta = Button(855, 500, 390, 40, "SAVE TO SNAPSHOT", (0, 150, 255))
btn_conv_yes = Button(500, 400, 100, 40, "YES", (0, 180, 100))
btn_conv_no = Button(680, 400, 100, 40, "NO", (200, 50, 50))
btn_axis_gear = Button(1210, 100, 30, 30, "O", (80, 80, 90)) 
btn_skip_onboarding = Button(1150, 20, 100, 35, "SKIP >>", UITheme.TEXT_DIM)
btn_onboard_upload = Button(SCREEN_CENTER_X - 150, 450, 300, 50, "UPLOAD FIRST EXPERIMENT", UITheme.ACCENT_ORANGE)

# MENU BAR BTNS
btn_menu_file = Button(20, 45, 60, 20, "FILE", UITheme.PANEL_GREY)
btn_menu_edit = Button(90, 45, 100, 20, "EDIT FILE", UITheme.PANEL_GREY)
btn_menu_analyze = Button(200, 45, 80, 20, "ANALYZE", UITheme.PANEL_GREY)

# EDITOR BTNS
btn_editor_save = Button(1050, 650, 200, 40, "SAVE CHANGES", (0, 180, 100))
btn_editor_exit = Button(20, 650, 150, 40, "CANCEL", (200, 50, 50))

researcher_name = ""
show_login_box = False
selected_project_path = ""
is_editing_metadata = False
search_text = ""
search_active = False

meta_input_notes = ""
meta_input_temp = ""
meta_input_sid = ""
active_field = "notes"

# --- EDITOR VARS ---
editor_df = None
editor_file_path = None
editor_scroll_y = 0
editor_selected_cell = None # (row_idx, col_idx)
editor_input_buffer = ""

def init_project(path):
    for folder in ["data", "exports", "logs"]: os.makedirs(os.path.join(path, folder), exist_ok=True)

def load_database_safe(path):
    global db
    if db: 
        try: db.close()
        except: pass
    db = DBHandler(path)

def export_project_worker(project_path):
    try:
        state.is_processing = True
        state.status_msg = "COMPRESSING PROJECT..."
        ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M")
        zip_name = f"SciGit_Export_{ts}"
        output_path = os.path.join(project_path, "exports", zip_name) 
        shutil.make_archive(output_path, 'zip', project_path)
        state.status_msg = f"EXPORT COMPLETE: {zip_name}.zip"
    except Exception as e: state.status_msg = f"EXPORT FAILED: {str(e)}"
    finally: state.is_processing = False

def analyze_branch_worker():
    try:
        state.is_processing = True
        state.status_msg = "GENERATING BRANCH EVOLUTION REPORT..."
        tree = db.get_tree_data()
        branch_nodes = [row for row in tree if row[2] == state.active_branch]
        history_text = ""
        for row in branch_nodes[-5:]:
            history_text += f"ID: {row[0]} | Name: {row[3]}\n"
        report = ai_engine.analyze_branch_history(history_text)
        state.current_analysis = {"summary": f"BRANCH REPORT ({state.active_branch}):\n{report}", "anomalies": []}
        state.status_msg = "BRANCH ANALYSIS COMPLETE."
    except Exception as e: state.status_msg = f"ERROR: {e}"
    finally: state.is_processing = False

def process_new_file_worker(file_path, parent_id, branch):
    try:
        state.is_processing = True
        state.status_msg = f"ANALYZING: {os.path.basename(file_path)}..."
        existing_id = db.get_id_by_path(file_path)
        if existing_id:
            state.selected_ids = [existing_id] 
            load_experiment_worker([existing_id])
            state.status_msg = "FILE ALREADY TRACKED."
        else:
            analysis_data = ai_engine.analyze_csv_data(file_path)
            new_id = db.add_experiment(os.path.basename(file_path), file_path, analysis_data.model_dump(), parent_id, branch)
            if new_id:
                state.head_id = new_id
                state.selected_ids = [new_id]
                state.current_analysis = analysis_data.model_dump()
                df = pd.read_csv(file_path)
                state.current_plot, state.plot_context = create_seaborn_surface(df)
                state.needs_tree_update = True
                state.status_msg = f"COMMITTED BY {researcher_name}"
    except Exception as e: state.status_msg = f"ERROR: {str(e)}"
    finally:
        state.is_processing = False
        state.needs_tree_update = True 

def load_experiment_worker(exp_ids, custom_x=None, custom_y=None, save_settings=False):
    try:
        state.is_processing = True
        if len(exp_ids) == 1:
            raw = db.get_experiment_by_id(exp_ids[0])
            if raw:
                # Load settings logic
                saved_settings = None
                if len(raw) > 11 and raw[11]: saved_settings = json.loads(raw[11])
                final_x = custom_x if custom_x else (saved_settings.get("x") if saved_settings else None)
                final_y = custom_y if custom_y else (saved_settings.get("y") if saved_settings else None)
                if save_settings and final_x and final_y: db.update_plot_settings(exp_ids[0], final_x, final_y)

                state.current_analysis = json.loads(raw[4])
                df = pd.read_csv(raw[3])
                state.current_plot, state.plot_context = create_seaborn_surface(df, x_col=final_x, y_col=final_y)
                state.status_msg = f"LOADED: {raw[2]}"
                
                global meta_input_notes, meta_input_temp, meta_input_sid
                meta_input_notes = raw[-4] if raw[-4] else ""
                meta_input_temp = raw[-3] if raw[-3] else ""
                meta_input_sid = raw[-2] if raw[-2] else ""

        elif len(exp_ids) == 2:
            raw1 = db.get_experiment_by_id(exp_ids[0])
            raw2 = db.get_experiment_by_id(exp_ids[1])
            if raw1 and raw2:
                df1 = pd.read_csv(raw1[3])
                df2 = pd.read_csv(raw2[3])
                u1, col1 = HeaderScanner.detect_temp_unit(df1)
                u2, col2 = HeaderScanner.detect_temp_unit(df2)
                
                if u1 and u2 and u1 != u2:
                    state.pending_conversion = (raw2[3], col2, u1) 
                    state.show_conversion_dialog = True
                    state.current_plot, state.plot_context = create_seaborn_surface(df1, df2)
                    state.status_msg = "UNIT MISMATCH DETECTED."
                else:
                    state.status_msg = "RUNNING DELTA ANALYSIS..."
                    state.current_plot, state.plot_context = create_seaborn_surface(df1, df2, x_col=custom_x, y_col=custom_y)
                    comparison_result = ai_engine.compare_experiments(df1, df2)
                    state.current_analysis = comparison_result
                    state.status_msg = "COMPARATIVE ANALYSIS COMPLETE"
    except Exception as e: state.status_msg = f"FAILED TO LOAD: {e}"
    finally: state.is_processing = False

def perform_conversion_worker(file_path, column, to_unit, ids_to_reload):
    try:
        state.is_processing = True
        df = pd.read_csv(file_path)
        df = HeaderScanner.convert_column(df, column, to_unit)
        df.to_csv(file_path, index=False)
        state.status_msg = f"CONVERSION COMPLETE."
        load_experiment_worker(ids_to_reload)
    except Exception as e: state.status_msg = f"CONVERSION ERROR: {e}"
    finally:
        state.is_processing = False
        state.show_conversion_dialog = False

def save_editor_changes():
    """Saves the modified DF from Editor to CSV."""
    global editor_df, editor_file_path
    try:
        editor_df.to_csv(editor_file_path, index=False)
        state.status_msg = "FILE UPDATED SUCCESSFULLY."
        # Reload to update graph
        threading.Thread(target=load_experiment_worker, args=(state.selected_ids,), daemon=True).start()
    except Exception as e:
        state.status_msg = f"SAVE FAILED: {e}"

# --- MAIN LOOP ---
running = True
while running:
    mouse_pos = pygame.mouse.get_pos()
    events = pygame.event.get()
    
    axis_selector_rect = pygame.Rect(850, 130, 200, 300)

    for event in events:
        if event.type == pygame.QUIT: running = False
        
        # --- EDITOR KEYBOARD INPUT ---
        if current_state == STATE_EDITOR and event.type == pygame.KEYDOWN:
            if editor_selected_cell:
                if event.key == pygame.K_RETURN:
                    # Commit change
                    r, c = editor_selected_cell
                    try:
                        # Auto-detect type (float vs string)
                        val = float(editor_input_buffer)
                        editor_df.iloc[r, c] = val
                    except ValueError:
                        editor_df.iloc[r, c] = editor_input_buffer
                    editor_selected_cell = None
                elif event.key == pygame.K_BACKSPACE:
                    editor_input_buffer = editor_input_buffer[:-1]
                else:
                    editor_input_buffer += event.unicode
            elif event.key == pygame.K_DOWN: editor_scroll_y = max(0, editor_scroll_y - 1)
            elif event.key == pygame.K_UP: editor_scroll_y += 1

        # --- MOUSE INPUT ---
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if current_state == STATE_EDITOR:
                if btn_editor_save.check_hover(mouse_pos):
                    save_editor_changes()
                    current_state = STATE_DASHBOARD
                elif btn_editor_exit.check_hover(mouse_pos):
                    current_state = STATE_DASHBOARD
                
                # GRID CLICK LOGIC
                # Header height = 60, Row height = 30, Col width = 100
                grid_y_start = 100
                x_scroll = 50
                
                # Check if click is in grid area
                if 50 < mouse_pos[0] < 1230 and 100 < mouse_pos[1] < 600:
                    rel_y = mouse_pos[1] - grid_y_start
                    row_idx = (rel_y // 30) + int(editor_scroll_y)
                    col_idx = (mouse_pos[0] - x_scroll) // 100
                    
                    if 0 <= row_idx < len(editor_df) and 0 <= col_idx < len(editor_df.columns):
                        editor_selected_cell = (row_idx, col_idx)
                        editor_input_buffer = str(editor_df.iloc[row_idx, col_idx])
                    else:
                        editor_selected_cell = None

            # DASHBOARD LOGIC
            elif current_state == STATE_DASHBOARD:
                if state.show_axis_selector:
                    if not axis_selector_rect.collidepoint(mouse_pos) and not btn_axis_gear.check_hover(mouse_pos):
                        state.show_axis_selector = False
                    elif axis_selector_rect.collidepoint(mouse_pos) and state.plot_context:
                        # ... Axis Selection Logic ... (Same as before)
                        df_ref = state.plot_context['df']
                        numeric_cols = df_ref.select_dtypes(include=['number']).columns
                        local_y = mouse_pos[1] - 160
                        idx = local_y // 25
                        if 0 <= idx < len(numeric_cols):
                            col_name = numeric_cols[idx]
                            if 850 <= mouse_pos[0] < 950: 
                                threading.Thread(target=load_experiment_worker, args=(state.selected_ids, col_name, state.plot_context.get('y_col'), True), daemon=True).start()
                            else:
                                threading.Thread(target=load_experiment_worker, args=(state.selected_ids, state.plot_context.get('x_col'), col_name, True), daemon=True).start()

                elif state.show_conversion_dialog:
                    if btn_conv_yes.check_hover(mouse_pos):
                        file_path, col, unit = state.pending_conversion
                        threading.Thread(target=perform_conversion_worker, args=(file_path, col, unit, state.selected_ids), daemon=True).start()
                    elif btn_conv_no.check_hover(mouse_pos):
                        state.show_conversion_dialog = False

                else:
                    # MENU ACTIONS
                    if btn_menu_analyze.check_hover(mouse_pos):
                        threading.Thread(target=analyze_branch_worker, daemon=True).start()
                    
                    if btn_menu_edit.check_hover(mouse_pos):
                        if len(state.selected_ids) == 1:
                            # START EDITOR
                            raw = db.get_experiment_by_id(state.selected_ids[0])
                            editor_file_path = raw[3]
                            editor_df = pd.read_csv(editor_file_path)
                            current_state = STATE_EDITOR
                            editor_selected_cell = None
                            state.status_msg = "EDITING MODE ACTIVE"
                        else:
                            state.status_msg = "SELECT 1 NODE TO EDIT"

                    if btn_menu_file.check_hover(mouse_pos):
                        # Simple File Menu: Just Export for now
                        threading.Thread(target=export_project_worker, args=(selected_project_path,), daemon=True).start()

                    # Standard Buttons
                    if btn_axis_gear.check_hover(mouse_pos): state.show_axis_selector = not state.show_axis_selector
                    
                    if len(state.selected_ids) == 1 and btn_add_manual.check_hover(mouse_pos):
                        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
                        if path: threading.Thread(target=process_new_file_worker, args=(path, state.selected_ids[0], state.active_branch), daemon=True).start()
                    
                    elif len(state.selected_ids) == 1 and btn_edit_meta.check_hover(mouse_pos): is_editing_metadata = not is_editing_metadata
                    
                    elif is_editing_metadata and btn_save_meta.check_hover(mouse_pos):
                        db.update_metadata(state.selected_ids[0], meta_input_notes, meta_input_temp, meta_input_sid)
                        is_editing_metadata = False
                        threading.Thread(target=load_experiment_worker, args=(state.selected_ids,), daemon=True).start()
                    
                    elif btn_snapshot_export.check_hover(mouse_pos):
                        threading.Thread(target=export_project_worker, args=(selected_project_path,), daemon=True).start()
                    elif btn_branch.check_hover(mouse_pos):
                        new_branch = simpledialog.askstring("New Branch", "Name:")
                        if new_branch:
                            state.active_branch = new_branch
                            state.status_msg = f"BRANCH: {new_branch}"
                    elif btn_export.check_hover(mouse_pos):
                        if state.current_analysis:
                            path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
                            if path:
                                try:
                                    temp_img = "temp_plot_export.png"
                                    if state.current_plot: pygame.image.save(state.current_plot, temp_img)
                                    export_to_report(path, state.current_analysis, state.active_branch, temp_img)
                                    if os.path.exists(temp_img): os.remove(temp_img)
                                    state.status_msg = "REPORT GENERATED."
                                except Exception as e: state.status_msg = f"ERROR: {e}"
                    else:
                        selected_list = tree_ui.handle_click(event.pos, (20, 80, 800, 600))
                        if selected_list: threading.Thread(target=load_experiment_worker, args=(selected_list,), daemon=True).start()

            # SPLASH / ONBOARDING CLICKS
            elif current_state == STATE_SPLASH:
                if not show_login_box:
                    if btn_new.check_hover(mouse_pos):
                        path = filedialog.askdirectory()
                        if path:
                            selected_project_path = path
                            init_project(path)
                            load_database_safe(os.path.join(path, "project_vault.db"))
                            show_login_box = True
                    elif btn_load.check_hover(mouse_pos):
                        path = filedialog.askdirectory()
                        if path:
                            if os.path.exists(os.path.join(path, "project_vault.db")):
                                selected_project_path = path
                                load_database_safe(os.path.join(path, "project_vault.db"))
                                show_login_box = True
                    elif btn_import.check_hover(mouse_pos):
                        file_path = filedialog.askopenfilename(filetypes=[("DB", "*.db")])
                        if file_path:
                            selected_project_path = os.path.dirname(file_path)
                            load_database_safe(file_path)
                            show_login_box = True
                else:
                    if btn_confirm.check_hover(mouse_pos):
                        if len(researcher_name) >= 2:
                            watcher = start_watcher(os.path.join(selected_project_path, "data"), event_queue)
                            tree_data = db.get_tree_data()
                            if not tree_data: current_state = STATE_ONBOARDING
                            else: 
                                tree_ui.update_tree(tree_data)
                                current_state = STATE_DASHBOARD

            elif current_state == STATE_ONBOARDING:
                if btn_onboard_upload.check_hover(mouse_pos):
                    path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
                    if path:
                        threading.Thread(target=process_new_file_worker, args=(path, None, "main"), daemon=True).start()
                        current_state = STATE_DASHBOARD
                elif btn_skip_onboarding.check_hover(mouse_pos): current_state = STATE_DASHBOARD

        # --- KEYBOARD (Global) ---
        if event.type == pygame.KEYDOWN:
            if current_state == STATE_SPLASH and show_login_box:
                if event.key == pygame.K_BACKSPACE: researcher_name = researcher_name[:-1]
                else: researcher_name += event.unicode
            elif search_active:
                if event.key == pygame.K_BACKSPACE: search_text = search_text[:-1]
                else: search_text += event.unicode
                tree_ui.search_filter = search_text
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

        if current_state == STATE_DASHBOARD:
            if event.type == pygame.MOUSEWHEEL: tree_ui.handle_zoom("in" if event.y > 0 else "out")
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2: tree_ui.is_panning = True
            if event.type == pygame.MOUSEBUTTONUP and event.button == 2: tree_ui.is_panning = False
            if event.type == pygame.MOUSEMOTION and tree_ui.is_panning: tree_ui.camera_offset += pygame.Vector2(event.rel)

    # --- DRAWING ---
    if current_state == STATE_SPLASH:
        screen.fill(UITheme.BG_LOGIN)
        if logo_img: screen.blit(logo_img, logo_img.get_rect(center=(SCREEN_CENTER_X, 230)))
        if not show_login_box:
            for b in [btn_new, btn_load, btn_import]:
                b.check_hover(mouse_pos)
                b.draw(screen, font_main)
        else:
            box_rect = pygame.Rect(SCREEN_CENTER_X - 225, 380, 450, 240)
            pygame.draw.rect(screen, (20, 20, 35), box_rect, border_radius=10)
            UITheme.draw_bracket(screen, box_rect, UITheme.ACCENT_ORANGE)
            screen.blit(font_bold.render("RESEARCHER IDENTITY", True, (255, 255, 255)), (SCREEN_CENTER_X - 100, 410))
            input_rect = pygame.Rect(SCREEN_CENTER_X - 190, 450, 380, 45)
            pygame.draw.rect(screen, (10, 10, 20), input_rect)
            pygame.draw.rect(screen, UITheme.ACCENT_ORANGE, input_rect, 2)
            screen.blit(font_bold.render(researcher_name + "|", True, (255, 255, 255)), (input_rect.x + 10, input_rect.y + 12))
            btn_confirm.check_hover(mouse_pos)
            btn_confirm.draw(screen, font_main)

    elif current_state == STATE_ONBOARDING:
        screen.fill(UITheme.BG_DARK)
        UITheme.draw_grid(screen)
        if logo_img: screen.blit(logo_img, logo_img.get_rect(center=(SCREEN_CENTER_X, 200)))
        msg1 = font_header.render("WELCOME TO THE LAB", True, (255, 255, 255))
        msg2 = font_bold.render("To begin, please upload your first experimental CSV file.", True, UITheme.TEXT_DIM)
        screen.blit(msg1, (SCREEN_CENTER_X - msg1.get_width()//2, 320))
        screen.blit(msg2, (SCREEN_CENTER_X - msg2.get_width()//2, 370))
        btn_onboard_upload.check_hover(mouse_pos)
        btn_onboard_upload.draw(screen, font_main)
        btn_skip_onboarding.check_hover(mouse_pos)
        btn_skip_onboarding.draw(screen, font_main)

    elif current_state == STATE_EDITOR:
        screen.fill((10, 10, 12))
        UITheme.draw_grid(screen)
        
        # Header
        pygame.draw.rect(screen, UITheme.PANEL_GREY, (0, 0, 1280, 60))
        screen.blit(font_bold.render(f"EDITING: {os.path.basename(editor_file_path)}", True, UITheme.ACCENT_ORANGE), (20, 20))
        screen.blit(font_main.render("Use Arrow Keys to Scroll | Enter to Confirm Cell | Save to Commit", True, UITheme.TEXT_DIM), (500, 22))

        # DRAW SPREADSHEET
        start_x = 50
        start_y = 100
        cell_w = 100
        cell_h = 30
        
        # Draw Columns
        cols = editor_df.columns
        for c_idx, col_name in enumerate(cols):
            cx = start_x + (c_idx * cell_w)
            if cx > 1200: break
            pygame.draw.rect(screen, (40, 40, 50), (cx, start_y - 30, cell_w, 30))
            pygame.draw.rect(screen, (80, 80, 80), (cx, start_y - 30, cell_w, 30), 1)
            screen.blit(font_small.render(col_name[:12], True, (255, 255, 255)), (cx + 5, start_y - 25))

        # Draw Rows
        row_limit = 15 # Visible rows
        visible_df = editor_df.iloc[int(editor_scroll_y):int(editor_scroll_y)+row_limit]
        
        for r_idx, (idx, row) in enumerate(visible_df.iterrows()):
            actual_row_idx = int(editor_scroll_y) + r_idx
            ry = start_y + (r_idx * cell_h)
            
            # Row Number
            screen.blit(font_small.render(str(actual_row_idx), True, UITheme.TEXT_DIM), (10, ry + 8))
            
            for c_idx, val in enumerate(row):
                cx = start_x + (c_idx * cell_w)
                if cx > 1200: break
                
                rect = pygame.Rect(cx, ry, cell_w, cell_h)
                
                # Check Selection
                is_selected = editor_selected_cell == (actual_row_idx, c_idx)
                
                bg_col = (20, 20, 25)
                if is_selected: bg_col = (0, 60, 100)
                
                pygame.draw.rect(screen, bg_col, rect)
                pygame.draw.rect(screen, (50, 50, 60), rect, 1)
                
                # Render Value
                display_val = editor_input_buffer if is_selected else str(val)
                screen.blit(font_main.render(display_val[:12], True, (255, 255, 255)), (cx + 5, ry + 5))
                
                if is_selected:
                    pygame.draw.rect(screen, UITheme.ACCENT_ORANGE, rect, 2)

        btn_editor_save.check_hover(mouse_pos)
        btn_editor_save.draw(screen, font_bold)
        btn_editor_exit.check_hover(mouse_pos)
        btn_editor_exit.draw(screen, font_bold)

    elif current_state == STATE_DASHBOARD:
        if not event_queue.empty() and not state.is_processing:
            ev = event_queue.get()
            if ev["type"] == "NEW_FILE":
                threading.Thread(target=process_new_file_worker, args=(ev["path"], state.head_id, state.active_branch), daemon=True).start()
        if state.needs_tree_update:
            tree_ui.update_tree(db.get_tree_data())
            state.needs_tree_update = False

        screen.fill(UITheme.BG_DARK)
        UITheme.draw_grid(screen)
        
        # HEADER
        pygame.draw.rect(screen, UITheme.PANEL_GREY, (0, 0, 1280, 70))
        pygame.draw.line(screen, UITheme.ACCENT_ORANGE, (0, 70), (1280, 70), 2)
        screen.blit(font_bold.render(f"SCI-GIT // {os.path.basename(selected_project_path).upper()} // {researcher_name.upper()}", True, UITheme.ACCENT_ORANGE), (20, 10))
        
        # MENU BAR
        for b in [btn_menu_file, btn_menu_edit, btn_menu_analyze]:
            b.check_hover(mouse_pos)
            b.draw(screen, font_small)

        # SEARCH BAR
        search_rect = pygame.Rect(850, 45, 200, 20)
        pygame.draw.rect(screen, (10, 10, 15), search_rect)
        pygame.draw.rect(screen, (UITheme.ACCENT_ORANGE if search_active else (50, 50, 60)), search_rect, 1)
        screen.blit(font_small.render("SEARCH:", True, UITheme.TEXT_DIM), (800, 48))
        screen.blit(font_small.render(search_text + ("|" if search_active else ""), True, (255, 255, 255)), (855, 48))

        # AI STATUS & MSG
        ai_status = "AI ONLINE" if ai_engine.client else "AI OFFLINE"
        ai_col = (0, 255, 150) if ai_engine.client else (200, 50, 50)
        screen.blit(font_main.render(ai_status, True, ai_col), (1150, 10))
        screen.blit(font_main.render(f"> {state.status_msg}", True, UITheme.TEXT_DIM), (850, 15))

        tree_surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        tree_ui.draw(tree_surf, mouse_pos)
        screen.blit(tree_surf, (20, 80))
        UITheme.draw_bracket(screen, (20, 80, 800, 600), UITheme.ACCENT_ORANGE)

        # Context Icons
        if len(state.selected_ids) == 1:
            for node in tree_ui.nodes:
                if node["id"] == state.selected_ids[0]:
                    pos = (node["pos"] * tree_ui.zoom_level) + tree_ui.camera_offset
                    mx, my = pos.x + 45, pos.y + 60
                    btn_add_manual.rect.topleft = (mx, my)
                    btn_edit_meta.rect.topleft = (mx, my + 40)
                    btn_add_manual.check_hover(mouse_pos)
                    btn_add_manual.draw(screen, font_main)
                    btn_edit_meta.check_hover(mouse_pos)
                    btn_edit_meta.draw(screen, font_main)

        side_rect = (840, 80, 420, 600)
        pygame.draw.rect(screen, UITheme.PANEL_GREY, side_rect)
        UITheme.draw_bracket(screen, side_rect, (100, 100, 100))

        if not is_editing_metadata:
            if state.current_plot: 
                screen.blit(state.current_plot, (850, 100))
                plot_rect = pygame.Rect(850, 100, 400, 300)
                pygame.draw.rect(screen, (50, 50, 55), plot_rect, 1)
                
                btn_axis_gear.check_hover(mouse_pos)
                btn_axis_gear.draw(screen, font_bold)

                if plot_rect.collidepoint(mouse_pos) and state.plot_context:
                    rel_x = (mouse_pos[0] - 850) / 400.0
                    rel_x = max(0, min(1, rel_x)) 
                    ctx = state.plot_context
                    df = ctx['df']
                    if not df.empty:
                        idx = int(rel_x * (len(df) - 1))
                        row = df.iloc[idx]
                        x_val = row[ctx['x_col']] if ctx.get('x_col') else idx
                        y_val = row[ctx['y_col']] if ctx.get('y_col') else "N/A"
                        tt_text = f"X: {x_val} | Y: {y_val}"
                        tt_surf = font_small.render(tt_text, True, (255, 255, 255))
                        tt_bg = pygame.Rect(mouse_pos[0] + 10, mouse_pos[1] + 10, tt_surf.get_width() + 10, 20)
                        pygame.draw.rect(screen, (20, 20, 25), tt_bg)
                        pygame.draw.rect(screen, UITheme.ACCENT_ORANGE, tt_bg, 1)
                        screen.blit(tt_surf, (tt_bg.x + 5, tt_bg.y + 3))

                if state.show_axis_selector and state.plot_context:
                    pygame.draw.rect(screen, (15, 15, 20), axis_selector_rect)
                    pygame.draw.rect(screen, (80, 80, 90), axis_selector_rect, 2)
                    screen.blit(font_bold.render("AXIS SELECTION", True, UITheme.ACCENT_ORANGE), (860, 135))
                    screen.blit(font_small.render("CLICK COL TO SET: [ X ]  [ Y ]", True, UITheme.TEXT_DIM), (860, 150))
                    df = state.plot_context['df']
                    numeric_cols = df.select_dtypes(include=['number']).columns
                    y_off = 160
                    for col in numeric_cols:
                        is_x = col == state.plot_context.get('x_col')
                        is_y = col == state.plot_context.get('y_col')
                        col_col = (255, 255, 255)
                        if is_x: col_col = (255, 120, 0)
                        if is_y: col_col = (0, 255, 255)
                        row_rect = pygame.Rect(850, y_off, 200, 25)
                        if row_rect.collidepoint(mouse_pos): pygame.draw.rect(screen, (30, 30, 40), row_rect)
                        screen.blit(font_main.render(col[:20], True, col_col), (860, y_off + 4))
                        if is_x: screen.blit(font_small.render("[X]", True, col_col), (980, y_off + 6))
                        if is_y: screen.blit(font_small.render("[Y]", True, col_col), (1010, y_off + 6))
                        y_off += 25

            if state.current_analysis:
                UITheme.render_terminal_text(screen, state.current_analysis.get('summary', ""), (855, 420), font_main, UITheme.TEXT_OFF_WHITE, 390)
                if len(state.selected_ids) == 1:
                    meta_txt = f"NOTE: {meta_input_notes}\nTEMP: {meta_input_temp} | ID: {meta_input_sid}"
                    if meta_input_notes or meta_input_temp:
                        UITheme.render_terminal_text(screen, meta_txt, (855, 550), font_main, UITheme.ACCENT_ORANGE, 390)
        else:
            screen.blit(font_bold.render("MANUAL DATA ENTRY", True, UITheme.ACCENT_ORANGE), (855, 100))
            y_ptr = 150
            for label, key in [("NOTES:", "notes"), ("TEMP (°C):", "temp"), ("SAMPLE ID:", "sid")]:
                screen.blit(font_main.render(label, True, UITheme.TEXT_DIM), (855, y_ptr))
                rect = pygame.Rect(855, y_ptr + 20, 390, 35)
                pygame.draw.rect(screen, (10, 10, 15), rect)
                pygame.draw.rect(screen, (UITheme.ACCENT_ORANGE if active_field == key else (50, 50, 60)), rect, 1)
                val = meta_input_notes if key == "notes" else (meta_input_temp if key == "temp" else meta_input_sid)
                screen.blit(font_main.render(val + ("|" if active_field == key else ""), True, (255, 255, 255)), (860, y_ptr + 28))
                if pygame.mouse.get_pressed()[0] and rect.collidepoint(mouse_pos): active_field = key
                y_ptr += 80
            btn_save_meta.check_hover(mouse_pos)
            btn_save_meta.draw(screen, font_main)

        for b in [btn_export, btn_branch, btn_snapshot_export]:
            b.check_hover(mouse_pos)
            b.draw(screen, font_main)
        
        if state.is_processing: draw_loading_overlay(screen, font_bold)

        if state.show_conversion_dialog:
            overlay = pygame.Surface((1280, 720), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 220))
            screen.blit(overlay, (0,0))
            d_rect = pygame.Rect(440, 260, 400, 200)
            pygame.draw.rect(screen, UITheme.PANEL_GREY, d_rect)
            UITheme.draw_bracket(screen, d_rect, UITheme.ACCENT_ORANGE)
            msg1 = font_bold.render("UNIT MISMATCH DETECTED", True, UITheme.ACCENT_ORANGE)
            msg2 = font_main.render(f"Convert Secondary Node to {state.pending_conversion[2]}?", True, UITheme.TEXT_OFF_WHITE)
            msg3 = font_main.render("This updates the CSV file permanently.", True, UITheme.TEXT_DIM)
            screen.blit(msg1, (d_rect.centerx - msg1.get_width()//2, 280))
            screen.blit(msg2, (d_rect.centerx - msg2.get_width()//2, 320))
            screen.blit(msg3, (d_rect.centerx - msg3.get_width()//2, 350))
            btn_conv_yes.check_hover(mouse_pos)
            btn_conv_yes.draw(screen, font_bold)
            btn_conv_no.check_hover(mouse_pos)
            btn_conv_no.draw(screen, font_bold)

    pygame.display.flip()
    clock.tick(60)
pygame.quit()
sys.exit()