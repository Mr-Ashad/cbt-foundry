import os
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from shared.states import BlackboardState, SafetyAssessment, ClinicalReview
from dotenv import load_dotenv 
from langchain_core.messages import AIMessage
import json
import logging
logger = logging.getLogger(__name__)
# Load environment variables from .env file
load_dotenv()

def extract_json_block(text: str) -> dict:
    import re
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON object found in LLM output")
    return json.loads(match.group(0))

drafter_llm = ChatGroq(
    model="openai/gpt-oss-safeguard-20b",
    temperature=0.3,
    api_key=os.getenv("GROQ_API_KEY_DRAFTER")
)

critic_llm = ChatGroq(
    model="openai/gpt-oss-safeguard-20b",
    temperature=0.0,
    api_key=os.getenv("GROQ_API_KEY_CRITIC")
)

safety_llm = ChatGroq(
    model="openai/gpt-oss-safeguard-20b",
    temperature=0.1,
    api_key=os.getenv("GROQ_API_KEY_SAFETY")
)

# --- 1. The Drafter Agent ---
from typing import Literal
# Ensure SafetyAssessment and ClinicalReview are correctly imported
# from shared.states import BlackboardState, SafetyAssessment, ClinicalReview 

def drafter_agent(state: BlackboardState):

    """Generates or Revises the CBT protocol based on the reason for revision."""
    
    intent = state['user_intent']
    draft = state.get('current_draft', "")
    augmented_draft = state.get('augmented_draft', "")
    
    # ⭐️ REQUIRED FLAG: Access the reason for revision set by the Supervisor
    revision_reason: Literal['SAFETY_FAILURE', 'CLINICAL_FAILURE', None] = state.get('reason_for_revision')
    
    # 1. INITIAL DRAFT MODE

    if not revision_reason :
        logger.info("RUNNING INITIAL DRAFT")
        thought = f"Starting a new draft based on user intent: '{intent}'."
        system_msg = """
              You are a CBT (Cognitive Behavioral Therapy) protocol drafter.

                Create a clear, supportive, and evidence-informed stress-management protocol
                based on the user’s intent.

                Guidelines:
                - Use an empathetic, collaborative, non-judgmental tone.

                - Do not diagnose or provide definitive medical advice.
                - Emphasize self-reflection, coping skills, and personal choice.
                - Acknowledge individual differences and encourage professional support when appropriate.

                Structure with clear sections (e.g., Introduction, Understanding Stress, Coping Strategies, Action Plan, Conclusion).

                Output the full protocol in clean Markdown only, with no extra commentary.
            """
        human_msg = f"User Intent: {intent}"
        

    # 2. REVISION MODE (Targeted Fixes)
    else:
        # Access the full assessment objects
        safety_assessment = state.get('safety_assessment')
        clinical_review = state.get('clinical_critique')
        
        feedback_str = ""
        
        # --- A. SAFETY REVISION ---
        if revision_reason == "SAFETY_FAILURE" and safety_assessment:
            logger.info("RUNNING REVISION FOR SAFETY FAILURE")
            thought = "Revising the draft to fix CRITICAL SAFETY ISSUES (Self-Harm, Medical Advice, Scope Breach)."
            system_msg = "You are refining a CBT protocol. **Your primary goal is safety.** Fix ONLY the specific safety issues flagged below. Do not change structure or tone unless necessary for safety. Output the revised protocol in clean Markdown format Do not add any leading or ending words ."
            
            # Assuming SafetyAssessment.feedback is a list of objects with line_number, safety_flag, description
            if safety_assessment.feedback:
                feedback_items = safety_assessment.feedback
                feedback_lines = []

                for item in feedback_items:
                    # Case 1: Proper structured object
                    if hasattr(item, "line_number"):
                        feedback_lines.append(
                            f"- Line {item.line_number} [{item.safety_flag}]: {item.description}"
                        )
                    # Case 2: Plain string fallback
                    else:
                        feedback_lines.append(f"- {str(item)}")

                feedback_str = "\n".join(feedback_lines)

                logger.info(f"Feedback Str: {feedback_str}")
                
        # --- B. CLINICAL REVISION ---
        elif revision_reason == "CLINICAL_FAILURE" and clinical_review:
            logger.info("RUNNING REVISION FOR clinical FAILURE")
            thought = "Revising the draft to fix Clinical Quality Issues (Tone, Structure)."
            system_msg = "You are refining a CBT protocol. **Your primary goal is fix Clinical Quality Issues (Empathy,Tone, Structure).** Fix ONLY the specific clinical issues flagged below. Maintain a safe protocol. Output the revised protocol in clean Markdown format do not add any leading or ending words."
            
            # Assuming ClinicalReview.feedback is a list of objects with line_number, aspect, description
            if clinical_review.feedback:

               feedback_items = clinical_review.feedback
               feedback_lines = []

               for item in feedback_items:
                    # Case 1: Proper structured object
                    if hasattr(item, "line_number"):
                        feedback_lines.append(
                            f"- Line {item.line_number} [{item.safety_flag}]: {item.description}"
                        )
                    # Case 2: Plain string fallback
                    else:
                        feedback_lines.append(f"- {str(item)}")

               feedback_str = "\n".join(feedback_lines)
        
        human_msg = f"Current Draft:\n{augmented_draft}\n\n==========================\n\nREQUIRED FIXES:\n{feedback_str}"
        
        # Fallback if revision reason is set but feedback is empty/missing
        if not feedback_str:
             thought = "Revision reason was set, but no actionable feedback was found. Generating a standard revision prompt."
             # Use a generic revision message to continue the process
             system_msg = "You are refining a CBT protocol. Improve the current draft based on the last review. Output the revised protocol in clean Markdown format."
             human_msg = f"Current Draft:\n{draft}\n\nPlease review and improve this draft."

    # Generate the new or revised draft

    response = drafter_llm.bind(tools=[]).invoke([
        ("system", system_msg), 
        ("human", human_msg)
    ])
    
    # We update the state with the new draft and increment iteration
    return {
        "current_draft": response.content, 
        "augmented_draft": None,
        "reason_for_revision": None, 
        "iteration_count": state.get('iteration_count', 0) + 1,
        "agent_thoughts": [{"agent_name": "Drafter", "thought": thought}]
    }

