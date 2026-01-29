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
        [venv_python, "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"],
        cwd=os.path.join(os.getcwd(), "backend"),
        env=backend_env
    )

    # 2. Start Frontend
    print("🔹 Launching Frontend (vite)...")
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev", "--", "--host"],
        cwd=os.path.join(os.getcwd(), "frontend"),
        stdout=subprocess.DEVNULL, # Keep frontend noisy logs quiet? Maybe let them show.
        stderr=subprocess.PIPE
    )

    print("✅ System Online!")
    print("   - Mission Control: http://localhost:5174")
    print("   - API Server:      http://localhost:8000")
    print("   - Press Ctrl+C to stop manually.")

    # 3. Open Browser
    time.sleep(3) # Wait for startup
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
            os.killpg(os.getpgid(frontend_process.pid), signal.SIGTERM) if hasattr(os, 'getpgid') else frontend_process.terminate()
        
        # Kill Backend
        if backend_process.poll() is None:
             backend_process.terminate()
        
        print("👋 System Shutdown Complete.")

if __name__ == "__main__":
    run_system()
