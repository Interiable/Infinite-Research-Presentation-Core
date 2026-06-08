# LangAIAgent — AI 설치 가이드

> **이 문서의 목적**  
> Python 개발 경험이 없는 사용자가 AI 어시스턴트(Claude, ChatGPT 등)에게 이 문서를 보여주고 설치를 대신 진행시키기 위한 가이드입니다.  
> AI가 이 문서를 읽으면 전체 프로젝트 구조와 설치 과정을 이해하고 명령을 실행할 수 있습니다.

---

## AI에게 전달할 프롬프트 (복사해서 사용)

```
아래 문서를 읽고 내 Ubuntu 24.04 PC에 LangAIAgent를 설치해줘.
내가 API 키를 입력해야 할 때는 멈추고 알려줘.
오류가 발생하면 원인을 설명하고 해결해줘.

[AI_SETUP_GUIDE.md 내용 붙여넣기]
```

---

## 1. 프로젝트 개요

**LangAIAgent**는 12개의 전문 AI 에이전트가 협업하여 자율적으로 연구를 수행하는 시스템입니다.

- 사용자가 연구 주제를 입력하면 AI가 논문·특허·웹을 검색하고 200페이지 이상의 보고서를 자동 생성합니다.
- **백엔드**: Python (FastAPI + LangGraph)
- **프론트엔드**: React + Vite (웹 브라우저 UI)
- **로컬 AI**: Ollama (오프라인 LLM 실행)
- **클라우드 AI**: Google Gemini API (주력), OpenAI API (폴백)

### 시스템 구조
```
LangAIAgent/
├── backend/           ← Python 서버 (포트 8000)
│   ├── app/
│   │   ├── agents/    ← AI 에이전트 12개 (Supervisor, Planner, Researcher 등)
│   │   ├── core/      ← LangGraph 워크플로우, ChromaDB RAG
│   │   └── utils/     ← 논문·특허·웹 검색, PDF 생성
│   ├── .env           ← API 키 설정 파일 (직접 생성 필요)
│   ├── .env.example   ← 설정 파일 템플릿
│   └── requirements.txt ← Python 패키지 목록
├── frontend/          ← React 웹 UI (포트 5174)
├── setup.sh           ← 자동 설치 스크립트
├── run_system.py      ← 시스템 시작 스크립트
└── SETUP.md           ← 추가 참고 문서
```

---

## 2. 시스템 요구사항

| 항목 | 최소 | 권장 |
|------|------|------|
| OS | Ubuntu 24.04 | Ubuntu 24.04 LTS |
| RAM | 16 GB | 32 GB |
| GPU VRAM | 없어도 됨 (CPU 가능) | 32 GB (로컬 AI 모델용) |
| 디스크 | 50 GB | 100 GB |
| Python | 3.11+ | 3.12 |
| Node.js | 18+ | 20+ |

---

## 3. 필수 준비: API 키 발급

설치 전에 아래 API 키들을 미리 발급받으세요.  
각 링크에 접속 → 회원가입 → API 키 복사.

### [필수] Google Gemini API 키
- 링크: https://aistudio.google.com/app/apikey
- 무료 티어 있음 (분당 요청 제한 있음)
- 발급 후 키 형식 예시: `AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`

### [필수] Tavily 웹 검색 API 키
- 링크: https://app.tavily.com/
- 무료 티어: 월 1,000회 검색
- 발급 후 키 형식 예시: `tvly-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`

### [선택] OpenAI API 키
- 링크: https://platform.openai.com/api-keys
- Gemini 장애 시 폴백으로만 사용됨. 없어도 동작함.
- 발급 후 키 형식 예시: `sk-proj-XXXXXXXXXXXXXXXXXXXXXXXX`

### [선택] Google Cloud BigQuery (특허 검색용)
- 특허 검색 기능을 쓸 때만 필요. 처음에는 없어도 됨.
- https://console.cloud.google.com/ 에서 프로젝트 생성 후 서비스 계정 키(JSON) 다운로드.

---

## 4. 설치 절차

> **AI에게:** 아래 단계를 순서대로 실행하세요. 각 단계에서 오류가 발생하면 멈추고 원인을 진단하세요.

### Step 1. 저장소 클론

```bash
# 홈 디렉토리로 이동 후 클론
cd ~
git clone https://github.com/Interiable/Infinite-Research-Presentation-Core.git LangAIAgent
cd LangAIAgent
```

### Step 2. 자동 설치 스크립트 실행

```bash
bash setup.sh
```

이 스크립트가 자동으로 처리하는 항목:
1. 시스템 패키지 설치 (Python, Node.js, 폰트, Playwright 의존성)
2. `backend/.env` 파일 생성 (API 키 입력 요청)
3. Python 가상환경 생성 (`backend/venv/`)
4. Python 패키지 설치 (`pip install -r requirements.txt`)
5. Playwright Chromium 설치 (PDF 생성 엔진)
6. Node.js 패키지 설치 (`npm install`)
7. Ollama 설치 (로컬 AI 서버)
8. AI 모델 다운로드 (`qwen3.6:27b` + `gemma4:31b`)

