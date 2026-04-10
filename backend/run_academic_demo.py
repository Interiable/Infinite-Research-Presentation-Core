import sys
import os

# Ensure backend app is in path
sys.path.append(os.path.join(os.path.dirname(__file__)))
from app.utils.academic_researcher import AcademicResearcher
from app.core.rag import PaperLibrary

def main():
    print("🚀 Initializing Academic Researcher for Expressive Robot Architecture...")
    researcher = AcademicResearcher()
    
    # Core research context from the updated prompt
    original_goal = (
        "Designing an Expressive Robot Architecture integrating Theory of Mind (ToM), "
        "Laban Movement Analysis (LMA), and Physical AI UX principles. "
        "The system uses a Dual-Process (System 1 / System 2) cognitive architecture "
        "and relies on Vision-Language-Action (VLA) foundation models to produce "
        "intelligent, elegant, and affective robotic movement."
    )
    
    topics = [
        "LLM based VLA (Vision-Language-Action) models for robotic manipulation and physical AI",
        "Dual-process Human-Robot Interaction using System 1 and System 2 cognitive architectures",
        "Expressive robot motion using Laban Movement Analysis and Theory of Mind"
    ]
    
    all_papers = []
    
    for topic in topics:
        print(f"\n==============================================")
        print(f"🎯 Researching Topic: {topic}")
        keywords = researcher.extract_keywords(topic, original_goal)
        print(f"🔑 Extracted Keywords: {keywords}")
        
        # Search via both APIs depending on which returns better hits, Semantic Scholar is usually good for quality
        results = []
        for kw in keywords[:2]: # Only use top 2 to save time
            sem_results = researcher.search_semantic_scholar(kw, max_results=3)
            arxiv_results = researcher.search_arxiv(kw, max_results=2)
            results.extend(sem_results + arxiv_results)
            
        print(f"📥 Found {len(results)} raw candidate papers.")
        
        # Filter for high relevance only
        print("🧠 Evaluating Relevance (Filtering out low-quality/off-topic papers)...")
        filtered_papers = researcher.filter_by_relevance(results, topic, original_goal, threshold=6.5)
        
        print(f"✅ Survived Relevance Filter: {len(filtered_papers)} papers.")
        
        for p in filtered_papers:
            # Avoid duplicates naturally
            if not any(existing['title'] == p['title'] for existing in all_papers):
                all_papers.append(p)
                print(f"  [{p['relevance_score']}/10.0] {p['title']} ({p.get('published', 'N/A')}) - {p['source']}")
                if 'justification' in p:
                    print(f"     => {p['justification']}")
                print(f"     => URL: {p.get('pdf_url', 'Not found')}")

if __name__ == "__main__":
    main()
