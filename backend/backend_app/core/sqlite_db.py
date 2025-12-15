import sqlite3
import json
from datetime import datetime
from uuid import UUID
import logging
logger = logging.getLogger(__name__)

from pathlib import Path

DB_PATH = str(Path(__file__).resolve().parents[1] / "cerina_foundry.db")


def init_db():
    """Initializes the application-level history database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create the history table
    # We store the structured critique history as a JSON blob
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS protocols_history (
        id TEXT PRIMARY KEY,
        run_id TEXT,
        user_intent TEXT,
        final_draft TEXT,
        iteration_count INTEGER,
        final_state_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.commit()
    conn.close()
    logger.info(f" Database initialized at {DB_PATH}")

def log_final_protocol(run_id: str, final_state: dict):
    """
    Logs a finalized protocol to the history table, including the full state
    for comprehensive auditing.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    import uuid
    record_id = str(uuid.uuid4())
    
    # --- Data Extraction and Serialization ---
    # Extract simple fields from the full state
    intent = final_state.get('user_intent', 'N/A')
    draft = final_state.get('current_draft', '')
    iterations = final_state.get('iteration_count', 0)

    # The default=str handles complex objects like Pydantic models, UUIDs, or datetimes.
    try:
        serialized_state = json.dumps(final_state, default=str)
    except TypeError as e:
        # Fallback in case of highly complex objects that can't be stringified
        logger.info(f" Warning: Could not serialize full state. Storing partial JSON. Error: {e}")
        serialized_state = json.dumps({"error": str(e), "partial_state": draft})
        
    
    # --- Insertion ---
    cursor.execute("""
    INSERT INTO protocols_history 
    (id, run_id, user_intent, final_draft, iteration_count, final_state_json)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (record_id, run_id, intent, draft, iterations, serialized_state))
    
    conn.commit()
    conn.close()
    logger.info(f"Protocol archived with full audit data (ID: {record_id})")

if __name__ == "__main__":
    # Run this file directly to set up the DB: `python api/core/db.py`
    init_db()