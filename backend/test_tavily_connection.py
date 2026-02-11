
import os
from dotenv import load_dotenv
from langchain_community.tools.tavily_search import TavilySearchResults

# Load environment variables
load_dotenv()

def test_tavily_connection():
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("❌ TAVILY_API_KEY not found in .env")
        return

    print(f"🔑 API Key found (starts with: {api_key[:5]}...)")
    
    try:
        search = TavilySearchResults(
            max_results=3,
            search_depth="advanced",
            include_answer=True,
            include_raw_content=True
        )
        
        query = "Physical AI Presence & Motion Research 2025 trends"
        print(f"🌍 Performing test search for: '{query}'")
        
        results = search.invoke(query)
        
        if results and isinstance(results, list):
            print(f"✅ Success! Found {len(results)} results.")
            for i, res in enumerate(results):
                print(f"\n--- Result {i+1} ---")
                print(f"URL: {res.get('url')}")
                print(f"Content Snippet: {res.get('content')[:200]}...")
        else:
            print("⚠️ No results returned from Tavily.")
            print(f"Raw Output: {results}")

    except Exception as e:
        print(f"❌ Tavily Search Failed: {e}")

if __name__ == "__main__":
    test_tavily_connection()
