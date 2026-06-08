import os
import json
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.state import AgentState
from app.utils import RobustGemini, log_night_audit

# --- CONFIGURATION ---
llm_flash = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash"), 
    temperature=0.0, 
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    timeout=120,
    max_retries=2
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
3. **LANGUAGE**: All visible text MUST be in **English**.

**TECHNICAL CONSTRAINTS:**
- **Navigation**: The main component handles state (`currSlide`).
- **Layout**: Full height (`h-full`), flex column.
"""

def extract_json(text):
    """Robust JSON extractor"""
    try:
        if isinstance(text, list):
            parsed_parts = []
            for c in text:
                if isinstance(c, dict) and 'text' in c:
                    parsed_parts.append(c['text'])
                elif hasattr(c, 'text'):
                    parsed_parts.append(c.text)
                else:
                    parsed_parts.append(str(c))
            text = "".join(parsed_parts)
            
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match: return json.loads(match.group(1))
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match: return json.loads(match.group(1))
        return json.loads(text)
    except:
        return None

def extract_code(text):
    """Robust Code extractor"""
    if isinstance(text, list):
        parsed_parts = []
        for c in text:
            if isinstance(c, dict) and 'text' in c:
                parsed_parts.append(c['text'])
            elif hasattr(c, 'text'):
                parsed_parts.append(c.text)
            else:
                parsed_parts.append(str(c))
        text = "".join(parsed_parts)
        
    match = re.search(r"```(?:tsx|jsx|javascript|typescript)?\s*(.*?)```", text, re.DOTALL)
    if match: return match.group(1).strip()
    return text.replace("```", "").strip()

def architect_node(state: AgentState, config):
    try:
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        
        # Input Source
        content = state.get('storyboard', '') or state.get('shared_knowledge', '') or "No Content"
        current_index = state.get('current_step_index', 0)
        current_sub_idx = state.get('current_sub_step_index', 0)
        version = state.get('iteration_count', 0)
        
        # Critique Handling
        critique = state.get('critique_feedback', '')
        critique_prompt = ""
        if critique:
            previous_code = state.get('slide_code', {}).get(1, '')
            critique_prompt = f"\n\n**CRITICAL FEEDBACK (FIX REQUIRED):**\n{critique}\n\n**PREVIOUS CODE:**\n{previous_code}\n\n**INSTRUCTION:** Refactor the previous code to address the feedback."
        
        print(f"🎨 Architect Started. Version: {version}")

        # 1. Multi-Concept Blueprinting & Loop
        concepts = [
            {"id": "A", "name": "경영진 요약 및 훅 (Executive & Strategic UX)"},
            {"id": "B", "name": "감성 스토리텔링 및 사용자 경험 (Emotional Journey)"},
            {"id": "C", "name": "로우레벨 아키텍처 및 센스-액션 플로우 (Tech Architecture)"}
        ]
        
        slide_codes = {}
        
        for concept in concepts:
            print(f"\n🌟 Phase 1: Blueprinting Concept {concept['id']} - {concept['name']}...")
            blueprint_prompt = f"""
            Analyze this report and outline a Slide Deck (1-3 slides) optimized for the theme: "{concept['name']}".
            The user explicitly wants this focused on Physical AI Robot PoC (companion forms like birds, moving TVs, not general humanoid). Fast Path vs Generative Path, Expression Design System.
            Report:
            {content[:15000]}...
            
            Output JSON ONLY:
            {{
              "slides": [
                {{ "id": 1, "type": "Title", "title": "Main Title", "key_points": ["Sub 1", "Sub 2"] }},
                {{ "id": 2, "type": "Concept", "title": "Section 1", "key_points": ["Point 1...", "Point 2..."] }}
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
                slides = [{"id": 1, "type": "Title", "title": "Physical AI PoC", "key_points": ["Review Full Report"]}]

            # 2. COMPONENT LOOP (Drafting each slide React Component)
            slide_components = []
            
            for i, slide in enumerate(slides):
                print(f"🔨 Phase 2: Building Concept {concept['id']} Slide {i+1}/{len(slides)}: {slide.get('title')}...")
                
                slide_prompt = f"""
                **Write React Code for Slide {i+1}**
                Theme Concept: {concept['name']}
                Type: {slide['type']}
                Title: {slide['title']}
                Points: {slide['key_points']}
                
                **STRICT TECHNICAL GUIDELINE:**
                - DO NOT use literal string escape characters like \\n or \\t in the code output.
                - Output actual newlines.
                - Use standard JSX syntax.
                - **NO External Data Visualization Libraries** (Do not use Recharts). Use flex/grid and Tailwind for visual layouts.
                - Ensure all icons used are from the available Lucide list: [ArrowRight, ArrowLeft, Check, Star, BarChart, BarChart3, PieChart, Activity, Globe, Shield, Terminal, Cpu, Zap, Layers, FileText, User, ArrowUpRight, ShieldCheck, Database].
                
                **Requirement:**
                - Create a verifiable `const Slide{i+1} = () => {{ ... }}` component.
                - **ENGLISH TEXT ONLY**.
                - Use `motion.div` from `framer-motion` for entrances.
                - Use `Lucide` icons.
                - Just output the FUNCTION COMPONENT code (No import statements).
                
                {critique_prompt}
                """
                
                try:
                    # Use Robust Gemini Pro for Coding
                    code_res = llm_pro.invoke([
                        SystemMessage(content=SYSTEM_PROMPT),
                        HumanMessage(content=slide_prompt)
                    ])
                    slide_components.append(extract_code(code_res.content))
                except Exception as e:
                    print(f"⚠️ Slide {i+1} Failed: {e}")
                    slide_components.append(f"const Slide{i+1} = () => <div className='p-10 text-white'>Error generating slide</div>")

            # 3. ASSEMBLY (Stitching it together into standalone HTML)
            print(f"🏗️ Phase 3: HTML Assembly for Concept {concept['id']}...")
            
            base_html = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Presentation - {CONCEPT_NAME}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script crossorigin src="https://unpkg.com/react@18/umd/react.development.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <script type="importmap">
    {
      "imports": {
        "framer-motion": "https://esm.sh/framer-motion@10.16.4",
        "lucide-react": "https://esm.sh/lucide-react@0.292.0"
      }
    }
  </script>
  <style>
    body, html, #root { height: 100%; margin: 0; background-color: #111827; }
  </style>
</head>
<body>
  <div id="root"></div>
  <script type="text/babel" data-type="module">
    const { useState, useEffect } = React;
    const { createRoot } = ReactDOM;
    import { motion, AnimatePresence } from 'framer-motion';
    import { 
      ArrowRight, ArrowLeft, Check, Star, BarChart, BarChart3, 
      PieChart, Activity, Globe, Shield, Terminal, 
      Cpu, Zap, Layers, FileText, User, ArrowUpRight, ShieldCheck, Database
    } from 'lucide-react';

    // === SLIDES GENERATED CODE ===
{SLIDE_COMPONENTS}

    const slides = [ {SLIDES_ARRAY} ];

    function Presentation() {
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

      const CurrentSlideComponent = slides[currentSlide].component;

      return (
        <div className="h-full w-full flex flex-col items-center justify-center text-white overflow-hidden font-sans selection:bg-cyan-500/30">
          <header className="fixed top-0 w-full h-16 bg-gray-900/80 backdrop-blur-md flex items-center justify-between px-6 z-50 border-b border-white/10">
            <div className="flex items-center gap-2">
                <Activity className="text-cyan-400 w-5 h-5" />
                <span className="font-bold tracking-wider text-sm text-gray-300">AI REPORT: {CONCEPT_NAME}</span>
            </div>
            <div className="flex items-center gap-4">
                <span className="text-sm font-mono text-gray-400">{currentSlide + 1} / {slides.length}</span>
                <div className="flex gap-2">
                    <button onClick={prevSlide} className="p-2 hover:bg-white/10 rounded-full transition-colors"><ArrowLeft className="w-5 h-5" /></button>
                    <button onClick={nextSlide} className="p-2 hover:bg-white/10 rounded-full transition-colors"><ArrowRight className="w-5 h-5" /></button>
                </div>
            </div>
          </header>

          <main className="w-full max-w-6xl h-full pt-20 pb-8 px-6 relative flex items-center justify-center">
            <AnimatePresence mode='wait'>
                <motion.div 
                    key={currentSlide}
                    initial={{ opacity: 0, scale: 0.95, y: 10 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 1.05, y: -10 }}
                    transition={{ duration: 0.4, ease: "easeInOut" }}
                    className="w-full flex justify-center items-center"
                >
                    <CurrentSlideComponent />
                </motion.div>
            </AnimatePresence>
          </main>
        </div>
      );
    }

    createRoot(document.getElementById('root')).render(<Presentation />);
  </script>
</body>
</html>
"""

            # String Replacements
            base_html = base_html.replace("{CONCEPT_NAME}", concept['name'])
            base_html = base_html.replace("{SLIDE_COMPONENTS}", "\n\n".join(slide_components))
            
            # Arrays logic
            slide_array_inner = ", ".join([f"{{ component: Slide{j+1} }}" for j in range(len(slide_components))])
            base_html = base_html.replace("{SLIDES_ARRAY}", slide_array_inner)

            # Save Output Locally
            from app.utils import save_artifact
            filename = f"Step{current_index+1}_Sub{current_sub_idx+1}_Slide_{concept['id']}_v{version+1}"
            save_artifact(filename, base_html, "html", thread_id=thread_id)
            
            slide_codes[concept['id']] = base_html
            
        return {
            "slide_code": slide_codes, 
            "messages": [SystemMessage(content=f"3 HTML Slide Concepts Generated Successfully.")]
        }
    except Exception as e:
        print(f"⚠️ Architect Node Critical Failure: {e}")
        log_night_audit("Architect", f"Critical Failure: {str(e)}")
        return {
            "slide_code": {1: "export default function Error() { return <div>Architect Critical Failure</div> }"},
            "messages": [SystemMessage(content=f"Architect Failed: {e}")]
        }
