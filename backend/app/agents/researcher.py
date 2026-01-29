import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import Tool

from app.core.state import AgentState

# Gemini 3 Flash for fast, grounded research
# Note: Using 'gemini-1.5-flash' logic as placeholder for 'gemini-3.0-flash'
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash", 
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
Your goal is to find concrete, factual, and latest information on the user's topic.
Use the Search tools to find data.
Output a synthesized summary of what you found.
Do NOT just list links. Explain *what* the links say.
"""

def researcher_node(state: AgentState):
    """
    Scans the web for the topic.
    """
    topic = state.get('research_topic', 'Unknown Topic')
    
    # In a real version, we'd invoke the search tool. 
    # Here we simulate the LLM using its internal knowledge + (potential) grounding tool

    # Context Injection: Pass Local Knowledge to the Deep Researcher
    local_context = state.get('local_knowledge', '')
    context_prompt = ""
    if local_context:
        context_prompt = f"\n\n**Internal Knowledge (Local Files):**\n{local_context}\n\n**Instruction:** Integrate this local knowledge. If the web contradicts it, note the conflict. If it supports it, strengthen the argument."

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Research this topic deeply: {topic}. Focus on recent developments (2024-2026).{context_prompt}")
    ]
    
    response = llm.invoke(messages)
    
    return {
        "web_knowledge": response.content,
        "shared_knowledge": f"Web Research Summary:\n{response.content}", # Append
        "messages": [SystemMessage(content=f"Research Complete for: {topic}")]
    }
