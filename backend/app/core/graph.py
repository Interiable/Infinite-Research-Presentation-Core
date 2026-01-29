from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.core.state import AgentState
from app.agents.supervisor import supervisor_node
from app.agents.researcher import researcher_node
from app.agents.archivist import archivist_node
from app.agents.architect import architect_node

# Define the graph
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("SUPERVISOR", supervisor_node)
workflow.add_node("RESEARCHER", researcher_node)
workflow.add_node("ARCHIVIST", archivist_node)
workflow.add_node("ARCHITECT", architect_node)

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

# Conditional Edge from Supervisor
workflow.add_conditional_edges(
    "SUPERVISOR",
    router,
    {
        "RESEARCHER": "RESEARCHER",
        "ARCHIVIST": "ARCHIVIST",
        "ARCHITECT": "ARCHITECT",
        "SUPERVISOR": "SUPERVISOR",
        END: END
    }
)

# Persistence
memory = MemorySaver()

# Compile
graph = workflow.compile(checkpointer=memory)
