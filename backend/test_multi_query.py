import requests
import json

prompt = f"""You are a Search Query Specialist. Generate 1 to 3 distinct search queries for web search engines.

**TASK**: Read the research context and generate up to 3 distinct search queries. If the topic contains distinctly different theoretical concepts and brand names, split them into separate focused queries to avoid concept blending.

**RULES:**
1. OUTPUT MUST BE A VALID JSON ARRAY OF STRINGS: ["query 1", "query 2"]
2. Maximum 3 queries.
3. For brand-specific queries, ALWAYS preserve proper nouns (e.g., "Samsung Design Mauro Porcini").
4. For pure theoretical or methodological topics (e.g., "PESO model framework", "Media tiering definition"), output a SEPARATE query WITHOUT the brand name to ensure proper academic/methodological extraction.
5. Do NOT include markdown code blocks, just the raw JSON array.

Original Research Goal: Samsung Design Media Tracking for Mauro Porcini's impact from 2025-2026.
Current Sub-topic: Define the P.E.S.O. (Paid, Earned, Shared, Owned) classification model and Media Tiering (Tier 1, Tier 2, Tier 3) framework.

JSON Output:"""

print("Invoking local_llm (Ollama gemma4:31b)...")
response = requests.post("http://127.0.0.1:11434/api/generate", json={
    "model": "gemma4:31b",
    "prompt": prompt,
    "stream": False
})

raw_res = response.json().get("response", "").strip()

print("\n--- RAW LLM OUTPUT ---")
print(raw_res)
print("----------------------\n")

if '</think>' in raw_res:
    raw_res = raw_res.split('</think>')[-1].strip()
raw_res = raw_res.replace('```json', '').replace('```', '').strip()

try:
    queries_list = json.loads(raw_res)
    print("✅ PARSED JSON SUCCESS!")
    print("Parsed Queries List:")
    for i, q in enumerate(queries_list):
        print(f"   [{i+1}] {q}")
except Exception as e:
    print("❌ JSON DECODE ERROR:", e)
    print("Fallback active: will use raw string as single query.")
