import operator
from typing import Annotated, List, Optional, TypedDict, Union, Dict, Any
from pydantic import BaseModel, Field

# --- 1. Inner Data Models (Structured "Thoughts") ---
# These are the rigorous schemas we want our agents to populate.
"""
class FeedbackItem(BaseModel):
    line: Optional[int] = Field(
        None, description="The specific line number <L#> to fix. None if general feedback."
    )
    aspect: str = Field(
        ..., description="Type of issue: 'SAFETY', 'CLINICAL_TONE', 'STRUCTURE', 'CLARITY'."
    )
    feedback: str = Field(
        ..., description="Specific instructions for the Drafter on how to fix this."
    )
"""
class ClinicalReview(BaseModel):
    """The full output from the Clinical Critic agent."""
    feedback: Optional[List[str]] = None
    overall_score: int = Field(..., description="0-10 score of quality.")

class SafetyAssessment(BaseModel):
    """The output from the Safety Guardian."""
    feedback: Optional[List[str]] = None
    safety_score: float = Field(..., description="0 - 10 score for Safety")

# --- 2. The Main Blackboard State ---
# This is the object passed between nodes in the graph.

class BlackboardState(TypedDict):
    # --- Inputs ---
    user_intent: str             # The original prompt from the user
    
    # --- The Artifact ---
    current_draft: str           # The actual text of the protocol
    augmented_draft: str         # The draft with <L1> line numbers added (for internal agent reference)
    final_draft: str             # The final text approved by the human
    
    # --- History & Versioning ---
    # operator.add tells LangGraph to APPEND new items to this list, not overwrite
    draft_history: Annotated[List[str], operator.add] 
    iteration_count: int         # Safety valve to prevent infinite loops
    
    # --- The "Blackboard" (Agent Scratchpads) ---
    # Agents write their structured thoughts here
    safety_assessment: Optional[SafetyAssessment]
    clinical_critique: Optional[ClinicalReview]
    agent_thoughts: Annotated[List[Dict], operator.add]
    
    # --- Workflow Control ---
    # The Supervisor sets these to guide the graph
    next_action: str             # e.g., "revise", "halt", "finalize"
    status: str                  # e.g., "Drafting", "Reviewing", "Awaiting Human Approval"
    execution_context: str       # e.g., "", "M2M_API"
    human_decision: Optional[str]
    reason_for_revision: Optional[str]
    is_revision: bool
