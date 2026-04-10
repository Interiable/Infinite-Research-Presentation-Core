import sys
from pypdf import PdfReader, PdfWriter

file_path = "/home/hgeon/gravity/LangAIAgent/backend/artifacts/jtvyys/Project_SOW_Prompt.pdf"

reader = PdfReader(file_path)
writer = PdfWriter()

# Keep all pages except the 6th page (index 5)
for i in range(len(reader.pages)):
    if i != 5:  # Page 6 is at index 5
        writer.add_page(reader.pages[i])

with open(file_path, "wb") as f:
    writer.write(f)

print(f"Successfully processed {file_path}. Total pages now: {len(writer.pages)}")
