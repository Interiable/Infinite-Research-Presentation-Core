from langchain_community.tools.tavily_search import TavilySearchResults
import os
from dotenv import load_dotenv

load_dotenv()

def test_tavily():
    print("--- Testing Tavily Search API ---")
    topic = "Theory of Mind applied to Robot motion"
    print(f"🔎 Query: {topic}")
    
    try:
        search = TavilySearchResults(max_results=3)
        results = search.invoke(topic)
        
        if isinstance(results, list) and len(results) > 0:
            print(f"✅ Tavily Success! Found {len(results)} results.")
            for i, res in enumerate(results):
                title = res.get('title', 'No Title')
                url = res.get('url', '#')
                content = res.get('content', '')
                print(f"\n[Result {i+1}] {title}")
                print(f"   URL: {url}")
                print(f"   Content Length: {len(content)} characters")
                print(f"   Content Preview: {content[:1000]}...") # Show more context
            return True
        else:
            print(f"⚠️ Tavily returned empty or invalid results: {results}")
            return False
            
    except Exception as e:
        print(f"❌ Tavily Failed: {e}")
        return False

if __name__ == "__main__":
    test_tavily()
