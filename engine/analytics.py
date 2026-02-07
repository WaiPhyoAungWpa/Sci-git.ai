import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import seaborn as sns
import pygame
import pandas as pd
import re
from settings import UITheme

# --- HEADER SCANNER & CONVERSION UTILS ---
class HeaderScanner:
    @staticmethod
    def detect_temp_unit(df):
        """Returns ('C', col_name) or ('F', col_name) or None."""
        for col in df.columns:
            # Regex for _C, (C), Celsius or _F, (F), Fahrenheit
            if re.search(r'(_|\()C(\)|$)|Celsius', col, re.IGNORECASE):
                return 'C', col
            if re.search(r'(_|\()F(\)|$)|Fahrenheit', col, re.IGNORECASE):
                return 'F', col
        return None, None

    @staticmethod
    def convert_column(df, col_name, to_unit):
        """Performs math conversion in place."""
        if to_unit == 'C':
            # F to C: (F - 32) * 5/9
            df[col_name] = (df[col_name] - 32) * 5.0/9.0
            # Rename header to reflect change
            new_col = re.sub(r'F(ahrenheit)?', 'C', col_name, flags=re.IGNORECASE)
            df.rename(columns={col_name: new_col}, inplace=True)
        elif to_unit == 'F':
            # C to F: (C * 9/5) + 32
            df[col_name] = (df[col_name] * 9.0/5.0) + 32
            new_col = re.sub(r'C(elsius)?', 'F', col_name, flags=re.IGNORECASE)
            df.rename(columns={col_name: new_col}, inplace=True)
        return df

def create_seaborn_surface(df1, df2=None, width=400, height=300):
    """Generates a Seaborn plot for 1 or 2 DataFrames."""
    try:
        fig = Figure(figsize=(width/80, height/80), dpi=80, facecolor='#16161a')
        canvas = FigureCanvasAgg(fig)

        # Style params
        line_colors = ['#ff7800', '#00d4ff'] # Orange (Primary), Cyan (Secondary)
        
        if df2 is None:
            # --- SINGLE MODE ---
            ax = fig.add_subplot(111)
            ax.set_facecolor('#0d0d0f')
            
            numeric_cols = df1.select_dtypes(include=['number']).columns
            if len(numeric_cols) >= 2:
                sns.lineplot(data=df1, x=numeric_cols[0], y=numeric_cols[1], 
                             ax=ax, color=line_colors[0], linewidth=2)
                ax.set_title(f"ANALYSIS: {numeric_cols[0]} vs {numeric_cols[1]}", 
                             color=line_colors[0], fontsize=10, family='monospace')
            else:
                ax.text(0.5, 0.5, "INSUFFICIENT DATA", color='gray', ha='center', va='center')
                
        else:
            # --- DUAL MODE ---
            cols1 = df1.select_dtypes(include=['number']).columns
            cols2 = df2.select_dtypes(include=['number']).columns
            
            # Check compatibility (Simplified: Do they have the same column names?)
            common_cols = [c for c in cols1 if c in cols2]
            
            if len(common_cols) >= 2:
                # --- OVERLAY MODE ---
                ax = fig.add_subplot(111)
                ax.set_facecolor('#0d0d0f')
                
                # Plot Primary
                sns.lineplot(data=df1, x=common_cols[0], y=common_cols[1], 
                             ax=ax, color=line_colors[0], linewidth=2, label="Primary")
                # Plot Secondary
                sns.lineplot(data=df2, x=common_cols[0], y=common_cols[1], 
                             ax=ax, color=line_colors[1], linewidth=2, label="Secondary")
                
                ax.set_title("COMPARATIVE OVERLAY", color='#ffffff', fontsize=10, family='monospace')
                ax.legend(facecolor='#16161a', edgecolor='#333333', labelcolor='white')
            
            else:
                # --- SIDE-BY-SIDE MODE (Mismatch) ---
                # Top Plot (Primary)
                ax1 = fig.add_subplot(211)
                ax1.set_facecolor('#0d0d0f')
                if len(cols1) >= 2:
                    sns.lineplot(data=df1, x=cols1[0], y=cols1[1], ax=ax1, color=line_colors[0])
                    ax1.set_title(f"A: {cols1[1]}", color=line_colors[0], fontsize=8)
                
                # Bottom Plot (Secondary)
                ax2 = fig.add_subplot(212)
                ax2.set_facecolor('#0d0d0f')
                if len(cols2) >= 2:
                    sns.lineplot(data=df2, x=cols2[0], y=cols2[1], ax=ax2, color=line_colors[1])
                    ax2.set_title(f"B: {cols2[1]}", color=line_colors[1], fontsize=8)
                
                fig.tight_layout()

        # Common Axis Styling
        for ax in fig.axes:
            ax.tick_params(colors='#888888', labelsize=8)
            for spine in ax.spines.values():
                spine.set_edgecolor('#333333')

        canvas.draw()
        rgba_buffer = canvas.buffer_rgba()
        return pygame.image.frombuffer(rgba_buffer, canvas.get_width_height(), "RGBA")

    except Exception as e:
        print(f"Plotting Error: {e}")
        surf = pygame.Surface((width, height))
        surf.fill((30, 30, 35))
        return surf