from typing import Literal
from shared.states import BlackboardState, SafetyAssessment, ClinicalReview 
import logging 

logger = logging.getLogger(__name__)

# Max number of auto-revisions before forcing human intervention
MAX_ITERATIONS = 4 

# --- Helper function for safe attribute/key access (MUST BE PLACED HERE) ---
def get_attr_or_key(obj, key, default=None):
    """Safely retrieves a key/attribute from a Pydantic object or dictionary."""
    if obj is None:
        return default
    # Try attribute access first (Pydantic object)
    val = getattr(obj, key, None)
    if val is not None:
        return val
    # Try dictionary access next (LangGraph dict serialization)
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default

# ----------------------------------------------------

def supervisor_logic(state: BlackboardState):
    """
    The deterministic brain of the operation.
    Decides the next node based on Safety Score, Critique, and Iteration Limit.
    """
    
    safety = state.get('safety_assessment')
    critique = state.get('clinical_critique')
    iters = state.get('iteration_count', 0)
    human_decision = state.get("human_decision")

    thought = ""

    # --- 1. HIL PATH CHECK (PRIORITY #1: Resuming from pause) ---
    if human_decision:
        logger.info(f"[SUPERVISOR] Human Decision: {human_decision}")
        if human_decision == "approve":
            thought = "Human approved the final draft. Proceeding to finalization."
            logger.info(f"[SUPERVISOR] {thought}")
            return {
                "next_action": "finalizer_node",
                "agent_thoughts": [{"agent_name": "Supervisor", "thought": thought}],
                "human_decision": None # Reset the decision flag
            }
        
        elif human_decision == "revise":
            thought = "Human requested revisions. Cycling back to the drafter."
            logger.info(f"[SUPERVISOR] {thought}")
            return {
                "next_action": "drafter_agent",
                "agent_thoughts": [{"agent_name": "Supervisor", "thought": thought}],
                "human_decision": None # Reset the decision flag
            }
        
    # --- 2. EMERGENCY BRAKE: Infinite Loop Protection ---
    if iters >= MAX_ITERATIONS:
        thought = "Maximum iterations reached. Escalating to human review to prevent an infinite loop."
        logger.warning(f"[SUPERVISOR] {thought}")
        return {
            "next_action": "human_in_the_loop",
            "status":"AWAITING_HUMAN_REVIEW",
            "agent_thoughts": [{"agent_name": "Supervisor", "thought": thought}]
        }
    
    # --- Retrieve agent results safely ---
    safety_score = get_attr_or_key(safety, 'safety_score', default=None)
    critic_score = get_attr_or_key(critique, 'overall_score', default=None)
    
    # --- 3. ROBUSTNESS CHECK (Did the parallel agents succeed?) ---
    if safety_score is None or critic_score is None:
        thought = f"CRITICAL: Safety ({safety_score}) or Critique ({critic_score}) results are missing. Workflow inconsistent."
        logger.error(f"[SUPERVISOR] {thought}")
        return {
            "next_action": "human_in_the_loop", # Escalate critical failures
            "agent_thoughts": [{"agent_name": "Supervisor", "thought": thought}]
        }
    
    # --- 4. SAFETY CHECK ---
    # Assuming safety_score is an integer from 1 to 10.
    if int(safety_score) < 9:
        thought = f"Safety score ({safety_score}) is below the threshold of 9. Requesting revision."
        logger.info(f"[SUPERVISOR] {thought}") 
        return {
            "next_action": "drafter_agent",
            "reason_for_revision": "SAFETY_FAILURE",
            "is_revision" : True,
            "agent_thoughts": [{"agent_name": "Supervisor", "thought": thought}]
        }

    # --- 5. CLINICAL QUALITY CHECK --- 
    # Assuming critic_score is an integer from 1 to 10 or a boolean that converts to 0/1. 
    # If it's a score: < 8 fails. If it's a boolean, ensure the critiquing agent sets 'is_passing' appropriately.
    if int(critic_score) < 8:
        thought = f"Clinical critique score is below threshold({critic_score} < 8). Requesting revision."
        logger.info(f"[SUPERVISOR] {thought}") 
        return {
            "next_action": "drafter_agent",
            "reason_for_revision": "CLINICAL_FAILURE",
            "is_revision" : True,
            "agent_thoughts": [{"agent_name": "Supervisor", "thought": thought}]
        }

    # --- 6. APPROVAL PATH (All checks passed) ---
    thought = "Safety and clinical quality checks passed. The draft is ready for human review."
    logger.info(f"[SUPERVISOR] {thought}") 
    return {
        "next_action": "human_in_the_loop",
        "status": "AWAITING_HUMAN_REVIEW",
        "agent_thoughts": [{"agent_name": "Supervisor", "thought": thought}]
    }