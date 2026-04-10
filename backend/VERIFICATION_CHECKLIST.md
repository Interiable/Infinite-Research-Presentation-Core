# 🔍 v11.0 Full-Text Deep Read — Verification Checklist

다음 연구 프로젝트 실행 시 아래 항목을 확인하세요.

## 기능 설명
Researcher가 매 substep마다 ChromaDB에서 논문/특허를 검색하고, 관련도 ≥ 0.5인 항목의 **원본 전문(PDF/JSON)**을 읽어 수식·청구항·알고리즘을 추출하여 보고서 작성에 활용.

## 확인 항목

### 1. Paper Full-Text Deep Read
- [ ] 로그에 `📖 Full-Text Deep Read: {논문제목}` 메시지 출력 확인
- [ ] 로그에 `✅ Extracted {N} chars of detailed content` 출력 확인
- [ ] 로그에 `🔬 Full-Text Extraction Complete: {N} papers` 출력 확인
- [ ] 관련 없는 논문은 `⏭️ Paper not relevant to current topic, skipped` 으로 스킵되는지 확인
- [ ] 추출된 내용에 수식(LaTeX)이나 알고리즘이 포함되어 있는지 확인 (최종 보고서에서)

### 2. Patent Full-Text Deep Read
- [ ] 로그에 `📖 Full-Text Deep Read: Patent {ID}` 메시지 출력 확인
- [ ] 로그에 `✅ Extracted {N} chars from patent {ID}` 출력 확인
- [ ] 로그에 `🔬 Full-Text Patent Extraction Complete: {N} patents` 출력 확인
- [ ] 추출된 특허 claims가 보고서에 인용되는지 확인

### 3. 안전장치 확인
- [ ] 논문 최대 3편까지만 전문 읽기 (3편 초과 시 나머지 무시)
- [ ] 특허 최대 3건까지만 전문 읽기
- [ ] 각 추출 결과가 5,000자 이내인지 확인 (로그의 chars 수 확인)
- [ ] Substep마다 독립적으로 동작하는지 확인 (이전 substep 추출 내용이 다음에 누적되지 않음)

### 4. 성능 확인
- [ ] ChromaDB 검색 자체는 2초 이내 완료 (로그의 시간 확인)
- [ ] 전문 읽기 + LLM 추출은 substep당 추가 1~3분 이내 완료
- [ ] 전체 연구 시간이 비정상적으로 늘어나지 않음

### 5. 보고서 품질 확인
- [ ] 이전 연구 대비 수식/알고리즘 인용이 더 구체적인지 비교
- [ ] `[Paper: ...]` 또는 `[Patent: ...]` 인용이 정확한 출처와 함께 달리는지 확인
- [ ] 추출된 내용이 원문 복붙이 아닌 **해당 토픽에 맞게 정리/요약** 되었는지 확인

## 관련 코드
- **RAG 검색**: [rag.py](app/core/rag.py) → `search_papers_with_sources()`, `search_patents_with_sources()`
- **전문 추출**: [researcher.py](app/agents/researcher.py) → `extract_from_fulltext_papers()`, `extract_from_fulltext_patents()`
- **호출 지점**: [researcher.py](app/agents/researcher.py) L924~L965 (Paper/Patent Library 검색 섹션)

## 문제 발생 시
- Gemini Embedding API 타임아웃 → `.env`의 `GOOGLE_API_KEY` 확인
- ChromaDB 검색 결과 0건 → `data/chroma_paper_library/`, `data/chroma_patent_library/` 비어있는지 확인
- 전문 읽기 실패 → PDF 파일이 `data/papers/`에 실제 존재하는지, JSON이 `data/patents/`에 존재하는지 확인
