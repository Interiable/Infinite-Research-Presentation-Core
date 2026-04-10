import re
import os
import urllib.request
from collections import defaultdict

artifact_dir = "/home/hgeon/gravity/LangAIAgent/backend/artifacts/9e0ioe"
report_path = "/home/hgeon/gravity/LangAIAgent/backend/results/9e0ioe/00_Project_Recursive_Master_Report.md"

# 1. Iteration Analysis
files = os.listdir(artifact_dir)
chapter_versions = defaultdict(list)
for f in files:
    match = re.search(r'step(\d+)_sub(\d+)_ch(\d+)_v(\d+)\.md', f)
    if match:
        step, sub, ch, v = match.groups()
        key = f"Step {step}.{sub} Ch {ch}"
        chapter_versions[key].append(int(v))

iteration_counts = [max(v) for v in chapter_versions.values()]
if iteration_counts:
    avg_iterations = sum(iteration_counts) / len(iteration_counts)
    max_iter = max(iteration_counts)
else:
    avg_iterations = 0
    max_iter = 0

print(f"Total Chapters Written: {len(chapter_versions)}")
print(f"Average Iterations per Chapter: {avg_iterations:.2f}")
print(f"Max Iterations for a single chapter: {max_iter}")
print(f"Total Artifacts generated: {len(files)}")

# 2. Extract Links and Check Fakes
with open(report_path, 'r', encoding='utf-8') as f:
    content = f.read()

urls = re.findall(r'https?://[^\s\]\>]+', content)
unique_urls = set(urls)
print(f"\nFound {len(unique_urls)} unique URLs.")
dummy_patterns = ['example.com', 'yourdomain', 'placeholder', 'test.com', 'foo.bar']
fake_urls = [u for u in unique_urls if any(d in u for d in dummy_patterns)]
if fake_urls:
    print(f"⚠️ POTENTIAL FAKE URLS: {fake_urls}")
else:
    print(f"✅ No obvious dummy domains found among {len(unique_urls)} links.")

# 3. Check Sub-steps completeness
sections = re.findall(r'^## 📍 (Step \d+\.\d+.*)', content, re.MULTILINE)
print(f"\nSub-steps found in Master Report: {len(sections)}")
for s in sections:
    print(f" - {s}")

# 4. Check for YouTube Transcripts
# Searching for standard YouTube links
yt_links = [u for u in unique_urls if 'youtube.com/watch' in u or 'youtu.be/' in u]
print(f"\nFound {len(yt_links)} YouTube Links.")
no_transcripts = content.count("No transcript available")
print(f"Instances of 'No transcript available': {no_transcripts}")

