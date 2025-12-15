import os
import logging
from langgraph.graph import StateGraph, END
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from shared.states import BlackboardState
from agents.supervisor import supervisor_logic
from agents.workers import drafter_agent, safety_guardian_agent, clinical_critic_agent
from agents.utilities import preprocessor_node, human_in_the_loop, finalizer_node

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------
# Async graph factory
# -------------------------
async def build_graph():
    # --- 1. Checkpointer ---
    db_path = os.path.join(os.getcwd(), "checkpoints.sqlite")
    conn = await aiosqlite.connect(db_path)
    checkpointer = AsyncSqliteSaver(conn)

    # --- 2. Execution wrapper ---
    def execute_and_log(node_name, agent_func, *args, **kwargs):
        logger.info(f"[GRAPH] Entering node: {node_name}")
        return agent_func(*args, **kwargs)

    # --- 3. Graph ---
    graph_builder = StateGraph(BlackboardState)

    graph_builder.add_node(
        "drafter_agent",
        lambda *a, **k: execute_and_log("drafter_agent", drafter_agent, *a, **k)
    )
    graph_builder.add_node(
        "preprocessor",
        lambda *a, **k: execute_and_log("preprocessor", preprocessor_node, *a, **k)
    )
    graph_builder.add_node(
        "safety_guardian_agent",
        lambda *a, **k: execute_and_log("safety_guardian_agent", safety_guardian_agent, *a, **k)
    )
    graph_builder.add_node(
        "clinical_critic_agent",
        lambda *a, **k: execute_and_log("clinical_critic_agent", clinical_critic_agent, *a, **k)
    )
    graph_builder.add_node(
        "supervisor",
        lambda *a, **k: execute_and_log("supervisor", supervisor_logic, *a, **k)
    )
    graph_builder.add_node(
        "human_in_the_loop",
        lambda *a, **k: execute_and_log("human_in_the_loop",human_in_the_loop, *a, **k)
    )
    graph_builder.add_node(
        "finalizer_node",
        lambda state, config: execute_and_log(
            "finalizer_node", finalizer_node, state, config
        )
    )

    # --- 4. Edges ---
    graph_builder.set_entry_point("drafter_agent")
    graph_builder.add_edge("drafter_agent", "preprocessor")

    def route_from_preprocessor(state: BlackboardState):
        # First run → full parallel evaluation
        if not state.get("is_revision", False):
            return ["safety_guardian_agent", "clinical_critic_agent"]

        # Revision → targeted re-evaluation
        reasons = state.get("reason_for_revision", '')
        logger.info(f"[GRAPH] Reason for revision: {reasons}")

        routes = []
        if reasons =="SAFETY_FAILURE":
            routes.append("safety_guardian_agent")
        if reasons =="CLINICAL_FAILURE":
            routes.append("clinical_critic_agent")
        if reasons == None:
            routes.append("safety_guardian_agent")
            routes.append("clinical_critic_agent")

        return routes
    
    graph_builder.add_conditional_edges(
        "preprocessor",
        route_from_preprocessor
        )

    graph_builder.add_edge("safety_guardian_agent", "supervisor")
    graph_builder.add_edge("clinical_critic_agent", "supervisor")

    def route_from_supervisor(state: BlackboardState):
        next_action = state.get("next_action", "drafter_agent")
        context = state.get("execution_context", "M2M_API")

        if next_action == "human_in_the_loop" and context == "M2M_API":
            logger.warning("[GRAPH] Bypassing HIL for M2M_API")
            return "finalizer_node"

        return next_action

    graph_builder.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "drafter_agent": "drafter_agent",
            "human_in_the_loop": "human_in_the_loop",
            "finalizer_node": "finalizer_node",
        },
    )

    graph_builder.add_edge("human_in_the_loop", "supervisor")
    

    graph_builder.add_edge("finalizer_node", END)

    app = graph_builder.compile(checkpointer=checkpointer)
    logger.info("LangGraph compiled successfully.")

    return app
