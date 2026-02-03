import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import Tool

from app.core.state import AgentState

# Gemini 3 Flash for fast, grounded research
# Note: Using 'gemini-1.5-flash' logic as placeholder for 'gemini-3.0-flash'
llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview", 
    temperature=0.0, 
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    # Enable Google Search Grounding
    # tools=[GoogleSearchRetrieval] # Requires updated langchain library support
    # For now, we use the `google_search` keyword in the tool binding if available, 
    # or rely on the model's native ability if configured.
    # We will simulate the "Deep Research" behavior effectively.
    model_kwargs={"tools": [{"google_search": {}}]} # Native grounding trigger for some versions
)

SYSTEM_PROMPT = """
You are the **Deep Researcher** for the team.
Your goal is to build a **Comprehensive, Long-Form Report** on the user's topic.
Use the Search tools to find concrete, factual data.
**CRITICAL RULE:** Do NOT summarize. Do NOT shorten.
**ACTION:** You must **ACCUMULATE** information.
- **Restructure** the report if needed for better flow.
- **Correct** previous information if new data proves it wrong.
- **Merge** redundant sections intelligently.
- **NEVER DELETE** valid details. If in doubt, keep it.
Output a structured report with clear sections.
"""

from app.agents.local_model import local_llm

def researcher_node(state: AgentState):
    """
    Scans the web for the topic OR Refines existing content based on critique.
    Tiered Strategy: Skips 'Google Search' if mode is 'refine' to save cost/time.
    """
    topic = state.get('research_topic', 'Unknown Topic')
    mode = state.get('research_mode', 'deep') # Default to deep

    # Context Injection
    local_context = state.get('local_knowledge', '')
    critique = state.get('storyboard_critique', '')
    previous_summary = state.get('shared_knowledge', '') or state.get('web_knowledge', '')
    
    context_prompt = ""
    if local_context:
        context_prompt += f"\n\n**Internal Knowledge (Local Files):**\n{local_context}\n\n**Instruction:** Integrate this local knowledge."
        
    if critique:
        context_prompt += f"\n\n**Create Critique (Reason for Revision):**\n{critique}\n\n**PREVIOUS DRAFT:**\n{previous_summary}"

    # DECISION: Deep Search vs Refinement
    if mode == "refine":
        # Cost Optimization: Do NOT use Search Tools. Just rewrite.
        task_prompt = f"""
        **MODE: REFINEMENT & EXPANSION**
        You are tasked with **EVOLVING** the previous report based on the critique.
        
        **CRITICAL INSTRUCTION:** 
        1. **INTEGRATE** the `PREVIOUS DRAFT` as your base.
        2. **EXPAND** with new details to address the `Critique`.
        3. **RESTRUCTURE** if necessary to make the report logical and coherent.
        4. **CORRECT** any factual errors found in the previous draft.
        5. **DO NOT SUMMARIZE**. Keep all specific numbers, dates, and technical details.
        
        Topic: {topic}
        Critique: {critique}
        
        Action: output the **FULL UPDATED REPORT**. It should be LONGER, MORE ACCURATE, and BETTER STRUCTURED than before.
        """
        # Switching to Local LLM for Pure Refinement
        print("⚡ Using Local LLM for Refinement Task...")
        try:
            response = local_llm.invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=task_prompt)
            ])
        except Exception as e:
            print(f"⚠️ Local LLM Failed: {e}. Falling back to Cloud Flash.")
            response = llm.invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=task_prompt)
            ])

    else:
        # Standard Deep Research (Cloud)
        task_prompt = f"""
        Research this topic deeply: {topic}. 
        Focus on recent developments (2024-2026).
        
        **CONTEXT:**
        {context_prompt}
        
        **INSTRUCTION:**
        If there is a `PREVIOUS DRAFT`, you must **EVOLVE** it with new findings.
        - **Integrate** new facts into the existing body to create a seamless report.
        - **Update** old sections with newer data.
        - **Expand** on brief sections.
        Do not output a separate summary. Output one cohesive, detailed report.
        """
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=task_prompt)
        ])
    
    # Robust Content Parsing
    content = response.content
    if isinstance(content, list):
        content = " ".join([str(c) for c in content])
    else:
        content = str(content)

    # Save Artifact
    from app.utils import save_artifact
    save_artifact("research_summary", content, "md")
    
    return {
        "web_knowledge": content,
        "shared_knowledge": f"Research Summary ({mode}):\n{content}", 
        "messages": [SystemMessage(content=f"Research Complete ({mode}): {topic}")]
    }
