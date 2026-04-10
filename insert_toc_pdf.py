"""
목차(TOC) 페이지만 PDF로 생성한 뒤 기존 PDF의 본문 부분 앞에 새 TOC를 삽입합니다.
기존 PDF에서 이전 TOC 페이지들을 제거합니다.
"""
import asyncio
import markdown
import os
from playwright.async_api import async_playwright
from pypdf import PdfWriter, PdfReader

original_pdf = "/home/hgeon/gravity/LangAIAgent/backend/artifacts/9zsvx/00_Project_Recursive_Master_Report.pdf"
output_pdf   = "/home/hgeon/gravity/LangAIAgent/backend/artifacts/9zsvx/00_Project_Recursive_Master_Report.pdf"
bak_pdf      = "/home/hgeon/gravity/LangAIAgent/backend/artifacts/9zsvx/00_Project_Recursive_Master_Report.bak.pdf"
toc_only_pdf = "/tmp/toc_only.pdf"
toc_only_html = "/tmp/toc_only.html"

# ── 1. MD 파일에서 TOC 섹션만 추출 ──────────────────────────────
md_path = "/home/hgeon/gravity/LangAIAgent/backend/artifacts/9zsvx/00_Project_Recursive_Master_Report.md"
with open(md_path, encoding="utf-8") as f:
    lines = f.readlines()

toc_lines = []
in_toc = False
for line in lines:
    stripped = line.strip()
    if stripped == "## Table of Contents":
        in_toc = True
        toc_lines.append(line)
        continue
    if in_toc:
        if (stripped.startswith("# ") and stripped != "## Table of Contents") or stripped.startswith("<!--"):
            break
        toc_lines.append(line)

toc_md = "# Project 9zsvx Recursive Master Report\n\n" + "".join(toc_lines)
print(f"TOC section extracted: {len(toc_lines)} lines")

# ── 2. TOC만 HTML → PDF ──────────────────────────────────────────
html_body = markdown.markdown(toc_md, extensions=["tables", "fenced_code"])

html_doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
       padding: 40px; font-size: 13px; line-height: 1.7; color: #222; }}
h1 {{ color: #111; border-bottom: 2px solid #ccc; padding-bottom: 6px; margin-bottom: 20px; font-size: 20px; }}
h2 {{ color: #333; border-bottom: 1px solid #ddd; margin-top: 24px; margin-bottom: 12px; font-size: 16px; }}
h3 {{ color: #444; margin-top: 18px; margin-bottom: 8px; font-size: 14px; }}
ul {{ padding-left: 20px; }}
li {{ margin-bottom: 4px; }}
strong {{ color: #0a58ca; }}
a {{ color: #0969da; text-decoration: none; }}
p {{ margin: 4px 0 10px 0; color: #555; font-style: italic; font-size: 12px; }}
hr {{ border: none; border-top: 1px solid #eee; margin: 20px 0; }}
</style>
</head><body>
{html_body}
</body></html>"""

with open(toc_only_html, "w", encoding="utf-8") as f:
    f.write(html_doc)

async def render_toc_pdf():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"file://{toc_only_html}", wait_until="networkidle")
        await page.pdf(
            path=toc_only_pdf,
            format="A4",
            print_background=True,
            margin={"top": "20mm", "bottom": "20mm", "left": "20mm", "right": "20mm"}
        )
        await browser.close()
    print("TOC PDF rendered.")

asyncio.run(render_toc_pdf())

# ── 3. 원본 PDF에서 기존 TOC 제외한 본문 시작 페이지 찾기 ─────────
# 현재 output_pdf 는 이미 (new_toc + old_pdf) 형태이므로,
# 원본 PDF는 .bak.pdf 에서 찾거나 백업해서 써야 합니다.
# 현재 output_pdf에서 진행 중이라면, .bak이 있는지 확인합니다.

import shutil

# bak_pdf가 없으면 현재 파일을 bak으로 보관하고 작업
if not os.path.exists(bak_pdf):
    shutil.copy(original_pdf, bak_pdf)
    print(f"Backed up original to {bak_pdf}")

# bak.pdf 에서 본문 시작 페이지 탐색
bak_reader = PdfReader(bak_pdf)
toc_reader  = PdfReader(toc_only_pdf)

print(f"BAK PDF total pages: {len(bak_reader.pages)}")
print(f"New TOC pages: {len(toc_reader.pages)}")

# 본문 탐색 - "Step 1.1" 내용이 시작되는 첫 페이지 찾기
# 기존 TOC는 "Table of Contents"로 시작하나, 본문은 "1.1.1 Selection..." 등으로 시작
body_start_page = 0
TOC_KEYWORDS = ["Table of Contents", "Step 1 —", "Step 2 —", "Step 3 —", "Step 4 —",
                 "Step 5 —", "Step 6 —", "Step 7 —"]
BODY_KEYWORDS = ["Deep Report:", "Hardware-Model Alignment", "YOLOv8", "Research Report",
                  "Step 1.1 Research", "Selection of State-of-the-Art"]

for i, page in enumerate(bak_reader.pages):
    text = (page.extract_text() or "").strip()
    is_toc = any(kw in text for kw in TOC_KEYWORDS) and not any(bk in text for bk in BODY_KEYWORDS)
    is_body = any(bk in text for bk in BODY_KEYWORDS)
    print(f"  Page {i+1}: is_toc={is_toc}, is_body={is_body} | {text[:80].replace(chr(10),'|')[:60]}")
    if is_body:
        body_start_page = i
        break

print(f"\nBody starts at page {body_start_page + 1} in BAK PDF")

# ── 4. 새 PDF 조합: 새 TOC + 본문 ──────────────────────────────
writer = PdfWriter()
for page in toc_reader.pages:
    writer.add_page(page)
for i, page in enumerate(bak_reader.pages):
    if i >= body_start_page:
        writer.add_page(page)

with open(output_pdf, "wb") as f:
    writer.write(f)

print(f"\nDone! Final PDF: {output_pdf}")
print(f"  New TOC pages: {len(toc_reader.pages)}")
print(f"  Body pages from BAK: {len(bak_reader.pages) - body_start_page}")
print(f"  Total: {len(toc_reader.pages) + len(bak_reader.pages) - body_start_page} pages")

os.remove(toc_only_html)
os.remove(toc_only_pdf)
