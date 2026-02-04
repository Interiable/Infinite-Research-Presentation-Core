# 🌌 Gravity AI Agent v3.1 (Ultimate Edition - Qwen3 Powered)

**"Hybrid Intelligence, Absolute Quality."**

This is an advanced, autonomous AI Agent system designed to function as a complete **R&D Team**. It combines the cost-efficiency of **High-Performance Local LLMs** with the reasoning power of Gemini Pro and GPT-5.2, all orchestrated by a rigorous Supervisor.

---

## 🚀 Key Features (v3.1 Update)

### 1. 🛡️ Polyglot Fallback Engine ("The Brain that Never Sleeps")
The system uses a tiered intelligence strategy to ensure zero downtime and maximum quality:
1.  **Primary**: **Gemini 3 Pro** (High Reasoning, Polyglot).
2.  **Secondary**: **OpenAI GPT-5.2** (High Quality Fallback). If Gemini hits a quota limit (429), the system *instantly* switches to GPT-5.2 while preserving the entire conversation context.
3.  **Local LLM**: **Qwen3-32B (Dense)** running via Ollama.
    -   **Why?**: Selected for **maximum reasoning consistency** and instruction-following capability.
    -   **Specs**: 32B parameters (Dense), 20GB VRAM usage. Fits comfortably on RTX 5090.
    -   **Trade-off**: Slightly slower than MoE, but provides deeper, more stable analysis.

### 2. 🧠 Strict Librarian & North Star Protocol ("The Anti-Drift System")
-   **Strict Librarian**: The Planner filters and selects only relevant files (`.pdf`, `.txt`, `.md`, **`.docx`**) from the `data/` folder and connected repositories.
    -   *Update*: Now fully supports Microsoft Word (`.docx`) deep reading.
-   **North Star Protocol**: To prevent "Goal Drift", the Supervisor rejects any work that deviates from the original user intent.

### 3. ✍️ Deep Recursive Writer ("The Book Author")
Instead of shallow summaries, the Researcher writes **Book-Quality Reports**:
-   **Blueprinting**: Generates a Table of Contents (TOC).
-   **Deep Reading**: Reads the **FULL TEXT** of relevant PDFs/Code for each chapter (not just snippets).
-   **Performance Tracking**: Automatically tracks and reports execution time for every chapter (e.g., "Duration: 45.2s").
-   **Refined Supervision**: Supervisor intervenes to "Coach & Rewrite" after **10 failed attempts** (Standard) to ensure quality.

### 4. 🎨 Iterative Architect ("The Designer")
Builds complex React applications (Slides/Dashboards) component by component:
-   **Blueprint First**: Designs the slide structure.
-   **Component Loop**: Codes each slide individually (`Slide1.tsx`, `Slide2.tsx`...).
-   **Feedback Loop**: If the Supervisor critiques a specific slide, the Architect refactors ONLY that slide.

---

## 🛠️ System Architecture

| Agent | Role | Engine | Key Capability |
| :--- | :--- | :--- | :--- |
| **Planner** | Strategist | Gemini 3 Pro | **Context Filtering** (Strict Librarian) |
| **Supervisor** | Gatekeeper | Polyglot (Pro/GPT) | **Quality Control** (Intervenes @ 10 failures) |
| **Researcher** | Writer | **Qwen3-32B (Dense)** | **Recursive Drafting** (Deep Read + Timer) |
| **Architect** | Developer | Gemini 3 Pro | **Iterative Coding** (React/Lucide) |

---

## 🏃 Implementation Guide

### Prerequisites
-   Python 3.10+
-   Node.js 18+
-   **Ollama** running locally with `qwen3:32b`
-   **Hardware**: RTX 5090 Recommended for full performance (20GB VRAM required)
-   API Keys: `GOOGLE_API_KEY`, `OPENAI_API_KEY` (Optional fallback)

### 1. Setup Environment
```bash
# Clone Repository
git clone [repo-url]
cd LangAIAgent

# Create Virtual Environment (Recommended)
python -m venv backend/venv
source backend/venv/bin/activate

# Install Dependencies
pip install -r backend/requirements.txt
```

### 2. Configure Credentials
Create `backend/.env`:
```ini
GOOGLE_API_KEY=AIzaSy...
OPENAI_API_KEY=sk-proj...
# Comma-separated absolute paths to your research data/code
LOCAL_RESEARCH_DIR=/home/user/data,/home/user/projects/robot_code
# Local Model Selection
LOCAL_LLM_MODEL=qwen3:32b
```

### 3. Prepare Data
Put your PDF papers, text files, Word docs (`.docx`) or code repositories into `backend/data/` or link them via `LOCAL_RESEARCH_DIR`.

### 4. Launch System
```bash
python share_system.py
```
This script handles everything:
-   Starts the FastAPI Backend.
-   Starts the React Frontend (Vite).
-   Sets up the Tunnel (ngrok/localtunnel) for sharing.

---

## 📂 Project Structure

```
LangAIAgent/
├── backend/
│   ├── app/
│   │   ├── agents/          # Planner, Supervisor, Researcher, Architect
│   │   ├── core/            # State Schema (AgentState, Graph)
│   │   └── utils.py         # RobustGemini (Polyglot Wrapper)
│   ├── data/                # Your Research Files (PDFs, Code)
│   └── artifacts/           # Generated Reports & Slides
└── frontend/
    └── src/                 # React UI
```

---

## 🛡️ License
Private Agent System. Developed for Advanced AI Research.
