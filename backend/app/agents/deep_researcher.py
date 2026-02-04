import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.state import AgentState
from app.core.state import AgentState
from app.utils import save_artifact
from langchain_community.utilities import GoogleSearchAPIWrapper

# SPECIALIZED DEEP RESEARCH ENGINE
# This model is used ONLY for intensive investigative tasks.
llm_deep = ChatGoogleGenerativeAI(
    model="deep-research-pro-preview-12-2025",
    temperature=0.2,
    google_api_key=os.getenv("GOOGLE_API_KEY")
)

SYSTEM_PROMPT = """
You are the **Specialized Deep Investigator**.
Your goal is to perform an exhaustive, multi-perspective investigation on a specific technical or research topic.

**LANGUAGE RULE (CRITICAL):**
1. **WRITE IN KOREAN**: The final report/output MUST be in **Korean**.
2. **Detail**: Provide extreme depth. Look for edge cases, technical specifications, and historical context.

**SOURCE MATERIAL:**
You will be provided with snippets or filenames from a local library. Focus your "thinking" on synthesizing these while using your internal vast knowledge to provide a "Deep Research" perspective.
"""

from langchain_core.runnables import RunnableConfig

def deep_researcher_node(state: AgentState, config: RunnableConfig):
    """
    Focused Investigative Node using the specialized Deep Research model.
    """
    # Extract Thread ID
    thread_id = config.get("configurable", {}).get("thread_id", None)
    topic = state.get('research_topic', 'Deep Investigation')
    mode = state.get('research_mode', 'deep')
    
    local_context = state.get('local_knowledge', '')
    web_context = ""

    # Web Research Trigger
    if mode == "deep_web" or "web" in topic.lower():
        print(f"🌍 Performing Web Research on: {topic}")
        try:
            search = GoogleSearchAPIWrapper()
            results = search.results(topic, 5)
            
            web_context = "\n\n**EXTERNAL WEB FINDINGS:**\n"
            for res in results:
                web_context += f"- [{res.get('title', 'No Title')}]({res.get('link', '#')}): {res.get('snippet', '')}\n"
            
            # Save Raw Data
            raw_data_path = f"data/{topic[:20].replace(' ', '_')}_raw.txt"
            os.makedirs("data", exist_ok=True)
            with open(raw_data_path, "w") as f:
                f.write(web_context)
            print(f"💾 Raw Search Data Saved: {raw_data_path}")
            
        except Exception as e:
            print(f"⚠️ Web Search Failed: {e}")
            web_context = "\n(Web Search Failed)"
    
    print(f"🧬 ACTIVATING SPECIALIZED DEEP RESEARCH ENGINE for: {topic}")
    
    prompt = f"""
    **STRICT TASK: PERFORM DEEP RESEARCH ON "{topic}"**
    
    **LOCAL KNOWLEDGE BASE (Context):**
    {local_context}

    **WEB FINDINGS (New Data):**
    {web_context}
    
    **INSTRUCTIONS:**
    1. Analyze the local context deeply.
    2. Provide a 100% Comprehensive Technical Report in **KOREAN**.
    3. Include sections for: [현황 분석, 핵심 기술 요약, 기술적 도전 과제, 미래 전망 및 결론].
    4. Cite any relevant file names mentioned in the context.
    """
    
    try:
        response = llm_deep.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ])
        report_content = response.content
    except Exception as e:
        report_content = f"Deep Research Model Failed: {e}"

    # Save individual investigative report
    save_artifact(f"deep_investigation_{topic[:20]}", report_content, "md", thread_id=thread_id)

    return {
        "sender": "DeepResearcher",
        "web_knowledge": report_content, # Store result in web_knowledge/shared_knowledge
        "shared_knowledge": f"--- SPECIALIZED DEEP RESEARCH RESULT ({topic}) ---\n{report_content}",
        "messages": [SystemMessage(content=f"Specialized Deep Research on '{topic}' completed using deep-research-pro-preview-12-2025.")]
    }
