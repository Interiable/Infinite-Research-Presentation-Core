import subprocess
import time
import os
import signal
import sys
import webbrowser

def run_system():
    print("🚀 Starting Infinite Research Agent System...")

    # 1. Start Backend
    print("🔹 Launching Backend (uvicorn)...")
    # We assume 'venv' is in backend/venv
    backend_env = os.environ.copy()
    
    # Check if venv exists
    venv_python = os.path.join(os.getcwd(), "backend", "venv", "bin", "python")
    if not os.path.exists(venv_python):
        print(f"❌ Virtual Environment not found at {venv_python}")
        print("Please run 'cd backend && python3 -m venv venv && pip install -r requirements.txt'")
        sys.exit(1)

    backend_process = subprocess.Popen(
        [
            venv_python, "-m", "uvicorn", "app.main:app", "--port", "8000",
            # WebSocket keepalive tolerance: heavy local-LLM phases (Deep Research
            # synthesis) can block the event loop for a while. Without a generous
            # ping timeout, uvicorn drops the WS connection mid-research.
            "--ws-ping-interval", "30",      # send a ping every 30s
            "--ws-ping-timeout", "600",      # tolerate up to 10 min before closing
            "--timeout-keep-alive", "75",    # HTTP keep-alive tolerance
        ],
        cwd=os.path.join(os.getcwd(), "backend"),
        env=backend_env,
        preexec_fn=os.setsid # Create new process group
    )

    # 2. Start LLaMA Server (RETIRED: Now using Ollama via local_model.py)
    # print("🔹 Launching LLaMA Server (port 8080)...")
    # llama_bin = "/home/hgeon/gravity/LangAIAgent/llama.cpp/build/bin/llama-server"
    # llama_model = "/home/hgeon/models/llama4_scout/meta-llama_Llama-4-Scout-17B-16E-Instruct-Q4_K_M/meta-llama_Llama-4-Scout-17B-16E-Instruct-Q4_K_M-00001-of-00002.gguf"
    
    # # Check if files exist
    # if not os.path.exists(llama_bin) or not os.path.exists(llama_model):
    #     print("⚠️ LLaMA binary or model not found. Skipping Local LLM.")
    #     llama_process = None
    # else:
    #     try:
    #         print("⏳ Starting LLaMA Server... (DISABLED: Managed by Ollama)")
    #         # llama_process = subprocess.Popen(...)
    llama_process = None

    # 3. Start Frontend
    print("🔹 Launching Frontend (vite)...")
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev", "--", "--host"],
        cwd=os.path.join(os.getcwd(), "frontend"),
        stdout=None, 
        stderr=None,
        preexec_fn=os.setsid # Create new process group
    )

    print("✅ System Online!")
    print("   - Mission Control: http://localhost:5174")
    print("   - API Server:      http://localhost:8000")
    print("   - LLaMA Server:    http://localhost:8080")
    print("   - Press Ctrl+C to stop manually.")

    # 4. Open Browser
    time.sleep(3) 
    webbrowser.open("http://localhost:5174")

    try:
        while True:
            # Check if backend is alive
            if backend_process.poll() is not None:
                print("⚠️ Backend server has stopped. Shutting down system...")
                break
            
            # Check if frontend is alive
            if frontend_process.poll() is not None:
                print("⚠️ Frontend server has stopped. Shutting down system...")
                break
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Manual Stop received.")
    finally:
        print("Cleaning up processes...")
        
        def kill_process_group(proc, name):
            """Two-stage kill: SIGTERM (graceful) → SIGKILL (forced)"""
            if proc and proc.poll() is None:
                print(f"🛑 Stopping {name} Server (Process Group)...")
                try:
                    pgid = os.getpgid(proc.pid)
                    # Stage 1: Graceful SIGTERM
                    os.killpg(pgid, signal.SIGTERM)
                    # Wait up to 2 seconds for graceful shutdown
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        # Stage 2: Force SIGKILL
                        print(f"   ⚡ {name} didn't stop gracefully. Force killing...")
                        os.killpg(pgid, signal.SIGKILL)
                        proc.wait(timeout=3)
                except Exception as e:
                    print(f"⚠️ Failed to kill {name} process group: {e}. Forcing termination...")
                    proc.kill() # Last resort
        
        # Kill Frontend Process Group
        kill_process_group(frontend_process, "Frontend")
        
        # Kill Backend Process Group
        kill_process_group(backend_process, "Backend")

        # Kill LLaMA (If active)
        if llama_process and llama_process.poll() is None:
            print("🛑 Stopping LLaMA Server...")
            llama_process.terminate()
        
        # --- FINAL SAFETY NET: Force-release port 8000 ---
        try:
            subprocess.run(["fuser", "-k", "8000/tcp"], 
                          capture_output=True, timeout=3)
        except Exception:
            pass  # Best-effort cleanup
        
        print("👋 System Shutdown Complete.")

if __name__ == "__main__":
    run_system()
