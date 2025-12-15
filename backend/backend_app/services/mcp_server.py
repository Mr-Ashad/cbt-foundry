import asyncio
import uuid
import os
from typing import Dict, Any
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP 
from fastapi import HTTPException
import sys
import os
import traceback

from pathlib import Path



PROJECT_ROOT = Path(__file__).parent.parent 
sys.path.insert(0, str(PROJECT_ROOT))
from core.graph import build_graph
from core.sqlite_db import init_db
DB_PATH = str(Path(__file__).parent / "cerina_foundry.db")
# Import state models
from shared.states import BlackboardState 
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

_graph_app = None
_graph_lock = asyncio.Lock()

async def get_graph_app():
    global _graph_app

    if _graph_app is not None:
        return _graph_app

    async with _graph_lock:
        if _graph_app is None:
            _graph_app = await build_graph()

    return _graph_app


# --- 2. Define the MCP Interface Schemas ---

class ProtocolInput(BaseModel):
    """Input required by the MCP Client to start the tool."""
    user_goal: str = Field(
        ...,
        description="The user's specific request or goal for the clinical protocol, e.g., 'Create a sleep hygiene protocol based on CBT-I principles'."
    )

class ProtocolOutput(BaseModel):
    """Structured output returned to the MCP Client upon completion."""
    thread_id: str = Field(description="Unique ID for the completed workflow execution.")
    status: str = Field(description="Final status of the workflow ('COMPLETED', 'FAILED').")
    protocol_draft: str = Field(description="The final, safety-reviewed draft of the clinical protocol.")
    iteration_count: int = Field(description="Number of draft iterations performed.")


# --- 3. Implement the FastMCP Server and Tool ---

# Initialize the FastMCP server
mcp_app = FastMCP(
    name="CerinaFoundryProtocolCreator",
    json_response=True 
)

@mcp_app.tool()
async def create_clinical_protocol(input_data: ProtocolInput) -> ProtocolOutput:
    """
    Triggers the complex LangGraph workflow to create a fully reviewed clinical protocol, 
    bypassing Human-in-the-Loop steps for a single M2M request/response cycle.
    """
    
    thread_id = str(uuid.uuid4())
    user_intent = input_data.user_goal.strip()
    
    # ⭐️ KEY STEP: Set the execution_context flag to 'M2M_API' to trigger the HIL bypass in the graph router ⭐️
    initial_state = BlackboardState(
        user_intent=user_intent,
        status="STARTING",
        thread_id= thread_id,
        execution_context="M2M_API" 
    )
    
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # We use app.invoke (your compiled LangGraph)
        # It must be run in a separate thread since it's synchronous
        app = await get_graph_app()

        final_state: BlackboardState = await app.ainvoke(
            initial_state,
            config=config
        )
    except Exception as e:
        print(f"CRITICAL ERROR IN MCP WORKFLOW (Thread ID: {thread_id}): {str(e)}")
        # Raise an HTTPException for the MCP client to handle failure
        print("❌ ERROR DURING app.invoke()", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

        raise HTTPException(
            status_code=500, 
            detail=f"Cerina Foundry Workflow failed: {str(e)}"
        )

    # Map the final LangGraph state to the external ProtocolOutput schema
    return ProtocolOutput(
        thread_id=thread_id,
        status=final_state.get("status"),
        protocol_draft=final_state.get("current_draft"),
        iteration_count=final_state.get("iteration_count", 0),
    )




def start_mcp_server(host="0.0.0.0", port=8001):
    """Initializes and starts the MCP server."""
    print(f"\n--- Starting Cerina Foundry MCP Server on http://{host}:{port} ---")
    print("M2M Endpoint: /mcp-docs (for discovery)")
    print("Tool Function: create_clinical_protocol")
    
    import uvicorn
    uvicorn.run(mcp_app.app, host=host, port=port)

if __name__ == "__main__":
    init_db()
    mcp_app.run()
