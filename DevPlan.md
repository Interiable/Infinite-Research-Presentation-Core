# Project Name: Infinite-Research-Presentation-Core (v2026)
# Target Platform: Python (LangGraph) + React (Frontend for Slides)
# Created Date: 2026-01-29

## 1. Project Objective
Build an **Autonomous Recursive Research & Infographic Agent System**.
The system acts as a 24/7 research lab that continuously researches a given topic, plans a narrative, and generates high-quality **HTML5 Infographic Slides (React/Tailwind based)**.
The process must be iterative, strictly versioned, and driven by a "Perfectionist" Supervisor who obsessively critiques logic, flow, and design until the highest standard is met.

## 2. Core Agent Personas (The Team)

### A. The Perfectionist Director (Supervisor & Critic) - [Model: Gemini 1.5 Pro]
- **Role:** Project Manager & Creative Director.
- **Personality:** Obsessive about details, logic, and storytelling (Steve Jobs persona). Never accepts "good enough."
- **Responsibilities:**
    - Analyzes the user's vague goal into concrete research plans.
    - Critiques the HTML slides pixel-by-pixel (via code/text inspection).
    - Checks logical flow: "Does slide 3 connect to slide 4 smoothly?"
    - **Decision Authority:**
        - If quality < 99%: Rejects and sends back to Research or Design.
        - If quality >= 99%: Approves and saves final version.
        - Even after approval, continues to suggest "Next Level" improvements.

### B. The Deep Researcher (Worker) - [Model: Gemini 1.5 Flash / Tavily]
- **Role:** Web & API Researcher.
- **Responsibilities:**
    - Uses Deep Research API for comprehensive web scanning.
    - Continuously updates the 'Knowledge Base' with new findings.

### C. The Local Archivist (Worker) - [Model: Local LLM / Llama-3]
- **Role:** Internal Document Specialist.
- **Responsibilities:**
    - Scans local folders (PDF, Docx, MD) using RAG.
    - Ensures the project aligns with user's existing private data.

### D. The Infographic Architect (Frontend Dev) - [Model: Gemini 1.5 Pro (Coding Mode)]
- **Role:** HTML/React Slide Generator.
- **Output:** Modern, animated HTML slides (using React, Tailwind CSS, Framer Motion).
- **Special Instruction:**
    - Do NOT generate static images for complex visuals.
    - Instead, leave **Placeholders** (e.g., `<div className="placeholder-video">Insert Demo Video Here</div>`) with precise size/aspect ratio instructions.
    - Focus on typography, layout, color theory, and motion capability.

## 3. Workflow Logic (The "Infinite Loop")

The system operates on a `StateGraph` with a strict feedback loop:

1.  **Phase 1: Planning & Research**
    - Supervisor sets the angle.
    - Researcher & Archivist gather data -> Update `SharedKnowledgeState`.
2.  **Phase 2: Synthesis & Storyboarding**
    - Supervisor creates a detailed storyboard (Text).
3.  **Phase 3: Development (Coding Slides)**
    - Infographic Architect converts storyboard into React Components (`Slide_v{N}.tsx`).
4.  **Phase 4: Review & Versioning (CRITICAL)**
    - Supervisor reviews the generated code/content.
    - **Action: Save Artifact** -> Save current build to `./output/v{N}/` (Full HTML build).
    - **Action: Critique** ->
        - Logic flaw? -> Go to **Phase 1**.
        - Design flaw? -> Go to **Phase 3**.
        - Content gap? -> Go to **Phase 1**.
        - Perfect? -> Wait for user command or Start "Deepen Cycle" (Self-initiated improvement).

## 4. Technical Specifications
- **Framework:** LangChain / LangGraph
- **Backend:** Python 3.12+
- **Frontend (Slides):** React, Vite, TailwindCSS, Framer Motion (for animations).
- **File System:**
    - `/workspace/data`: User's local documents.
    - `/workspace/output/v1`, `/workspace/output/v2`... : Versioned builds.
    - `/workspace/logs`: Detailed reasoning logs of the Supervisor.
