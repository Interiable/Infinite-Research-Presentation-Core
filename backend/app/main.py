import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    research_dir = os.getenv("LOCAL_RESEARCH_DIR")
    if not research_dir:
        print("WARNING: LOCAL_RESEARCH_DIR is not set in .env")
    else:
        print(f"INFO: Local Research Directory set to: {research_dir}")
    
    # Initialize Graph & DB
    from app.core import graph as graph_module
    print("INFO: Initializing Graph & Persistence...")
    compiled_graph, db_conn = await graph_module.init_graph()
    
    # Store for global access if needed, though module-level variable in graph.py works too
    app.state.graph = compiled_graph
    app.state.db_conn = db_conn
    
    yield
    
    # Shutdown
    print("INFO: Closing Persistence Connection...")
    await db_conn.close()

app = FastAPI(title="Infinite Research Agent Core", version="2026.1.0", lifespan=lifespan)

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

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "2026.1.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
