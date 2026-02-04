
import re

# Simulated RAG Output (What the Planner gets)
file_overview = """
- backend/data/DMP_paper.pdf (Snippet: Dynamic Movement Primitives...)
- backend/data/UX_Guidelines.txt (Snippet: 10 rules of physical AI...)
- backend/data/complex path/with spaces.md (Snippet: content...)
- plain_file.py
"""

# The logic I added to Planner.py
print("--- PLANNER REGEX TEST ---")
found_files = re.findall(r"- (.+)", file_overview)
print(f"Found {len(found_files)} files:")
for f in found_files:
    print(f"  [{f}]")

# The logic I added to Researcher.py
print("\n--- RESEARCHER REGEX TEST ---")
# Planner usually passes the list back as a string in the context
planner_context = """
Selected Files:
- backend/data/DMP_paper.pdf (Snippet: Dynamic Movement Primitives...)
- backend/data/UX_Guidelines.txt (Snippet: 10 rules of physical AI...)
"""

raw_files = re.findall(r"- (.+)", planner_context)
available_files = []
for f in raw_files:
    # Cleanup: remove trailing parenthesis context if present
    clean_f = f.split(' (')[0].strip()
    available_files.append(clean_f)

print(f"Extracted {len(available_files)} clean filenames:")
for f in available_files:
    print(f"  [{f}]")

# Verification
expected = ["backend/data/DMP_paper.pdf", "backend/data/UX_Guidelines.txt"]
if available_files == expected:
    print("\n✅ VERIFICATION SUCCESS: Regex captures filenames correctly.")
else:
    print("\n❌ VERIFICATION FAILED: Regex mismatch.")
