from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
import asyncio

from app.core.state import AgentState
from app.agents.supervisor import supervisor_node
from app.agents.researcher import researcher_node
from app.agents.archivist import archivist_node
from app.agents.architect import architect_node

from app.agents.planner import planner_node
from app.agents.deep_researcher import deep_researcher_node
from app.agents.finalizer import finalizer_node
from app.agents.plan_refiner import plan_refiner_node
from app.agents.warden import warden_node

# v9.3: Async wrappers — run sync node functions in separate threads
# This keeps the asyncio event loop free for HTTP/WebSocket requests
async def async_supervisor_node(state, config=None):
    return await asyncio.to_thread(supervisor_node, state, config)

async def async_researcher_node(state, config=None):
    return await asyncio.to_thread(researcher_node, state, config)

async def async_deep_researcher_node(state, config=None):
    return await asyncio.to_thread(deep_researcher_node, state, config)

async def async_archivist_node(state, config=None):
    return await asyncio.to_thread(archivist_node, state)  # archivist_node takes state only

async def async_architect_node(state, config=None):
    return await asyncio.to_thread(architect_node, state, config)

async def async_planner_node(state, config=None):
    return await asyncio.to_thread(planner_node, state, config)

async def async_finalizer_node(state, config=None):
    return await asyncio.to_thread(finalizer_node, state, config)

async def async_plan_refiner_node(state, config=None):
    return await asyncio.to_thread(plan_refiner_node, state, config)

async def async_warden_node(state, config=None):
    return await asyncio.to_thread(warden_node, state, config)

# Define the graph
workflow = StateGraph(AgentState)

# Add Nodes (using async wrappers)
workflow.add_node("SUPERVISOR", async_supervisor_node)
workflow.add_node("RESEARCHER", async_researcher_node)
workflow.add_node("DEEP_RESEARCHER", async_deep_researcher_node)
workflow.add_node("ARCHIVIST", async_archivist_node)
workflow.add_node("ARCHITECT", async_architect_node)
workflow.add_node("PLANNER", async_planner_node)
workflow.add_node("FINALIZER", async_finalizer_node)
workflow.add_node("PLAN_REFINER", async_plan_refiner_node)
workflow.add_node("WARDEN", async_warden_node)

# Define Logic for Routing
def router(state: AgentState):
    """
    Read the 'next' field from the state and route accordingly.
    """
    next_node = state.get("next", "SUPERVISOR")
    
    # Map 'next' string to actual Node Names
    if next_node == "RESEARCHER":
        return "RESEARCHER"
    elif next_node == "DEEP_RESEARCHER":
        return "DEEP_RESEARCHER"
    elif next_node == "ARCHIVIST":
        return "ARCHIVIST"
    elif next_node == "ARCHITECT":
        return "ARCHITECT"
    elif next_node == "PLANNER":
        return "PLANNER"
    elif next_node == "WARDEN":
        return "WARDEN"
    elif next_node == "PLAN_REFINER":
        return "PLAN_REFINER"
    elif next_node == "FINALIZER":
        return "FINALIZER"
    elif next_node == "END":
        return "END"
    else:
        return "SUPERVISOR" # Default back to Supervisor to re-evaluate

# Edges
# Start always goes to Supervisor to plan/route
workflow.add_edge(START, "SUPERVISOR")

# Workers always report back to Supervisor
workflow.add_edge("RESEARCHER", "SUPERVISOR")
workflow.add_edge("DEEP_RESEARCHER", "SUPERVISOR")
workflow.add_edge("ARCHIVIST", "SUPERVISOR")
workflow.add_edge("ARCHITECT", "SUPERVISOR")
workflow.add_edge("FINALIZER", "SUPERVISOR") # Finalizer reports back for critique
workflow.add_edge("PLANNER", "SUPERVISOR") # Planner reports back plan
workflow.add_edge("PLAN_REFINER", "SUPERVISOR") # Sub-planner reports back
workflow.add_edge("WARDEN", "SUPERVISOR") # Warden reports back brief

# Conditional Edge from Supervisor
workflow.add_conditional_edges(
    "SUPERVISOR",
    router,
    {
        "RESEARCHER": "RESEARCHER",
        "DEEP_RESEARCHER": "DEEP_RESEARCHER",
        "ARCHIVIST": "ARCHIVIST",
        "ARCHITECT": "ARCHITECT",
        "PLANNER": "PLANNER",
        "WARDEN": "WARDEN",
        "PLAN_REFINER": "PLAN_REFINER",
        "FINALIZER": "FINALIZER",
        "SUPERVISOR": "SUPERVISOR",
        "END": END
    }
)

# Persistence (SQLite for Disk Storage)
import os
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# Resolve absolute path to backend directory
# app/core/graph.py -> app/core -> app -> backend
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "checkpoints.sqlite")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

graph = None

async def init_graph():
    global graph
    
    print(f"INFO: Connecting to Persistence DB at: {DB_PATH}")
    
    import aiosqlite
    # Use a long timeout and enable WAL for reliable async concurrency
    conn = await aiosqlite.connect(DB_PATH, timeout=60.0)
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA synchronous=NORMAL")
    await conn.execute("PRAGMA busy_timeout=30000")
    
    memory = AsyncSqliteSaver(conn)
    graph = workflow.compile(checkpointer=memory)
    return graph, conn

# We remove the global compile line.
# graph = workflow.compile(checkpointer=memory)
