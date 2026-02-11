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
        [venv_python, "-m", "uvicorn", "app.main:app", "--port", "8000"],
        cwd=os.path.join(os.getcwd(), "backend"),
        env=backend_env
    )

    # 2. Start LLaMA Server (Local LLM)
    print("🔹 Launching LLaMA Server (port 8080)...")
    llama_bin = "/home/hgeon/gravity/LangAIAgent/llama.cpp/build/bin/llama-server"
    llama_model = "/home/hgeon/models/llama4_scout/meta-llama_Llama-4-Scout-17B-16E-Instruct-Q4_K_M/meta-llama_Llama-4-Scout-17B-16E-Instruct-Q4_K_M-00001-of-00002.gguf"
    
    # Check if files exist
    if not os.path.exists(llama_bin) or not os.path.exists(llama_model):
        print("⚠️ LLaMA binary or model not found. Skipping Local LLM.")
        llama_process = None
    else:
        try:
            print("⏳ Starting LLaMA Server... (Check logs below)")
            # RTX 5090 (32GB VRAM) safe settings:
            # - Context (-c): 16384 (16k) - balances capacity vs memory
            # - GPU Layers (-ngl): 16 - partial offload for MoE model
            # WARNING: 32k context causes OOM and system crash!
            llama_process = subprocess.Popen(
                [llama_bin, "-m", llama_model, "--port", "8080", "-c", "16384", "-ngl", "16"],
                stdout=None, 
                stderr=None
            )
            print("✅ LLaMA Server Process Launched.")
        except Exception as e:
            print(f"❌ Failed to start LLaMA: {e}")
            llama_process = None

    # 3. Start Frontend
    print("🔹 Launching Frontend (vite)...")
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev", "--", "--host"],
        cwd=os.path.join(os.getcwd(), "frontend"),
        stdout=None, 
        stderr=None
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
        # Kill Frontend
        if frontend_process.poll() is None:
             # Try to kill process group if possible
            try:
                os.killpg(os.getpgid(frontend_process.pid), signal.SIGTERM)
            except:
                frontend_process.terminate()
        
        # Kill Backend
        if backend_process.poll() is None:
             backend_process.terminate()

        # Kill LLaMA
        if llama_process and llama_process.poll() is None:
            print("🛑 Stopping LLaMA Server...")
            llama_process.terminate()
        
        print("👋 System Shutdown Complete.")

if __name__ == "__main__":
    run_system()
