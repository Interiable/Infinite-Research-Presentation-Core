import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

def search_arxiv(query, max_results=3):
    url = f'http://export.arxiv.org/api/query?search_query={urllib.parse.quote(query)}&start=0&max_results={max_results}&sortBy=relevance&sortOrder=descending'
    try:
        response = urllib.request.urlopen(url)
        xml_data = response.read()
        root = ET.fromstring(xml_data)
        
        papers = []
        for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
            title = entry.find('{http://www.w3.org/2005/Atom}title').text.replace('\n', ' ').strip()
            summary = entry.find('{http://www.w3.org/2005/Atom}summary').text.replace('\n', ' ').strip()
            published = entry.find('{http://www.w3.org/2005/Atom}published').text.split('T')[0]
            link = entry.find('{http://www.w3.org/2005/Atom}id').text
            papers.append({'title': title, 'summary': summary, 'published': published, 'link': link})
        return papers
    except Exception as e:
        return str(e)

queries = [
    ('Apple Foundation Models / Elegant Intelligence', 'all:"Apple Intelligence" OR (all:"foundation model" AND all:"Apple")'),
    ('Physical AI & Vision-Language-Action (VLA)', 'all:"Vision-Language-Action" OR all:"VLA model"'),
    ('Dual-Process / System 1 System 2 Robotics', 'all:"System 1" AND all:"System 2" AND all:"robot"')
]

print("🔍 깐깐한 타당성 검증을 위한 SOTA 논문 탐색 (ArXiv API)")
print("="*60)

for topic_name, q in queries:
    print(f"\n📚 [테마]: {topic_name}")
    results = search_arxiv(q, max_results=2)
    if isinstance(results, list):
        if not results:
            print("   ⚠️ 관련된 논문을 찾지 못했습니다. 키워드 조정이 필요합니다.")
        for idx, p in enumerate(results, 1):
            print(f" {idx}. {p['title']} ({p['published']})")
            print(f"    🔗 {p['link']}")
            print(f"    💡 핵심 요약: {p['summary'][:250]}...")
    else:
        print(f"   ❌ 오류 발생: {results}")

