# LangAIAgent — 설치 및 실행 가이드

> Ubuntu 24.04 기준. 새 PC에서 `git clone` 후 이 가이드만 따르면 됩니다.

---

## 0. 시스템 요구사항

| 항목 | 최소 | 권장 |
|------|------|------|
| OS | Ubuntu 24.04 | Ubuntu 24.04 |
| Python | 3.11+ | 3.12 |
| RAM | 16 GB | 32 GB |
| GPU VRAM | 없어도 됨 (CPU 가능) | 20+ GB (로컬 LLM용) |
| 디스크 | 50 GB | 100 GB |
| Node.js | 18+ | 20+ |

---

## 1. 클론 & 자동 설치 (권장)

```bash
git clone <repo-url> LangAIAgent
cd LangAIAgent
bash setup.sh
```

`setup.sh`이 자동으로 처리하는 항목:
- 시스템 패키지 (Python, Node, 폰트 등)
- Python 가상환경 + pip 패키지
- Playwright Chromium (PDF 생성 엔진)
- Node 패키지 (프론트엔드)
- Ollama (로컬 LLM 서버)
- 로컬 LLM 모델 pull (선택적)

---

## 2. API 키 설정

```bash
nano backend/.env
```

`.env` 파일에 아래 값을 채웁니다:

```env
# [필수] Google Gemini
GOOGLE_API_KEY=AIza...

# [필수] Tavily 웹 검색
TAVILY_API_KEY=tvly-...

# [선택] OpenAI (폴백 LLM)
OPENAI_API_KEY=sk-...

# [선택] Google Cloud BigQuery (특허 검색용)
GCP_PROJECT_ID=my-project-id
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service_account.json

# 로컬 문서 폴더 (RAG 색인용)
LOCAL_RESEARCH_DIR=/home/yourname/documents
```

### API 키 발급 링크

| 서비스 | 링크 | 비고 |
|--------|------|------|
| Google Gemini | https://aistudio.google.com/app/apikey | 무료 티어 있음 |
| Tavily | https://app.tavily.com/ | 월 1,000회 무료 |
| OpenAI | https://platform.openai.com/api-keys | 폴백 전용, 선택사항 |
| Google Cloud | https://console.cloud.google.com/ | 특허 검색 시만 필요 |

---

## 3. AI 모델 설정

### 3-1. Cloud LLM (Gemini / OpenAI)

`.env`에서 모델명을 직접 지정합니다. **항상 최신 모델 확인 후 업데이트하세요.**

```env
# 주력 추론 모델 (계획, 비평, 최종 검수)
GEMINI_PRO_MODEL=gemini-2.5-pro

# 백업 (쿼터 초과 시 자동 전환)
GEMINI_PRO_BACKUP_MODEL=gemini-2.5-pro-preview-06-05

# 경량 모델 (초안 집필, 요약)
GEMINI_FLASH_MODEL=gemini-2.5-flash

# OpenAI 폴백
OPENAI_MODEL=gpt-4o

# RAG 임베딩
EMBEDDING_MODEL=models/text-embedding-004
```

> **최신 모델 확인:** https://ai.google.dev/gemini-api/docs/models

### 3-2. 로컬 LLM (Ollama)

Ollama로 실행되는 로컬 모델입니다. GPU 없이도 CPU로 동작하나 느립니다.

```bash
# 모델 설치 (택 1)
ollama pull qwen3:32b        # Dense, 고품질 (~20GB VRAM)
ollama pull qwen3:30b-a3b    # MoE, 효율적 (~16GB VRAM) ← 권장
ollama pull deepseek-r1:32b  # 과학적 추론 특화
ollama pull qwen3:8b         # GPU 없을 때 (8GB RAM)
```

```env
# .env에 선택한 모델명 지정
LOCAL_LLM_MODEL=qwen3:32b
```

> **최신 모델 목록:** https://ollama.com/library

---

## 4. 실행

```bash
# 가상환경 활성화 (첫 실행 시)
source backend/venv/bin/activate

# 시스템 시작
python3 run_system.py
```

브라우저가 자동으로 열립니다:
- **프론트엔드:** http://localhost:5174
- **API 서버:** http://localhost:8000

---

## 5. 수동 설치 (setup.sh 없이)

```bash
# Python 가상환경
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Playwright Chromium (PDF 생성 필수)
playwright install chromium

# 프론트엔드
cd ../frontend
npm install

# Ollama 설치
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:32b
```

---

## 6. Google Cloud BigQuery 설정 (특허 검색 선택사항)

```bash
# 1. gcloud CLI 설치
curl https://sdk.cloud.google.com | bash

# 2. 서비스 계정 생성 (GCP 콘솔에서)
#    IAM → 서비스 계정 → 키 생성 → JSON 다운로드

# 3. .env에 경로 지정
GOOGLE_APPLICATION_CREDENTIALS=/home/yourname/keys/gcp_key.json
GCP_PROJECT_ID=your-project-id
```

---

## 7. 문제 해결

### PDF가 생성되지 않을 때
```bash
# Playwright 브라우저 재설치
source backend/venv/bin/activate
playwright install chromium --with-deps
```

### Ollama 모델 응답 없을 때
```bash
# Ollama 서버 상태 확인
curl http://localhost:11434/api/tags

# 서비스 재시작
systemctl restart ollama   # 또는
ollama serve &
```

### 포트 충돌 시
```bash
# 8000 또는 5174 사용 중인 프로세스 확인
lsof -i :8000
lsof -i :5174
```

### ChromaDB 오류 시
```bash
# 벡터 DB 초기화
rm -rf backend/data/projects/*/chroma_db
```

---

## 8. 디렉토리 구조

```
LangAIAgent/
├── backend/
│   ├── app/
│   │   ├── agents/     # Supervisor, Planner, Researcher 등
│   │   ├── api/        # FastAPI WebSocket + REST
│   │   ├── core/       # LangGraph 워크플로우, RAG
│   │   └── utils/      # RobustGemini, PDF 변환 등
│   ├── .env            # API 키 (git 제외)
│   ├── .env.example    # 템플릿
│   └── requirements.txt
├── frontend/           # React 19 + Vite + Tailwind
├── run_system.py       # 시스템 시작 스크립트
├── setup.sh            # 자동 설치 스크립트
└── SETUP.md            # 이 파일
```
