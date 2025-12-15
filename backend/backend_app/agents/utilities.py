from typing import Literal
from langgraph.types import interrupt
from shared.states import BlackboardState, ClinicalReview
from core.sqlite_db import log_final_protocol # For the history requirement
import logging
import json
logger = logging.getLogger(__name__)

import sys
import io

# Force UTF-8 for all stdout/stderr
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
# --- 1. Preprocessor Node (Augment with Line Numbers) ---
def preprocessor_node(state: BlackboardState) -> dict:
    """
    Augments the current_draft with <L#> tags for precise agent referencing.
    """
    draft = state.get('current_draft', "")
    
    if not draft:
        # Should not happen, but safe guard
        return {"augmented_draft": ""}
    logger.info(">>>[PREPROCESSOR] STARTING: Adding line numbers...")

    numbered_lines = []
    lines = draft.split('\n')
    
    # Use XML-style tags for robustness in LLM parsing (Source 1.1)
    for i, line in enumerate(lines):
        # We store the original draft in 'draft_history' before augmenting 'current_draft' 
        # for the Drafter's reference.
        numbered_lines.append(f"<L{i+1}>{line}</L{i+1}>")
        
    augmented_draft = "\n".join(numbered_lines)
    
    # Store the non-augmented draft version in history
    history_update = {"draft_history": [draft]}
    return {
        "augmented_draft": augmented_draft, 
        **history_update
    }

# --- 2. Human-in-the-Loop Node (The Interrupt) ---

def human_in_the_loop(state):
    decision = interrupt({
        "status": "AWAITING_HUMAN_REVIEW",
    })
    logger.info(f"<<< [HUMAN IN LOOP] FINISHED: {decision}")

    thread_id = state.get("thread_id")

    if decision.get("approved"):
        return {
            "thread_id": thread_id,
            "current_draft": decision["final_draft"],
            "status": "COMPLETED",
            "human_decision": "approve",
        }

    return {
        "thread_id": thread_id,
        "status": "Revising/Interrupting",
        "human_decision": "revise"
    }


# --- 3. Finalizer Node (History Logger) ---
def finalizer_node(state, config: dict) -> dict:
    try:
        run_id = config["configurable"]["thread_id"]

        # ✅ Robust state normalization
        if isinstance(state, dict):
            state_dict = state
        else:
            # Pydantic v1 or v2 safe
            state_dict = (
                state.model_dump()
                if hasattr(state, "model_dump")
                else state.dict()
            )

        log_final_protocol(
            run_id=run_id,
            final_state=state_dict,
        )

        return {"status": "COMPLETED"}

    except KeyError:
        logger.error("Failed to retrieve 'thread_id' from config.")
        return {"status": "FINALIZATION_ERROR"}

    except Exception as e:
        logger.exception(f"Finalization error: {e}")
        return {"status": "FINALIZATION_ERROR"}