# --- 2. The Safety Guardian ---
def safety_guardian_agent(state: BlackboardState):
    logger.info(">>> [SAFETY] STARTING: Assessing draft for risk...")
    
    # 1. Define safety_agent Parser
    safety_parser = PydanticOutputParser(pydantic_object=SafetyAssessment)
    safety_format_instructions = safety_parser.get_format_instructions()
        
    system_msg = f"""
        You are an Expert Clinical Safety Officer specializing in reviewing drafts intended for CBT (Cognitive Behavioral Therapy) exercise.
        Your task is to thoroughly assess the provided draft text for safety risks,
        Specifically, look for:
        1.  Medical/Clinical Advice: Statements that diagnose, prescribe, or offer definitive medical/clinical recommendations, masquerading as therapy or general advice.
        2.  Self-Harm/Suicidal Ideation
        Provide a safety_score out of 10 (8 is considered passing score)

        ---
        **CRITICAL INSTRUCTION:**
        ONLY If the 'safety_score' is less than 8, you **MUST** populate the `feedback` list.
        Each note must include:
        * The **line number** (start counting from 1) where the issue is found.
        * The **safety_flag** (e.g., 'MEDICAL_ADVICE', 'CRISIS_KEYWORD').
        * A **description** of the problem and the necessary fix.
        **You MUST output only a raw JSON object it must be directly parseable by json.loads()** that strictly conforms to the provided schema."
        """
    
    human_msg = f"Draft to Check:\n{state['augmented_draft']}\n\n{safety_format_instructions}"
    
    thought = "Assessing the current draft for safety risks, including self-harm, medical advice, and crisis keywords."
    
    # 2. Get raw LLM response
    raw_assessment_msg = safety_llm.bind(tools=[]).invoke([
        ("system", system_msg), 
        ("human", human_msg)
    ])

    # 3. Extract JSON content string
    raw_json_string = raw_assessment_msg.content
    
    try:
        data = extract_json_block(raw_json_string)
        #data = json.loads(json_string)
        
        # Create the validated Pydantic object
        validated_assessment = SafetyAssessment(**data)
        
        logger.info(f"<<< [SAFETY] FINISHED: {validated_assessment}")
        
        # 5. Return the validated Pydantic object
        return {
     
            "safety_assessment": validated_assessment,
            "agent_thoughts": [{"agent_name": "Safety Guardian", "thought": thought}]
        }
        
    except json.JSONDecodeError as e:
        logger.info(f"--- [SAFETY-AGENT] JSON PARSE ERROR: {e}")
        logger.info(f"Raw LLM response content: {raw_json_string}")
        
        # Fallback for safety failure
        return {
            "safety_assessment": SafetyAssessment(safety_score=0.0, flags=["JSON_PARSE_FAILURE"]),
            "agent_thoughts": [{"agent_name": "Safety Guardian", "thought": f"CRITICAL FAILURE: Failed to parse LLM output. {e}"}]
        }
    
