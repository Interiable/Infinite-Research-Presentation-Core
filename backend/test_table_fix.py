import re

text = """**Taxonomy of Filtering Themes**
| Filtering Theme | Description & Scope | Target Application |
| :--- | :--- | :--- |
| **Design Identity** | Evaluation of Samsung’s overarching design philosophy and the "human-centered" pivot. | Brand Strategy |
"""

# Regex to find a line that does NOT start with | and is not empty,
# followed immediately by a line that DOES start with | (possibly after spaces)
# We want to insert an extra newline.
fixed_text = re.sub(r'([^\n|])\n(\s*\|)', r'\1\n\n\2', text)
print("FIXED:\n" + fixed_text)

# Also wait, what about the master report?
with open('/home/hgeon/gravity/LangAIAgent/backend/artifacts/9e0ioe/20260403_041417_project_master_report_en.md', 'r') as f:
    full_text = f.read()

fixed = re.sub(r'([^\n|])\n(\s*\|)', r'\1\n\n\2', full_text)
print("\nDifference in length:", len(fixed) - len(full_text))
