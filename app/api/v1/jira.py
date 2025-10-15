"""
Jira integration API endpoints
"""

import logging
from datetime import datetime
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.services.run_manager import RunManager
from app.services.jira_service import JiraService

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
run_manager = RunManager()
jira_service = JiraService()


@router.post("/sync/{run_id}")
async def sync_to_jira(
    background_tasks: BackgroundTasks,
    run_id: str,
    project_key: str = "NT",
    assignee_mappings: Dict[str, str] = None
):
    """Sync requirements to Jira"""
    
    try:
        # Check if run exists
        run = run_manager.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        
        # Check if decomposition exists
        decomposition = run_manager.load_requirements_decomposition(run_id)
        if not decomposition:
            raise HTTPException(status_code=404, detail="Requirements decomposition not found")
        
        # Start background Jira sync
        background_tasks.add_task(
            sync_to_jira_background, 
            run_id, 
            decomposition, 
            project_key, 
            assignee_mappings or {}
        )
        
        return {"message": "Jira synchronization started", "run_id": run_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting Jira sync for run {run_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/sync/{run_id}")
async def get_jira_sync_result(run_id: str):
    """Get Jira sync result for a run"""
    
    try:
        run = run_manager.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        
        sync_result = run_manager.load_jira_sync_result(run_id)
        if not sync_result:
            raise HTTPException(status_code=404, detail="Jira sync result not found")
        
        return sync_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Jira sync result for run {run_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/projects")
async def get_jira_projects():
    """Get available Jira projects"""
    
    try:
        projects = await jira_service.get_projects()
        return {"projects": projects}
        
    except Exception as e:
        logger.error(f"Error getting Jira projects: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/users")
async def get_jira_users():
    """Get Jira users for assignment"""
    
    try:
        # Use cached users if available
        cached = run_manager.load_or_create_users_cache()
        if cached:
            return {"users": cached}
        users = await jira_service.get_users()
        # Normalize + include role from user data
        norm = [
            {
                "account_id": getattr(u, "account_id", None) or "",
                "display_name": getattr(u, "display_name", None) or "",
                "email_address": getattr(u, "email_address", None),
                "role": getattr(u, "role", None) or ""
            }
            for u in users
        ]
        run_manager.save_users_cache(norm)
        return {"users": norm}
        
    except Exception as e:
        logger.error(f"Error getting Jira users: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/users/refresh")
async def refresh_and_get_jira_users():
    """Refresh Jira users via MCP/script and return the updated list."""
    try:
        users = await jira_service.refresh_users_via_mcp()
        norm = [
            {
                "account_id": getattr(u, "account_id", None) or "",
                "display_name": getattr(u, "display_name", None) or "",
                "email_address": getattr(u, "email_address", None),
                "role": getattr(u, "role", None) or ""
            }
            for u in users
        ]
        run_manager.save_users_cache(norm)
        return {"users": norm}
    except Exception as e:
        logger.error(f"Error refreshing Jira users: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/boards")
async def get_jira_boards(project_key: str = None):
    """Get Jira boards"""
    
    try:
        boards = await jira_service.get_boards(project_key)
        return {"boards": boards}
        
    except Exception as e:
        logger.error(f"Error getting Jira boards: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/bootstrap")
async def bootstrap_jira_cache():
    """On app load: refresh users and projects via MCP and return both."""
    try:
        data = await jira_service.bootstrap_cache()
        return {
            "users": data["users"],
            "projects": data["projects"],
        }
    except Exception as e:
        logger.error(f"Error bootstrapping Jira cache: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def sync_to_jira_background(
    run_id: str, 
    decomposition: Dict[str, Any], 
    project_key: str, 
    assignee_mappings: Dict[str, str]
):
    """Background task to sync requirements to Jira"""
    
    try:
        logger.info(f"Starting Jira sync for run {run_id}")
        
        # Update status
        run_manager.update_run_step(run_id, "jira_sync", "in_progress")
        
        # Sync to Jira
        sync_result = await jira_service.sync_requirements_to_jira(
            decomposition, 
            project_key, 
            assignee_mappings
        )
        
        # Save sync result
        sync_result_dict = sync_result.dict()
        run_manager.save_jira_sync_result(run_id, sync_result_dict)
        run_manager.update_run_step(run_id, "jira_sync", "completed")
        
        # Update run status
        run_manager.update_run_status(run_id, "completed")
        
        logger.info(f"Successfully synced to Jira for run {run_id}")
        
    except Exception as e:
        logger.error(f"Error syncing to Jira for run {run_id}: {str(e)}")
        run_manager.update_run_step(run_id, "jira_sync", "failed", {"error": str(e)})