# --- 3. The Clinical Critic ---
def clinical_critic_agent(state: BlackboardState):
    logger.info(">>> [CRITIC] STARTING: Reviewing draft quality (Safe Parsing)...")
    
    # 1. Setup Parser
    # The parser needs to know what structure to enforce
    parser = PydanticOutputParser(pydantic_object=ClinicalReview)
    critic_format_instructions = parser.get_format_instructions()
    thought = "Critiquing the current draft for tone, structure, and clinical soundness."

    # 2. Define the system message with explicit JSON instruction
    system_msg = f"""
        You are an Expert CBT Critic. Your task is to review a CBT exercise draft.
        
        Check the draft *thoroughly* based on the following three aspects:
        1. TONE: Is the tone empathetic, professional, and supportive?
        2. STRUCTURE: Is the exercise well-organized, logical, and easy to follow?
        3. CLINICAL SOUNDNESS: Is the underlying advice clinically accurate, appropriate for CBT, and does it align with established protocols?

        ---
        Score the draft out of 10. (Note: A passing standard is generally considered 8 or higher.)
        
        **CRITICAL INSTRUCTION:**
        ONLY If the 'overall_score' is less than 8, you **MUST** populate the `feedback` list.
        Each note must include:
        * The **line number** (start counting from 1) where the issue is found.
        * The **aspect** (e.g., 'TONE', 'STRUCTURE', 'CLINICAL_SOUNDNESS').
        * A **description** of the problem and the necessary fix.

        **You MUST output only a raw JSON object it must be directly parseable by json.loads() ** that strictly conforms to the provided schema.**
    """ 
    
    human_msg = f"Draft to Review:\n{state['augmented_draft']}\n\n{critic_format_instructions}"
    
    # Create the prompt with just the messages we need
    raw_assessment_msg = critic_llm.bind(tools=[]).invoke([
            ("system", system_msg), 
            ("human", human_msg)
        ])
    
    # 3. Extract JSON content string
    raw_json_string = raw_assessment_msg.content

    try:
        data = extract_json_block(raw_json_string)
        #data = json.loads(json_string)
        
        # Create the validated Pydantic object
        review = ClinicalReview(**data)
        
        logger.info(f"<<< [CRITIC] FINISHED: {review}")
        
        # 4. Update the thought
        thought = f"Reviewing the current draft for tone, structure, and clinical soundness. {thought}"
        # 5. Return the result
        return {
            "clinical_critique": review,
            "agent_thoughts": [{"agent_name": "Clinical Critic", "thought": thought}]
        }
            
    except Exception as e:
        logger.info(f"--- [CRITIC] ERROR: Failed to generate or parse response. {type(e).__name__}: {str(e)}")
        
        # Fallback mechanism: Return a safe, failed review
        return {
            "clinical_critique": ClinicalReview(
                feedback=[], 
                overall_score=0, 
                is_passing=False # Use hardcoded False here for safety fallback
            ),
            "agent_thoughts": [{"agent_name": "Clinical Critic", "thought": "CRITICAL FAILURE: LLM response failed structured parsing."}]
        }