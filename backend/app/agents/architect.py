import os
import json
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.state import AgentState
from app.utils import RobustGemini

# --- CONFIGURATION ---
llm_flash = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview", 
    temperature=0.0, 
    google_api_key=os.getenv("GOOGLE_API_KEY")
)

# Robust Polyglot Model for Coding
llm_pro = RobustGemini(temperature=0.0)

SYSTEM_PROMPT = """
You are the **Lead UI/UX Architect**.
Your goal is to build a **Stunning, Interactive React Presentation**.
Stack: **Tailwind CSS**, **Framer Motion**, **Lucide React**.

**DESIGN RULES:**
1. **Visual-First**: Use Charts, Icons, and Grids. Avoid walls of text.
2. **Modern**: Glassmorphism, gradients, clean typography.
3. **LANGUAGE**: All visible text MUST be in **Korean**.

**TECHNICAL CONSTRAINTS:**
- **Navigation**: The main component handles state (`currSlide`).
- **Layout**: Full height (`h-full`), flex column.
"""

def extract_json(text):
    """Robust JSON extractor"""
    try:
        if isinstance(text, list): text = str(text)
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match: return json.loads(match.group(1))
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match: return json.loads(match.group(1))
        return json.loads(text)
    except:
        return None

def extract_code(text):
    """Robust Code extractor"""
    if isinstance(text, list): text = str(text)
    match = re.search(r"```(?:tsx|jsx|javascript|typescript)?\s*(.*?)```", text, re.DOTALL)
    if match: return match.group(1).strip()
    return text.replace("```", "").strip()

def architect_node(state: AgentState, config):
    thread_id = config.get("configurable", {}).get("thread_id", "default")
    
    # Input Source
    content = state.get('storyboard', '') or state.get('shared_knowledge', '') or "No Content"
    version = state.get('current_version', 1)
    
    # Critique Handling
    critique = state.get('critique_feedback', '')
    critique_prompt = ""
    if critique:
        previous_code = state.get('slide_code', {}).get(1, '')
        critique_prompt = f"\n\n**CRITICAL FEEDBACK (FIX REQUIRED):**\n{critique}\n\n**PREVIOUS CODE:**\n{previous_code}\n\n**INSTRUCTION:** Refactor the previous code to address the feedback."
    
    print(f"🎨 Architect Started. Version: {version}")

    # 1. BLUEPRINTING (Structure)
    print("📐 Phase 1: Blueprinting Slide Deck...")
    blueprint_prompt = f"""
    Analyze this report and outline a Slide Deck (5-8 slides).
    Report:
    {content[:15000]}...
    
    Output JSON ONLY:
    {{
      "slides": [
        {{ "id": 1, "type": "Title", "title": "Main Title", "key_points": ["Sub 1", "Sub 2"] }},
        {{ "id": 2, "type": "Content", "title": "Section 1", "key_points": ["Chart data...", "Summary..."] }}
      ]
    }}
    """
    try:
        bp_res = llm_flash.invoke([HumanMessage(content=blueprint_prompt)])
        blueprint = extract_json(bp_res.content)
        slides = blueprint.get('slides', [])
        if not slides: raise Exception("Empty slides")
    except Exception as e:
        print(f"⚠️ Blueprint Failed: {e}. Fallback to default.")
        slides = [{"id": 1, "type": "Title", "title": "Report", "key_points": ["See full report"]}]

    # 2. COMPONENT LOOP (Drafting each slide)
    slide_components = []
    
    for i, slide in enumerate(slides):
        print(f"🔨 Phase 2: Building Slide {i+1}/{len(slides)}: {slide.get('title')}...")
        
        slide_prompt = f"""
        **Write React Code for Slide {i+1}**
        Type: {slide['type']}
        Title: {slide['title']}
        Points: {slide['key_points']}
        
        **Requirement:**
        - Create a verifiable `const Slide{i+1} = () => {{ ... }}` component.
        - **KOREAN TEXT ONLY**.
        - Use `framer-motion` for entrances.
        - Use `lucide-react` icons (e.g., Check, ArrowRight, BarChart).
        - **NO IMPORTS** (They will be added globally later).
        - Just output the FUNCTION COMPONENT code.
        
        {critique_prompt}
        """
        
        try:
            # Use Pro for coding
            code_res = llm_pro.invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=slide_prompt)
            ])
            code = extract_code(code_res.content)
            slide_components.append(code)
        except Exception as e:
            print(f"⚠️ Slide {i+1} Failed: {e}")
            slide_components.append(f"const Slide{i+1} = () => <div className='p-10'>Error generating slide</div>")

    # 3. ASSEMBLY (Stitching it together)
    print("🏗️ Phase 3: Final Assembly...")
    
    imports = """
import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ArrowRight, ArrowLeft, Check, Star, BarChart, 
  PieChart, Activity, Globe, Shield, Terminal, 
  Cpu, Zap, Layers, FileText, User
} from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RcTooltip, Legend, ResponsiveContainer } from 'recharts';
"""

    main_component_start = """
export default function Presentation() {
  const [currentSlide, setCurrentSlide] = useState(0);

  const nextSlide = () => setCurrentSlide(prev => (prev + 1) % slides.length);
  const prevSlide = () => setCurrentSlide(prev => (prev - 1 + slides.length) % slides.length);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'ArrowRight') nextSlide();
      if (e.key === 'ArrowLeft') prevSlide();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

"""

    # Create the 'slides' array text
    slide_array_str = "  const slides = [\n"
    for i in range(len(slide_components)):
        slide_array_str += f"    {{ component: Slide{i+1} }},\n"
    slide_array_str += "  ];\n"

    # Main Render
    main_render = """
  const CurrentSlideComponent = slides[currentSlide].component;

  return (
    <div className="h-full w-full bg-gray-900 text-white overflow-hidden font-sans selection:bg-cyan-500/30">
      {/* Header / Nav */}
      <header className="fixed top-0 w-full h-16 bg-gray-900/80 backdrop-blur-md flex items-center justify-between px-6 z-50 border-b border-white/10">
        <div className="flex items-center gap-2">
            <Activity className="text-cyan-400 w-5 h-5" />
            <span className="font-bold tracking-wider text-sm text-gray-300">AI REPORT</span>
        </div>
        <div className="flex items-center gap-4">
            <span className="text-sm font-mono text-gray-400">{currentSlide + 1} / {slides.length}</span>
            <div className="flex gap-2">
                <button onClick={prevSlide} className="p-2 hover:bg-white/10 rounded-full transition-colors"><ArrowLeft className="w-5 h-5" /></button>
                <button onClick={nextSlide} className="p-2 hover:bg-white/10 rounded-full transition-colors"><ArrowRight className="w-5 h-5" /></button>
            </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="h-full pt-16 relative">
        <AnimatePresence mode='wait'>
            <motion.div 
                key={currentSlide}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.4, ease: "easeInOut" }}
                className="h-full w-full"
            >
                <CurrentSlideComponent />
            </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
"""
    
    # Combine Everything
    full_code = imports + "\n\n" + "\n\n".join(slide_components) + "\n\n" + main_component_start + slide_array_str + main_render

    # Save Artifact
    from app.utils import save_artifact
    save_artifact(f"slide_v{version}", full_code, "tsx", thread_id=thread_id)
            
    return {
        "slide_code": {1: full_code}, 
        "messages": [SystemMessage(content=f"Slides Generated (Iterative Mode). Total Slides: {len(slides)}")]
    }
