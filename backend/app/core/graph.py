from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.core.state import AgentState
from app.agents.supervisor import supervisor_node
from app.agents.researcher import researcher_node
from app.agents.archivist import archivist_node
from app.agents.architect import architect_node

from app.agents.planner import planner_node

# Define the graph
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("SUPERVISOR", supervisor_node)
workflow.add_node("RESEARCHER", researcher_node)
workflow.add_node("ARCHIVIST", archivist_node)
workflow.add_node("ARCHITECT", architect_node)
workflow.add_node("PLANNER", planner_node) # New Node

# Define Logic for Routing
def router(state: AgentState):
    """
    Read the 'next' field from the state and route accordingly.
    """
    next_node = state.get("next", "SUPERVISOR")
    
    # Map 'next' string to actual Node Names
    if next_node == "RESEARCHER":
        return "RESEARCHER"
    elif next_node == "ARCHIVIST":
        return "ARCHIVIST"
    elif next_node == "ARCHITECT":
        return "ARCHITECT"
    elif next_node == "PLANNER":
        return "PLANNER"
    elif next_node == "END":
        return END
    else:
        return "SUPERVISOR" # Default back to Supervisor to re-evaluate

# Edges
# Start always goes to Supervisor to plan/route
workflow.add_edge(START, "SUPERVISOR")

# Workers always report back to Supervisor
workflow.add_edge("RESEARCHER", "SUPERVISOR")
workflow.add_edge("ARCHIVIST", "SUPERVISOR")
workflow.add_edge("ARCHITECT", "SUPERVISOR")
workflow.add_edge("PLANNER", "SUPERVISOR") # Planner reports back plan

# Conditional Edge from Supervisor
workflow.add_conditional_edges(
    "SUPERVISOR",
    router,
    {
        "RESEARCHER": "RESEARCHER",
        "ARCHIVIST": "ARCHIVIST",
        "ARCHITECT": "ARCHITECT",
        "PLANNER": "PLANNER",
        "SUPERVISOR": "SUPERVISOR",
        END: END
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
    conn = await aiosqlite.connect(DB_PATH)
    
    memory = AsyncSqliteSaver(conn)
    graph = workflow.compile(checkpointer=memory)
    return graph, conn

# We remove the global compile line.
# graph = workflow.compile(checkpointer=memory)
