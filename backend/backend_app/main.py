import uuid
import asyncio
from core.sqlite_db import init_db
import traceback
import contextlib
from typing import AsyncIterator
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from langgraph.checkpoint.base import Checkpoint
from shared.states import BlackboardState, ClinicalReview
from langgraph.types import Command
from core.graph import build_graph
import logging
logger = logging.getLogger(__name__)

# --- 1. Pydantic Schemas  ---

class StartRequest(BaseModel):
    """Input to start the agent."""
    user_intent: str = Field(..., description="The user's request.")

class ApproveRequest(BaseModel):
    """
    MVP Requirement: 'The Human can Edit the text or Approve it.'
    This request carries the FINAL text (whether edited by human or not) to finalize the process.
    """
    thread_id: str
    final_draft: str = Field(..., description="The final text approved by the human.")


class ReviseRequest(BaseModel):
    """
    MVP Requirement: Feedback loop.
    Allows the human to send the draft back with edits or notes for the agent to fix.
    """
    thread_id: str
    edited_draft: str = Field(..., description="The draft text with human edits.")
    revision_notes: Optional[str] = Field(None, description="Instructions for the agent on what to fix.")

class StatusResponse(BaseModel):
    """Output schema for the UI visualization."""
    thread_id: str
    status: str
    current_draft: str
    iteration_count: int
    critique: Optional[ClinicalReview] = None
    agent_thoughts: List[Dict] = Field(default_factory=list)

# --- 2. FastAPI Setup ---

@contextlib.asynccontextmanager
async def lifespan_handler(app: FastAPI) -> AsyncIterator[None]:
    """
    Handles application startup and shutdown events.
    Used for resource initialization (like the database).
    """
    
    # --- STARTUP LOGIC ---
    try:
        # Run the synchronous init_db function in a separate thread
        await asyncio.to_thread(init_db)
        logger.info("Sqlite Database initialization complete.")
    except Exception as e:
        logger.info(f"[LIFESPAN] CRITICAL ERROR during DB initialization: {e}")
        
    app.state.graph = await build_graph()
    
    yield  # <-- This yields control back to the application to run

    # --- SHUTDOWN LOGIC (runs after the server shuts down) ---
    logger.info("[LIFESPAN] Shutting down.")
    # If you had a DB connection pool that needed closing, it would go here.

app = FastAPI(title="Cerina Clinical Foundry API", version="1.0.0",lifespan=lifespan_handler)

# CORS 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"], # Allow all methods (including OPTIONS, POST, GET)
    allow_headers=["*"], # Allow all headers (including Content-Type)
)
# --- 3. Endpoints ---

import json
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator

@app.post("/start") 
async def start_workflow(request: StartRequest):
    thread_id = str(uuid.uuid4())
    
    initial_state = BlackboardState(
        user_intent=request.user_intent,
        thread_id = thread_id,
        current_draft="",
        augmented_draft="",
        draft_history=[],
        iteration_count=0,
        safety_assessment=None,
        clinical_critique=None,
        agent_thoughts=[],
        next_action="drafter_agent",
        status="STARTING",
        execution_context="UI"
    )
    state_thread_id =initial_state.get("thread_id")
    logger.info(f"[API] Starting workflow for thread_id: {thread_id},State Thread Id: {state_thread_id}")
    config = {"configurable": {"thread_id": thread_id}}
    
    # ----------------------------------------------------------------------
    # Define the Streaming Generator
    # ----------------------------------------------------------------------
    async def event_generator() -> AsyncGenerator[str, None]:
        # 1. Send initial metadata
        yield f"data: {json.dumps({'type': 'meta', 'thread_id': thread_id, 'status': 'STARTING'})}\n\n"
        clinical_foundry_graph =  app.state.graph
        try:
            # Iterate over the LangGraph workflow progress events
            async for event in clinical_foundry_graph.astream_events(initial_state, config=config, version="v2"):
                
                event_type = event["event"]
                node_name = event.get("name")

                
                # --- Stream Data on Node Completion (on_node_end) ---
                if event_type == "on_chain_end":
                    
                    output_data = event["data"]["output"]
                    # --- Stream node status updates ---
                    if "status" in output_data:
                        yield f"data: {json.dumps({'type': 'status_update','data': {'status': output_data['status'],'node': node_name}})}\n\n"
                                    
                    # --- Stream draft updates from drafter_agent ---
                    if node_name == "drafter_agent" and "current_draft" in output_data:
                        yield f"data: {json.dumps({'type': 'draft_update','data': {'current_draft': output_data['current_draft'],'iteration': output_data.get('iteration_count')}})}\n\n"

                    # --- A. Stream the Agent's High-Level Thought ---
                    # Check the 'agent_thoughts' field which is updated in every agent function

                    if 'agent_thoughts' in output_data and output_data['agent_thoughts']:
                        # Assuming the agent_thoughts field returns a list of dictionaries, 
                        # and we want to stream the latest thought (the last one added)
                        latest_thought = output_data['agent_thoughts'][-1]
                        yield f"data: {json.dumps({'type': 'agent_thought', 'data': latest_thought})}\n\n"
                    
                    # --- B. Stream the Safety Assessment ---
                    if node_name == "safety_guardian_agent" and 'safety_assessment' in output_data:
                        # Convert the Pydantic object to a dictionary
                        assessment_dict = output_data['safety_assessment'].model_dump()
                        yield f"data: {json.dumps({'type': 'safety_report', 'data': assessment_dict})}\n\n"
                    
                    # --- C. Stream the Clinical Critique ---
                    elif node_name == "clinical_critic_agent" and 'clinical_critique' in output_data:
                        # Convert the Pydantic object to a dictionary
                        critique_dict = output_data['clinical_critique'].model_dump()
                        yield f"data: {json.dumps({'type': 'critique_report', 'data': critique_dict})}\n\n"


                # --- 4. Final Result / Graph End ---
                if event_type == "on_graph_end":
                    final_state = event["data"]["output"]
                    
                    # Send the final state data (for anything not streamed yet, like final draft)
                    final_payload = {
                        "thread_id": thread_id,
                        "status": final_state.get('status', 'FINISHED'),
                        "current_draft": final_state.get('current_draft', ''),
                        "iteration_count": final_state.get('iteration_count', 0),
                        # Note: agent_thoughts and critiques might be duplicates, but safe to send
                    }
                    yield f"data: {json.dumps({'type': 'final_result', 'data': final_payload})}\n\n"
                    break
        except asyncio.CancelledError:
            logger.info("SSE cancelled")
            raise
        except Exception as e:
            # Send an error event to the frontend before closing the connection
            yield f"data: {json.dumps({'type': 'error', 'message': f'Workflow failed: {str(e)}'})}\n\n"
            logger.info("ERROR IN WORKFLOW:", str(e))
   
            
    # ----------------------------------------------------------------------
    # Return the Streaming Response
    # ----------------------------------------------------------------------
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/status/{thread_id}", response_model=StatusResponse)
async def get_workflow_status(thread_id: str):
    """Required for the UI to 'fetch the current state'"""
    config = {"configurable": {"thread_id": thread_id}}
    clinical_foundry_graph =  app.state.graph
    checkpoint = await asyncio.to_thread(clinical_foundry_graph.checkpointer.get, config)

    if not checkpoint:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    state = checkpoint['channel_values']
    
    return StatusResponse(
        thread_id=thread_id,
        status=state.get('status', 'UNKNOWN'),
        current_draft=state.get('current_draft', ''),
        iteration_count=state.get('iteration_count', 0),
        critique=state.get('clinical_critique'),
        agent_thoughts=state.get('agent_thoughts', [])
    )
@app.post("/approve", response_model=StatusResponse)
async def approve_draft(request: ApproveRequest):

    config = {"configurable": {"thread_id": request.thread_id}}
    clinical_foundry_graph = app.state.graph

    try:
        resume_command = Command(
            resume={
                "approved": True,
                "final_draft": request.final_draft,
                "human_decision": "approve"
            }
        )

        result = await clinical_foundry_graph.ainvoke(
            resume_command,
            config=config
        )

        final_state = result

    except Exception as e:
        logger.exception("ERROR IN APPROVAL")
        raise HTTPException(
            status_code=500,
            detail=f"Approval failed: {str(e)}"
        )

    return StatusResponse(
        thread_id=request.thread_id,
        status=final_state.get("status", "COMPLETED"),
        current_draft=final_state.get("current_draft", request.final_draft),
        iteration_count=final_state.get("iteration_count", 0),
        critique=final_state.get("clinical_critique"),
        agent_thoughts=final_state.get("agent_thoughts", []),
    )


@app.post("/revise", response_model=StatusResponse)
async def revise_draft(request: ReviseRequest):
    """
    Human edits the draft and sends it back for another iteration.
    """
    config = {"configurable": {"thread_id": request.thread_id}}

    clinical_foundry_graph = app.state.graph

    try:
        resume_command = Command(
            resume={
                "approved": False,
                "human_decision": "revise"
            }
        )

        result = await clinical_foundry_graph.ainvoke(
            resume_command,
            config=config
        )

        final_state = result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Revision failed: {str(e)}"
        )

    return StatusResponse(
        thread_id=request.thread_id,
        status=final_state.get("status", "REVISING"),
        current_draft=final_state.get("current_draft", request.edited_draft),
        iteration_count=final_state.get("iteration_count", 0),
        critique=final_state.get("clinical_critique"),
        agent_thoughts=final_state.get("agent_thoughts", []),
    )
