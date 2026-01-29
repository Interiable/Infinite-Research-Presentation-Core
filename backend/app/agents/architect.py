import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.state import AgentState

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro", # Placeholder for gemini-3.0-pro-coding
    temperature=0.0,
    google_api_key=os.getenv("GOOGLE_API_KEY")
)

SYSTEM_PROMPT = """
You are the **Infographic Architect**.
Your goal is to write **Production-Ready React Code** for the slides.
You use **Tailwind CSS** and **Framer Motion**.

**Rules:**
1.  **Output**: ONLY the React component code. No markdown backticks if possible, or strip them.
2.  **Visuals**: Use `framer-motion` for entrances.
3.  **Placeholders**:
    -   Do NOT generate static images (`<img>` tags with fake URLs).
    -   Use `<div className="w-full h-64 bg-gray-800 flex items-center justify-center border border-neon-green">Video Placeholder</div>`
4.  **Styling**: Use the 'cyber' and 'neon' custom colors defined in tailwind.config.js.
5.  **Component Name**: Must be `SlideV{version}Page{number}`.
"""

def architect_node(state: AgentState):
    storyboard = state.get('storyboard', '')
    version = state.get('current_version', 1)
    
    # Logic to split storyboard into slides would go here.
    # For now, we generate a single "Mega Slide" or just the first slide as a demo.
    
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Create a React component for this storyboard segment.\n\nStoryboard:\n{storyboard}\n\nVersion: {version}")
    ]
    
    response = llm.invoke(messages)
    code = response.content.replace("```jsx", "").replace("```tsx", "").replace("```", "")
    
    return {
        "slide_code": {1: code}, # Updating slide 1 for now
        "messages": [SystemMessage(content="Slide Code Generated.")]
    }