> **중요:** 스크립트 실행 중 `.env` 파일 편집 요청이 나타나면 Step 3을 먼저 진행하세요.

### Step 3. API 키 설정

```bash
nano backend/.env
```

파일이 열리면 아래 값들을 실제 발급받은 키로 교체합니다:

```env
GOOGLE_API_KEY=여기에_Gemini_API_키_입력
TAVILY_API_KEY=여기에_Tavily_API_키_입력
OPENAI_API_KEY=여기에_OpenAI_키_입력  # 없으면 그냥 두거나 삭제
LOCAL_RESEARCH_DIR=/home/사용자이름/documents  # 로컬 문서 폴더 경로
TORCH_DEVICE=cpu  # GPU 없으면 cpu, NVIDIA GPU 있으면 cuda
```

저장: `Ctrl+O` → `Enter` → 종료: `Ctrl+X`

#### .env 전체 예시 (정상 설정된 상태)
```env
GOOGLE_API_KEY=AIzaSyAbCdEfGhIjKlMnOpQrStUvWxYz1234567
TAVILY_API_KEY=tvly-AbCdEfGhIjKlMnOpQrStUvWxYz12345678
OPENAI_API_KEY=sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz

GEMINI_PRO_MODEL=gemini-3.1-pro-preview
GEMINI_PRO_BACKUP_MODEL=gemini-3-pro-preview
GEMINI_FLASH_MODEL=gemini-3.5-flash
OPENAI_MODEL=gpt-5.5
EMBEDDING_MODEL=gemini-embedding-2

LOCAL_LLM_MODEL=qwen3.6:27b
LOCAL_SCIENCE_MODEL=gemma4:31b
OLLAMA_BASE_URL=http://localhost:11434

LOCAL_RESEARCH_DIR=/home/사용자이름/documents
TORCH_DEVICE=cpu
```

### Step 4. Ollama 서비스 시작 확인

```bash
# Ollama 서비스 상태 확인
systemctl status ollama

# 설치된 모델 목록 확인
ollama list
```

정상이라면 `qwen3.6:27b`와 `gemma4:31b`가 목록에 있어야 합니다.  
없다면 수동으로 다운로드:

```bash
ollama pull qwen3.6:27b    # 약 17GB, 시간 소요
ollama pull gemma4:31b     # 약 22GB, 시간 소요
```

### Step 5. 설치 검증

```bash
# Python 패키지 설치 확인
backend/venv/bin/python -c "import fastapi, langchain, playwright, chromadb, nest_asyncio; print('OK')"

# Node 패키지 확인
ls frontend/node_modules | head -5

# Playwright Chromium 확인
backend/venv/bin/python -m playwright install chromium --check 2>/dev/null && echo "Chromium OK"
```

모두 에러 없이 출력되면 설치 완료입니다.

---

## 5. 시스템 실행

```bash
cd ~/LangAIAgent
python3 run_system.py
```

성공 시 출력:
```
🚀 Starting Infinite Research Agent System...
🔹 Launching Backend (uvicorn)...
🔹 Launching Frontend (vite)...
✅ System Online!
   - Mission Control: http://localhost:5174
   - API Server:      http://localhost:8000
```

브라우저에서 `http://localhost:5174` 접속 → 연구 주제 입력 → `START RESEARCH` 클릭

---

## 6. AI 모델 역할 안내

### Cloud AI (인터넷 연결 필요)

| 모델 | 역할 |
|------|------|
| `gemini-3.1-pro-preview` | 주력 추론 — 연구 계획, 품질 검수, 최종 보고서 |
| `gemini-3.5-flash` | 빠른 작업 — 초안 집필, 요약, 포맷 검사 |
| `gemini-embedding-2` | 문서 벡터화 — ChromaDB RAG 검색 |
| `gpt-5.5` | 비상 폴백 — Gemini 전체 장애 시 |

### Local AI (인터넷 불필요, Ollama)

| 모델 | 역할 | VRAM |
|------|------|------|
| `qwen3.6:27b` | 한국어 번역, 문서 합성, 웹 필터링, 포맷 검사, Warden | ~17GB |
| `gemma4:31b` | 과학/수학/공학 추론 전용 (Scientific Notes) | ~22GB |

---

## 7. 문제 해결

### 문제: `backend/venv/bin/python: not found`
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 문제: PDF가 생성되지 않음
```bash
source backend/venv/bin/activate
python3 -m playwright install chromium --with-deps
```

### 문제: Ollama 모델이 응답하지 않음
```bash
# Ollama 재시작
sudo systemctl restart ollama
# 또는
ollama serve &

# 테스트
curl http://localhost:11434/api/tags
```

### 문제: `ModuleNotFoundError`
```bash
source backend/venv/bin/activate
pip install -r backend/requirements.txt
```

