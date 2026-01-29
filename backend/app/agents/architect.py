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
Your goal is to write **Production-Ready React Code** for a **Multi-Slide Presentation**.
You use **Tailwind CSS** and **Framer Motion**.

**Requirements:**
1.  **Structure**: Create a main `Presentation` component that manages state to switch between **at least 3 slides**.
2.  **Navigation**: Include "Next" and "Previous" buttons inside the component to navigate.
3.  **Content**: Based on the user's topic, create 3 distinct slides (e.g., Title, Key Data, Conclusion).
4.  **Visuals**: Use `framer-motion` for smooth transitions between slides (e.g., slide-in/out).
5.  **Output**: ONLY the React component code.
6.  **Styling**: Use the 'cyber' and 'neon' custom colors.
"""

def architect_node(state: AgentState):
    storyboard = state.get('storyboard', '')
    version = state.get('current_version', 1)
    
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Create a high-quality interactive presentation for this topic.\n\nContext:\n{storyboard}\n\nVersion: {version}")
    ]
    
    response = llm.invoke(messages)
    code = response.content.replace("```jsx", "").replace("```tsx", "").replace("```", "")
    
    return {
        "slide_code": {1: code}, # Updating slide 1 for now
        "messages": [SystemMessage(content="Slide Code Generated.")]
    }
