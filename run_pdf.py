import os
import sys

# Ensure backend app is in path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from backend.app.utils import convert_to_pdf

ART_DIR = os.path.join(os.path.dirname(__file__), "backend", "artifacts", "jtvyys")

prompt_md = os.path.join(ART_DIR, "Project_SOW_Prompt.md")
ref_md = os.path.join(ART_DIR, "Project_Reference_List_Complete.md")

prompt_pdf = os.path.join(ART_DIR, "Project_SOW_Prompt.pdf")
ref_pdf = os.path.join(ART_DIR, "Project_Reference_List_Complete.pdf")

print("Generating SOW Prompt PDF...")
convert_to_pdf(prompt_md, prompt_pdf)

print("Generating Reference List PDF...")
convert_to_pdf(ref_md, ref_pdf)

print("PDFs Generated Successfully!")