- **Configuration Management:**
    - The system must NOT utilize hardcoded paths for data sources.
    - Create a `config.yaml` or `.env` file where the user can define the `LOCAL_RESEARCH_DIR`.
    - **Feature:** The 'Local Archivist' agent must recursively scan (`os.walk` or `glob`) the user-defined folder, including all sub-folders, to find relevant documents (PDF, DOCX, MD, TXT).

- **Startup Routine:**
    - On startup, check if the `LOCAL_RESEARCH_DIR` is valid.
    - If not, prompt the user via CLI or UI: "연구 자료가 들어있는 폴더 경로를 입력해주세요."


## 5. Execution Instructions for Antigravity
- Generate the full directory structure.
- Implement the `Supervisor` node with a strict prompt that prevents early termination.
- Ensure the `Infographic Architect` generates runnable React code.
- Create a `Viewer` dashboard where the user can browse `v1`, `v2`, `v3` slides in real-time.

## 6. Communication & Execution Strategy (NEW: Optimistic Non-blocking)

### A. The "Bias for Action" Protocol
The Agent must **NEVER STOP** waiting for user input.
- **Scenario:** When an ambiguity arises (e.g., specific design preference, missing data).
- **Action:**
    1.  **Formulate Hypothesis:** The Agent selects the most logical option (e.g., "I assume the user wants option A based on previous context").
    2.  **Notify (Async):** Send a message to the user explaining the ambiguity and the chosen hypothesis.
    3.  **Execute Immediately:** Continue working based on that hypothesis without pausing.

### B. The "Boss-Report" Persona (Tone & Manner)
- **Interface:** Text-based Chat / Messenger API (Slack/Telegram style).
- **Tone:** Professional, Concise, Report-to-Senior-Manager style (Korean Business Manner).
- **Example Log:**
    > "박사님, 3번 슬라이드에서 로봇 제어 방식이 구체적이지 않아, 일단 '임피던스 제어' 기준으로 작성하고 넘어가겠습니다. 혹시 다른 방식(예: 위치 제어)을 원하시면 말씀해 주세요. 저는 계속 다음 장 만들고 있겠습니다."

### C. Feedback Handling (The "Hot-Swap" Logic)
- **Listener:** A background process constantly listens for User messages.
- **Trigger:** When User replies (e.g., "아니, 임피던스 말고 하이브리드 제어로 해").
- **Reaction:**
    1.  **Acknowledge:** "넵, 하이브리드 제어로 방향 수정하겠습니다."
    2.  **Rollback & Refactor:** Discard the parts based on the wrong hypothesis and regenerate them immediately.
    3.  **Resume:** Continue the infinite loop with the updated directive.

## 7. Integrated Tooling for Communication
- **Notification Tool:** `send_message_to_user(text)`
    - Connects to user's preferred messenger.
- **Listener Tool:** `check_user_messages()`
    - Runs in parallel loop.
    - Prioritizes user interrupt over current task.

## 8. Frontend UI Specifications (The "Mission Control" Dashboard)

### A. Layout Structure (Split-Screen)
Build a **Modern React-based Single Page Application (SPA)** with a 2-column layout:

1.  **Left Panel (30% width) - "Communication & Control"**
    - **Chat Component:** A messenger-style interface for the User and Supervisor Agent. Supports rich text (Markdown).
    - **Process Log:** A collapsible terminal view showing real-time logs (e.g., "Reading local PDF...", "Searching Web...").
    - **Settings Bar:** An input field to change `LOCAL_RESEARCH_DIR` dynamically.

2.  **Right Panel (70% width) - "Live Infographic Preview"**
    - **The Stage:** Renders the generated HTML/React slides fully interactive.
    - **Version Control Tabs:** [v1] [v2] [v3] tabs at the top to switch history instantly.
    - **Navigation:** Previous/Next slide buttons and a grid view for overview.

### B. Design System
- **Theme:** Dark Mode (Cyberpunk/Developer aesthetic) by default.
- **Library:** Use **Tailwind CSS** for layout and **Framer Motion** for slide transitions (make it feel like Apple Keynote but on Web).
- **Responsiveness:** Ensure the slide preview scales correctly maintaining the aspect ratio (16:9).

### C. Interaction Logic
- When the Agent updates the code, the Right Panel must **Hot-Reload** automatically without refreshing the whole page.
- Show a "Typing..." or "Thinking..." indicator in the Chat Component when the Agent is working.
