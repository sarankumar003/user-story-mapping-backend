"""
Assignment suggestions API endpoints
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.run_manager import RunManager
from app.services.ai_agent import AIAgent

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
run_manager = RunManager()
ai_agent = AIAgent()


class User(BaseModel):
    account_id: str
    display_name: str
    email_address: Optional[str] = None
    role: str = ""


class Task(BaseModel):
    id: str
    title: str
    description: Optional[str] = ""
    team: Optional[str] = ""
    priority: Optional[str] = "medium"
    task_type: str  # "epic", "story", "subtask"


class SuggestionRequest(BaseModel):
    users: List[User]
    tasks: List[Task]


class SuggestionResponse(BaseModel):
    suggestions: Dict[str, str]  # task_id -> user_account_id
    reasoning: Dict[str, str]    # task_id -> reasoning for assignment


@router.post("/suggest/{run_id}")
def generate_assignee_suggestions(run_id: str, request: SuggestionRequest):
    """Generate smart assignee suggestions using AI based on task context and user roles"""
    
    try:
        logger.info(f"Starting suggestion generation for run {run_id}")
        logger.info(f"Received {len(request.users)} users and {len(request.tasks)} tasks")
        
        # Use the tasks from the request (frontend already prepared them)
        tasks = request.tasks
        
        # Generate AI-powered suggestions
        logger.info("Calling AI agent for suggestions...")
        suggestions, reasoning = ai_agent.generate_assignee_suggestions(
            users=request.users,
            tasks=tasks
        )
        logger.info(f"AI agent returned {len(suggestions)} suggestions")
        
        # Save suggestions to JSON file for persistence
        suggestions_data = {
            "run_id": run_id,
            "generated_at": datetime.now().isoformat(),
            "suggestions": suggestions,
            "reasoning": reasoning,
            "users": [{"account_id": u.account_id, "display_name": u.display_name, "role": u.role} for u in request.users]
        }
        
        # Save to run-specific file
        run_manager.save_intermediate(run_id, "assignee_suggestions.json", suggestions_data)
        logger.info(f"Suggestions saved to file for run {run_id}")
        
        logger.info(f"Returning {len(suggestions)} suggestions to frontend")
        return SuggestionResponse(
            suggestions=suggestions,
            reasoning=reasoning
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating assignee suggestions for run {run_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/suggestions/{run_id}")
def get_assignee_suggestions(run_id: str):
    """Get saved assignee suggestions for a run"""
    
    try:
        # Load saved suggestions
        suggestions_data = run_manager.load_intermediate(run_id, "assignee_suggestions.json")
        if not suggestions_data:
            raise HTTPException(status_code=404, detail="No suggestions found for this run")
        
        return suggestions_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading assignee suggestions for run {run_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/final/{run_id}")
def save_final_assignments(run_id: str, assignments_data: Dict[str, Any]):
    """Save final assignments for Jira ticket creation"""
    
    try:
        logger.info(f"Saving final assignments for run {run_id}")
        
        # Save to run-specific file
        run_manager.save_intermediate(run_id, "final_assignments.json", assignments_data)
        logger.info(f"Final assignments saved to file for run {run_id}")
        
        return {"message": "Final assignments saved successfully", "run_id": run_id}
        
    except Exception as e:
        logger.error(f"Error saving final assignments for run {run_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/final/{run_id}")
def get_final_assignments(run_id: str):
    """Get final assignments for a run"""
    
    try:
        # Load saved final assignments
        assignments_data = run_manager.load_intermediate(run_id, "final_assignments.json")
        if not assignments_data:
            raise HTTPException(status_code=404, detail="No final assignments found for this run")
        
        return assignments_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading final assignments for run {run_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
