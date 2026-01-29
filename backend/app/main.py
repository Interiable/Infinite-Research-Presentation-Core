import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Infinite Research Agent Core", version="2026.1.0")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.endpoints import router as api_router

app.include_router(api_router, prefix="/api")

@app.on_event("startup")
async def startup_event():
    research_dir = os.getenv("LOCAL_RESEARCH_DIR")
    if not research_dir:
        print("WARNING: LOCAL_RESEARCH_DIR is not set in .env")
        # In a real CLI scenario, we might prompt here, but for now we just log.
    else:
        print(f"INFO: Local Research Directory set to: {research_dir}")

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "2026.1.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
