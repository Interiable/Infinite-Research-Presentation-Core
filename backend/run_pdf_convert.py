import os
from app.utils import convert_to_pdf

en_path = "/home/hgeon/gravity/LangAIAgent/backend/artifacts/krjgg8/20260319_095708_project_master_report_en.md"
ko_path = "/home/hgeon/gravity/LangAIAgent/backend/artifacts/krjgg8/20260319_101246_project_master_report_ko.md"

if os.path.exists(en_path):
    print("Converting EN to PDF...")
    convert_to_pdf(en_path)

if os.path.exists(ko_path):
    print("Converting KO to PDF...")
    convert_to_pdf(ko_path)
