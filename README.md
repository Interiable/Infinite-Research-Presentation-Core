# Infinite Research Presentation Core (v2026)

**Autonomous Recursive Research & Infographic Agent System**

An advanced AI Agent system that continuously researches topics, plans narratives, and generates high-quality HTML5/React infographic slides. Driven by a "Perfectionist" Supervisor (Gemini 3 Pro) and supported by deep research and local archiving agents.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Status](https://img.shields.io/badge/status-Active_Development-neon_green)

## 🚀 Key Features

-   **Recursive Research Loop**: Continuously gathers web (Deep Research) and local data until the "Perfectionist" Supervisor is satisfied.
-   **Strict Quality Gates**:
    -   **Content Gate**: Verifies narrative logic/flow before design begins.
    -   **Design Gate**: Pixel-perfect critique of React components.
-   **Mission Control Dashboard**:
    -   Cyberpunk-themed React UI.
    -   Real-time "Think Logs" via WebSockets.
    -   Hot-Reloading Slide Preview.
-   **Bias for Action**: Optimistic non-blocking workflow that assumes user intent to keep progress moving.

## 🛠️ Tech Stack (v2026)

-   **Backend**: Python, FastAPI, LangGraph, LangChain.
-   **Frontend**: React (Vite), Tailwind CSS v4, Framer Motion.
-   **AI Models**:
    -   **Supervisor**: Gemini 3 Pro ("Steve Jobs" Persona).
    -   **Researcher**: Gemini 3 Flash + Google Deep Research API.
    -   **Archivist**: Qwen 3 (32B) local model via Ollama.

## 📦 Installation

### Prerequisites
-   Python 3.12+
-   Node.js 20+
-   [Ollama](https://ollama.com) (for Local LLM)

### 1. Clone & Setup
```bash
git clone https://github.com/Interiable/Infinite-Research-Presentation-Core.git
cd Infinite-Research-Presentation-Core
```

### 2. Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# EDIT .env with your keys: GOOGLE_API_KEY, TAVILY_API_KEY
```

### 3. Frontend Setup
```bash
cd frontend
npm install
```

### 4. Local Model Setup
```bash
ollama run qwen3:32b
```

## 🖥️ Usage

1.  **Start Backend**:
    ```bash
    cd backend
    source venv/bin/activate
    uvicorn app.main:app --reload
    ```
2.  **Start Frontend**:
    ```bash
    cd frontend
    npm run dev
    ```
3.  **Access Mission Control**:
    Open [http://localhost:5174](http://localhost:5174) (or 5173).

## 📂 Project Structure
```
├── backend/            # FastAPI + LangGraph Agents
│   ├── app/agents/     # Supervisor, Researcher, Archivist, Architect
│   ├── app/core/       # State definition, Graph logic
│   └── app/api/        # Endpoints, WebSockets
├── frontend/           # React Mission Control
│   ├── src/components/ # Chat, Terminal, SlidePreview
│   └── src/hooks/      # WebSocket logic
└── workspace/          # Data Output Directory
```
