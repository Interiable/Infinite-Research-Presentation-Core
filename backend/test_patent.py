import os
import sys
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/home/hgeon/gravity/LangAIAgent/backend/.env')

# Add backend directory to sys.path so we can import app modules
sys.path.append('/home/hgeon/gravity/LangAIAgent/backend')

from app.utils.patent_researcher import PatentResearcher

def test_patent_search():
    print(f"Testing with GCP_PROJECT_ID: {os.getenv('GCP_PROJECT_ID')}")
    researcher = PatentResearcher()
    
    topic = "Vision-Language-Action robotic display"
    print(f"\n--- Extracting Keywords ---")
    keywords = researcher.extract_patent_keywords(topic)
    print(f"Keywords: {keywords}")
    
    kw = keywords[0] if keywords else "robot display"

    print(f"\n--- Testing BigQuery (Google Patents) ---")
    try:
        results = researcher.search_google_patents(kw, max_results=3)
        print(f"BigQuery Results found: {len(results)}")
        for idx, r in enumerate(results):
            print(f"  {idx+1}. {r.get('patent_number')} | {r.get('title')[:50]}...")
    except Exception as e:
        print(f"BigQuery Error: {e}")
            
    print(f"\n--- Testing USPTO ---")
    try:
        results = researcher.search_uspto(kw, max_results=3)
        print(f"USPTO Results found: {len(results)}")
    except Exception as e:
        print(f"USPTO Error: {e}")

    print(f"\n--- Testing PatentsView ---")
    try:
        results = researcher.search_patentsview(kw, max_results=3)
        print(f"PatentsView Results found: {len(results)}")
        for idx, r in enumerate(results):
            print(f"  {idx+1}. {r.get('patent_number')} | {r.get('title')[:50]}...")
    except Exception as e:
        print(f"PatentsView Error: {e}")
            
    print(f"\n--- Testing Full Text Scraping ---")
    try:
        # Fetch a known patent "US10600214B2"
        patent_id = "US10600214B2"
        print(f"Scraping Patent: {patent_id}")
        full_text_data = researcher.fetch_google_patents_fulltext(patent_id)
        print(f"Scraped Success: {full_text_data.get('scraped')}")
        print(f"Full Text Length: {len(full_text_data.get('full_text', ''))}")
    except Exception as e:
        print(f"Scraping Error: {e}")

if __name__ == '__main__':
    test_patent_search()
