import arxiv
import requests
import json

def test_arxiv():
    print("--- Testing ArXiv API ---")
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query = "Large Language Models",
            max_results = 2,
            sort_by = arxiv.SortCriterion.Relevance
        )
        results = list(client.results(search))
        if len(results) > 0:
            print(f"✅ ArXiv Success! Found {len(results)} papers.")
            print(f"   Sample: {results[0].title}")
            return True
        else:
            print("⚠️ ArXiv returned 0 results.")
            return False
    except Exception as e:
        print(f"❌ ArXiv Failed: {e}")
        return False

def test_semantic_scholar():
    print("\n--- Testing Semantic Scholar API ---")
    try:
        query = "Large Language Models"
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&limit=2&fields=title,authors,year"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data['total'] > 0:
                print(f"✅ Semantic Scholar Success! Found {data['total']} papers.")
                print(f"   Sample: {data['data'][0]['title']}")
                return True
            else:
                print("⚠️ Semantic Scholar returned 0 results.")
                return False
        else:
            print(f"❌ Semantic Scholar Failed: Status {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Semantic Scholar Error: {e}")
        return False

if __name__ == "__main__":
    arxiv_ok = test_arxiv()
    s2_ok = test_semantic_scholar()
    
    if arxiv_ok and s2_ok:
        print("\n✅ BOTH APIs are WORKING.")
    else:
        print("\n⚠️ Some APIs failed.")
