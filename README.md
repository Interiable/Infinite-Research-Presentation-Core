# 🌌 LangAIAgent D-Research (Ultimate Plus - Gemma-4-31B Powered)

**"Hybrid Intelligence, Absolute Quality, Zero Hallucinations."**

This is an advanced, autonomous AI Agent system designed to function as a complete **R&D Team**. It combines the cost-efficiency of **High-Performance Local LLMs (Gemma-4-31B)** with the reasoning power of Gemini Pro and GPT-5.2, all orchestrated by a rigorous Supervisor and a Deep Research pipeline.

---

## 🚀 Key Features (v4.0 Update)

### 1. 🧠 Holistic Knowledge Synchronization & Registry Guard
The biggest leap in v4.0 is the integration of a **Deep Research Pipeline** and **Ground Truth Synchronization**:
- **Deep Research Engine**: Actively fetches and parses Academic papers (ArXiv), Web searches, Patents (Google Patents), and Media (YouTube Transcripts).
- **Holistic Knowledge Sync**: `local_knowledge` (RAG DB) and `web_knowledge` (Deep Search) are globally injected into the **Plan Refiner** and **Supervisor**. The Supervisor now critiques drafts using actual *Ground Truth* rather than relying solely on arbitrary rules.
- **Registry Guard (0% Hallucination)**: All loaded documents are assigned a `REF` tag and stored in a `verified_reference_registry`. The Researcher Agent actively strips and amputates any LLM-hallucinated citations (`[REF-XXX]`) that do not exist in the registry before submitting drafts.

### 2. 🛡️ Polyglot Fallback Engine ("The Brain that Never Sleeps")
The system uses a tiered intelligence strategy to ensure zero downtime and maximum quality:
1.  **Primary**: **Gemini 1.5 Pro / Flash** (High Reasoning, Document Processing).
2.  **Secondary**: **OpenAI GPT-5.2** (High Quality Fallback). If Gemini hits a quota limit (429), the system *instantly* switches to GPT-5.2 while preserving the entire conversation context.
3.  **Local LLM**: **Gemma-4-31B** (Running locally).
    -   **Why?**: Unrivaled capacity for high-fidelity scientific reasoning, mathematical derivation, and academic paper summarization. Replaces DeepSeek-R1 for superior academic rigor without internal reasoning tag leakage.

### 3. ✍️ Deep Recursive Writer ("The Book Author")
Instead of shallow summaries, the Researcher writes **Book-Quality Reports**:
- **Dynamic Search Constraints**: Configurable flags (e.g., `--no-patent`, `--no-media`) block both web-scraping APIs and Local DB injections flawlessly across all agents.
- **Blueprinting**: Generates a Table of Contents (TOC) referencing the `Deep_Research_Results`.
- **Deep Reading**: Reads the **FULL TEXT** of relevant PDFs/Code for each chapter (not just snippets).
- **Refined Supervision**: Supervisor intervenes immediately to "Coach & Rewrite" if a document fails academic rigor logic tests.

### 4. 🎨 Iterative Architect ("The Designer")
Builds complex React applications (Slides/Dashboards) component by component:
-   **Blueprint First**: Designs the slide structure.
-   **Component Loop**: Codes each slide individually (`Slide1.tsx`, `Slide2.tsx`...).

---

## 🛠️ System Architecture

| Agent | Role | Engine | Key Capability |
| :--- | :--- | :--- | :--- |
| **Planner & Refiner** | Strategist | Gemini 1.5 Pro | **Holistic Knowledge Integration** |
| **Supervisor** | Quality Gate | Gemini 1.5 Pro / GPT | **Ground Truth Verification** |
| **Researcher** | Writer | Gemini 1.5 Flash | **Deep Reading & Registry Guard** |
| **Scientific Specialist** | Domain Expert | **Gemma-4-31B** | **Math & SOTA Synthesis** |

---

## 🏃 Implementation Guide

### Prerequisites
-   Python 3.10+
-   Node.js 18+
-   **Hardware**: RTX 5090 Recommended (Handles Gemma-4-31B efficiently).
-   API Keys: `GOOGLE_API_KEY`, `OPENAI_API_KEY` (Optional fallback), `TAVILY_API_KEY`

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
TAVILY_API_KEY=tvly-...
# Local Model Selection
LOCAL_LLM_MODEL=gemma4:31b
```

### 3. Prepare Data
Put your PDF papers, text files, Word docs (`.docx`) or code repositories into `backend/data/projects/default`.

### 4. Launch System
```bash
python run_system.py
```
This script handles everything:
-   Starts the FastAPI Backend (uvicorn).
-   Starts the React Frontend (vite).

---

## 📂 Project Structure

```text
LangAIAgent/
├── backend/
│   ├── app/
│   │   ├── agents/          # Supervisor, Researcher, Plan Refiner, Deep Researcher
│   │   ├── core/            # State Schema & Graph logic
│   │   ├── utils/           # Academic, Media, Patent sub-researchers
│   ├── data/                # Vector DBs (Chroma), SQLite Vault
│   └── artifacts/           # Auto-generated Reports & Outputs
└── frontend/
    └── src/                 # React UI
```

---

## 🛡️ License
Private Agent System. Developed for Advanced Physical AI & Concept Engineering.
