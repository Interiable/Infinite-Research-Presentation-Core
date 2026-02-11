import subprocess
import time
import os
import sys
import threading

def run_share():
    print("🚀 Starting Infinite Research Agent System (Mobile Access Mode)...")

    # 0. Start the Local LLM Server (llama.cpp)
    print("🧠 Starting Local LLM Server (LLaMA 4 Scout)...")
    llm_process = subprocess.Popen(["bash", "scripts/run_llama_server.sh"], 
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    # Wait for server to be ready
    print("⏳ Waiting for LLM server to load (this may take a minute for 60GB model)...")
    time.sleep(2) # Brief pause to allow process to start

    # 1. Start the System (Backend + Frontend)
    system_process = subprocess.Popen([sys.executable, "run_system.py"])
    
    print("⏳ Waiting for system to initialize (10s)...")
    time.sleep(10)
    
    # 2. Start LocalTunnel
    print("🌍 Establishing Secure Tunnel to Mission Control...")
    print("   (This may take a few seconds to request a public URL)")
    
    try:
        # Check if npx is available
        subprocess.run(["npx", "--version"], stdout=subprocess.DEVNULL, check=True)
        
        # Fetch Public IP for Tunnel Password
        try:
            import urllib.request
            print("🔐 Fetching Tunnel Password (Public IP)...")
            with urllib.request.urlopen('https://api.ipify.org') as response:
                public_ip = response.read().decode('utf-8')
        except Exception:
            public_ip = "Could not fetch IP. Please search 'What is my IP' on this computer."

        # Start lt for port 5174
        # We use a subprocess and try to grep the URL if possible, or just let it print to stdout
        tunnel_process = subprocess.Popen(
            ["npx", "-y", "localtunnel", "--port", "5174"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Read the URL line
        if tunnel_process.stdout:
            while True:
                line = tunnel_process.stdout.readline()
                if line:
                    if "your url is" in line.lower():
                        print("\n" + "="*60)
                        print(f"📱 MOBILE ACCESS LINK: {line.strip()}")
                        print(f"🔑 TUNNEL PASSWORD:   {public_ip}")
                        print("="*60 + "\n")
                        print("👉 Open the link and enter the Password above if prompted.")
                        break
                else:
                    if tunnel_process.poll() is not None:
                        print("❌ Tunnel process exited unexpectedly.")
                        break
                    time.sleep(0.5)
                    
        # Keep alive
        system_process.wait()
        
    except FileNotFoundError:
        print("❌ 'npx' not found. Please install Node.js/npm.")
    except KeyboardInterrupt:
        print("\nStopping Tunnel...")
        if 'tunnel_process' in locals(): tunnel_process.terminate()
        system_process.terminate()

if __name__ == "__main__":
    run_share()