### 문제: 포트 충돌 (8000 또는 5174 이미 사용 중)
```bash
# 사용 중인 프로세스 확인 후 종료
lsof -i :8000
lsof -i :5174
kill -9 <PID>
```

### 문제: Gemini API 오류 (429 쿼터 초과)
시스템이 자동으로 폴백 모델로 전환합니다. 즉시 조치 불필요.  
장기적으로는 Google AI Studio에서 요금제 업그레이드 고려.

### 문제: ChromaDB 오류 (벡터 DB 손상)
```bash
rm -rf backend/data/projects/*/chroma_db
# 재실행 시 자동 재생성됨
```

---

## 8. 디렉토리 구조 (AI 참고용)

```
backend/
├── app/
│   ├── agents/
│   │   ├── local_model.py      ← Ollama 로컬 모델 초기화 (qwen3.6, gemma4)
│   │   ├── supervisor.py       ← 전체 워크플로우 지휘·품질 검수
│   │   ├── planner.py          ← 연구 계획 수립
│   │   ├── plan_refiner.py     ← 계획 세분화
│   │   ├── researcher.py       ← 보고서 집필 (Gemma4로 과학 추론)
│   │   ├── deep_researcher.py  ← 웹·논문 검색
│   │   ├── archivist.py        ← 로컬 문서 RAG 색인
│   │   ├── finalizer.py        ← 최종 보고서 조립 + PDF 생성
│   │   ├── warden.py           ← 연구 방향 정합성 감시
│   │   └── architect.py        ← React UI 생성
│   ├── core/
│   │   ├── graph.py            ← LangGraph 워크플로우 정의
│   │   ├── rag.py              ← ChromaDB 벡터 검색
│   │   └── state.py            ← 에이전트 상태 정의
│   ├── utils/
│   │   ├── __init__.py         ← RobustGemini (폴백 전략), PDF 생성
│   │   ├── academic_researcher.py ← ArXiv 논문 검색/다운로드
│   │   ├── patent_researcher.py   ← Google Patents BigQuery
│   │   └── media_researcher.py    ← YouTube 자막 추출
│   └── main.py                 ← FastAPI 앱 진입점
├── .env                        ← API 키 (절대 git에 올리지 말 것)
├── .env.example                ← 설정 템플릿
└── requirements.txt            ← Python 패키지 목록
```

---

## 9. 주요 환경변수 전체 목록 (AI 참고용)

| 변수명 | 필수 | 설명 |
|--------|------|------|
| `GOOGLE_API_KEY` | ✅ | Gemini API 키 |
| `TAVILY_API_KEY` | ✅ | 웹 검색 API 키 |
| `OPENAI_API_KEY` | 선택 | OpenAI 폴백 키 |
| `GCP_PROJECT_ID` | 선택 | BigQuery 특허 검색용 |
| `GOOGLE_APPLICATION_CREDENTIALS` | 선택 | GCP 서비스 계정 JSON 경로 |
| `GEMINI_PRO_MODEL` | ✅ | 주력 Gemini 모델명 |
| `GEMINI_PRO_BACKUP_MODEL` | ✅ | 백업 Gemini 모델명 |
| `GEMINI_FLASH_MODEL` | ✅ | Flash Gemini 모델명 |
| `OPENAI_MODEL` | 선택 | OpenAI 폴백 모델명 |
| `EMBEDDING_MODEL` | ✅ | Gemini 임베딩 모델명 |
| `LOCAL_LLM_MODEL` | ✅ | 일반 로컬 LLM (번역·합성) |
| `LOCAL_SCIENCE_MODEL` | ✅ | 과학 추론 전용 로컬 LLM |
| `OLLAMA_BASE_URL` | ✅ | Ollama 서버 주소 |
| `LOCAL_RESEARCH_DIR` | 선택 | 로컬 문서 폴더 경로 |
| `TORCH_DEVICE` | ✅ | `cpu` 또는 `cuda` |

---

## 10. 정상 동작 확인 체크리스트

설치 완료 후 아래 항목을 순서대로 확인하세요.

```
[ ] git clone 완료 — 디렉토리 LangAIAgent/ 존재
[ ] backend/.env 생성 완료 — GOOGLE_API_KEY, TAVILY_API_KEY 입력됨
[ ] Python venv 존재 — backend/venv/bin/python 파일 있음
[ ] pip 패키지 설치 — fastapi, langchain, playwright, chromadb 설치됨
[ ] Playwright Chromium 설치 — PDF 생성 가능
[ ] Node 패키지 설치 — frontend/node_modules/ 폴더 있음
[ ] Ollama 실행 중 — http://localhost:11434 응답
[ ] qwen3.6:27b 다운로드 완료 — ollama list에 표시됨
[ ] gemma4:31b 다운로드 완료 — ollama list에 표시됨
[ ] python3 run_system.py 실행 — http://localhost:5174 접속됨
[ ] 연구 주제 입력 후 START RESEARCH — 에이전트 동작 시작됨
```
