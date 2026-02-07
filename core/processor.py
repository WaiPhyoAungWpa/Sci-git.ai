from fpdf import FPDF
import os

class PDFReport(FPDF):
    def header(self):
        self.set_font('Courier', 'B', 12)
        self.cell(0, 10, 'SCI-GIT // AUTOMATED RESEARCH LOG', 0, 1, 'R')
        self.line(10, 20, 200, 20)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Courier', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def export_to_report(filename, analysis_dict, branch_name, plot_image_path=None):
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font("Courier", "B", 16)
    pdf.cell(0, 10, f"EXPERIMENTAL REPORT: {branch_name}", ln=True, align='L')
    pdf.ln(5)
    
    if plot_image_path and os.path.exists(plot_image_path):
        pdf.image(plot_image_path, x=10, w=190)
        pdf.ln(5)
    
    pdf.set_font("Courier", "B", 12)
    pdf.cell(0, 10, "AI ANALYSIS SUMMARY:", ln=True)
    pdf.set_font("Courier", "", 11)
    summary_text = analysis_dict.get('summary', 'No summary available.')
    pdf.multi_cell(0, 6, summary_text)
    pdf.ln(5)
    
    anomalies = analysis_dict.get('anomalies', [])
    if anomalies:
        pdf.set_font("Courier", "B", 12)
        pdf.cell(0, 10, "DETECTED ANOMALIES:", ln=True)
        pdf.set_font("Courier", "", 11)
        for item in anomalies:
            pdf.cell(0, 6, f"[!] {item}", ln=True)
    
    try:
        pdf.output(filename)
        return True
    except Exception as e:
        print(f"PDF Generation Error: {e}")
        return False