# 🌌 Gravity AI Agent v2.0 (Architect Edition)

**"From Chaos to Structure: The Plan-First AI Agent"**

This project is an advanced, autonomous AI Agent system built with **LangGraph** and **Google Gemini Models**. It is designed to emulate a human engineering team, featuring strict role separation, meticulous planning, and accumulative knowledge building.

---

## 🚀 Key Features

### 1. 🧠 Step-by-Step Architecture (The "Architect" Brain)
Unlike typical chatbots that rush to answer, this agent **Plans First**.
- **Planner Agent**: Before any execution, it generates a structured **Project Plan** (e.g., Phase 1: Research -> Phase 2: Design).
- **Sequential Execution**: The Supervisor enforces strict adherence to the plan. Phase 2 starts only after Phase 1 is marked `[COMPLETE]`.
- **Artifact**: You can see the live plan in `project_plan.md`.

### 2. 📚 Accumulative Research (Smart Expansion)
Research reports **grow** over time instead of being rewritten.
- **"Preserve & Append"**: The AI never deletes valid details. It appends new findings to the existing body.
- **"Smart Evolution"**: The AI acts as a "Lead Editor", correcting errors and restructuring flow while strictly maintaining density and depth.
- **Outcome**: A massive, detailed report that gets smarter with every iteration.

### 3. ⏱️ Command History UI
NEVER lose track of what you said.
- A new **History Panel** (Clock Icon) allows you to view the full log of your commands within the current session.
- Powered by persistent `sqlite` state storage.

### 4. ⚡ Tiered Intelligence
- **Planner/Supervisor**: Uses `gemini-2.0-flash-exp` for fast, structured decision making.
- **Deep Researcher**: Uses `gemini-3-flash-preview` for grounded, high-speed data retrieval.
- **Local LLM**: Integrated fallback for cost-efficient refinement.

---

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, LangGraph, Google Gemini API
- **Frontend**: React, Vite, TypeScript, TailwindCSS
- **Persistence**: `AsyncSqliteSaver` (SQLite) - The "Hippocampus" of the system.
- **Knowledge Base**: ChromaDB (Vector Store) for local document retrieval.

---

## 🏃 Implementation Guide

### Prerequisites
- Python 3.10+
- Node.js 18+
- Google Gemini API Key

### Quick Start
This system comes with a "One-Click" launcher that handles backend, frontend, and tunnel creation.

```bash
# 1. Clone & Setup
git clone [repo-url]
cd LangAIAgent

# 2. Configure Environment
cp backend/.env.example backend/.env
# Edit backend/.env and add your GOOGLE_API_KEY

# 3. Launch System
python share_system.py
```

---

## 📂 Project Structure

```
LangAIAgent/
├── backend/
│   ├── app/
│   │   ├── agents/          # Role-Based Agents (Planner, Supervisor, Researcher...)
│   │   ├── core/            # Graph Logic & State Schema
│   │   └── api/             # FastAPI Endpoints
│   ├── data/                # SQLite Database (System Memory - CAUTION: Do Not Delete)
│   └── artifacts/           # Generated Output (Slides, Reports)
└── frontend/
    └── src/
        └── components/      # React UI Components (ChatPanel, etc.)
```

---

## 🛡️ License
Private Agent System. Developed for Advanced AI Research.
