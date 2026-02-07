class AppState:
    def __init__(self):
        # CHANGED: Support multiple selections
        self.selected_ids = [] 
        self.head_id = None
        self.active_branch = "main"
        
        self.current_plot = None
        self.current_analysis = None
        
        self.is_processing = False
        self.needs_tree_update = False 
        self.status_msg = "SYSTEM READY"

        # NEW: For Unit Conversion Dialog
        self.show_conversion_dialog = False
        self.pending_conversion = None # Stores (file_path, column, to_unit)

state = AppState()