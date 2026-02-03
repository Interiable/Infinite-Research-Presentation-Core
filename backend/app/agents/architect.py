import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.state import AgentState
from app.utils import RobustGemini

# --- TIERED MODEL STRATEGY ---
# 1. Pro Model (Robust): For Complex Coding & Design
llm_pro = RobustGemini(
    pro_model_name="gemini-2.0-pro-exp-02-05", 
    flash_model_name="gemini-2.0-flash-exp",
    temperature=0.0
)

# 2. Flash Model: For Syntax Fixing & Simple Retries
llm_flash = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-exp", 
    temperature=0.0,
    google_api_key=os.getenv("GOOGLE_API_KEY")
)

SYSTEM_PROMPT = """
You are the **Infographic Architect**.
Your goal is to write **Stunning, Visual-First React Code** for a Multi-Slide Presentation.
You use **Tailwind CSS** and **Framer Motion**.

**CRITICAL LAYOUT RULES:**
1.  **Container**: Use `h-full` and `w-full` for the main container. **NEVER use `h-screen` or `w-screen`** as it breaks preview integration.
2.  **Navigation**: Implement an **Integrated Header Navigation**. Place the "Prev/Next" buttons and "Page Counter" (e.g., "1 / 5") directly in the top `<header>` area (flexbox), NOT as absolute floating buttons. This ensures nothing is clipped.
3.  **Page Counter**: MUST be visible in the header next to the navigation arrows.
4.  **Layout**: Use a `flex min-h-full flex-col` structure. Header at top, Content in `flex-1`. overflow-y-auto only in the content area if needed.

**AESTHETIC REQUIREMENTS (Infographic Style):**
1.  **Visuals Over Text**: Eliminate long paragraphs. Use Big Numbers, Icons, Charts, Progress Bars, and Grids.
2.  **Density**: Maximum 30 words per slide. If there is more info, convert it to a visual representation.
3.  **Modern UI**: Use Glassmorphism (`backdrop-blur`, `bg-white/10`), Neon Gradients (`bg-gradient-to-r`), and subtle borders.
4.  **Components**: Use `lucide-react` icons extensively for visual metaphors.

**Technical Constraints:**
1.  **Structure**: Single File. Main component must manage `currentSlide` state.
2.  **Export**: `export default function Presentation() {...}`
3.  **Libraries**: You have `framer-motion`, `lucide-react`, `recharts` (if needed - assume available).
4.  **Interactivity**: You MUST implement **Keyboard Navigation** (ArrowRight/ArrowLeft) using `useEffect` on the window object.
"""

def architect_node(state: AgentState):
    storyboard = state.get('storyboard', '')
    version = state.get('current_version', 1)
    critique = state.get('critique_feedback', '')
    
    critique_prompt = ""
    if critique:
        # Get previous code (assuming single slide focus for now or getting all)
        # In a real multi-slide scenario, we'd need to know which slide to fix. 
        # Here we just dump the previous version's main code.
        previous_code = state.get('slide_code', {}).get(1, '')
        critique_prompt = f"\n\n**FEEDBACK ON PREVIOUS VERSION:**\n{critique}\n\n**PREVIOUS CODE:**\n{previous_code}\n\n**Instruction:** Refactor the Previous Code to fix the issues. Keep what works, fix what doesn't."

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Create a high-quality interactive presentation for this topic.\n\nContext:\n{storyboard}\n\nVersion: {version}{critique_prompt}")
    ]
    
    # Validation Loop
    max_retries = 3
    current_try = 0
    
    while current_try < max_retries:
        # Optimization: Use Flash for retries (Syntax Fixing)
        current_llm = llm_pro if current_try == 0 else llm_flash
        
        response = current_llm.invoke(messages)
        
        # Robust Content Parsing
        content = response.content
        if isinstance(content, list):
            parsed_parts = []
            for c in content:
                if isinstance(c, dict) and 'text' in c:
                    parsed_parts.append(c['text'])
                elif hasattr(c, 'text'):
                    parsed_parts.append(c.text)
                else:
                    parsed_parts.append(str(c))
            content = " ".join(parsed_parts)
        else:
            content = str(content)
            
        code = content
        # Try to extract code block with regex
        import re
        match = re.search(r"```(?:tsx|jsx|javascript|typescript)?\s*(.*?)```", content, re.DOTALL)
        if match:
            code = match.group(1).strip()
        else:
            # Fallback: simple replace if no block found (or just one block without closer)
            code = content.replace("```jsx", "").replace("```tsx", "").replace("```", "").strip()
        
        # Self-Correction Check
        is_valid = True
        error_msg = ""
        
        if code.startswith("{") and "type" in code and "text" in code:
            is_valid = False
            error_msg = "Error: You outputted a Python dictionary string instead of raw React code."
        elif "import React" not in code and "export default" not in code:
             is_valid = False
             error_msg = "Error: Code must include imports and export default."
             
        if is_valid:
            # Save Artifact
            from app.utils import save_artifact
            save_artifact(f"slide_v{version}", code, "tsx")
            
            return {
                "slide_code": {1: code}, 
                "messages": [SystemMessage(content=f"Slide Code Generated (v{version}).")]
            }
        
        # If failed, add to history and retry
        print(f"⚠️ Architect Handled Error: {error_msg}. Retrying...")
        messages.append(HumanMessage(content=f"SYSTEM_ALERT: {error_msg} Please output ONLY the raw React TSX code. Do not wrap in JSON."))
        current_try += 1

    # Fallback if all retries fail
    return {
        "slide_code": {},
        "messages": [SystemMessage(content="Failed to generate valid code after 3 attempts.")]
    }
