"""
Jira Sync API endpoints
Handles syncing requirements to Jira using direct REST API approach
"""

import logging
import base64
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.services.run_manager import RunManager
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
run_manager = RunManager()


class JiraAuth:
    """Jira authentication helper"""
    
    def __init__(self, base_url: str, username: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.api_token = api_token
    
    def build_headers(self) -> Dict[str, str]:
        """Build authentication headers"""
        credentials = f"{self.username}:{self.api_token}".encode("ascii")
        b64 = base64.b64encode(credentials).decode("ascii")
        return {
            "Authorization": f"Basic {b64}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }


class SyncRequest(BaseModel):
    assignments: Dict[str, Any]


class SyncResponse(BaseModel):
    message: str
    run_id: str
    sync_status: Dict[str, str]


@router.get("/sync/{run_id}")
async def get_jira_sync_result(run_id: str):
    """Get Jira sync result for a run"""
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    sync_result = run_manager.load_jira_sync_result(run_id)
    if not sync_result:
        raise HTTPException(status_code=404, detail="Jira sync result not found")
    
    return sync_result


@router.post("/sync/{run_id}", response_model=SyncResponse)
async def sync_to_jira(
    run_id: str,
    request: SyncRequest
):
    """Sync requirements to Jira using direct REST API - waits for completion"""
    
    try:
        # Check if run exists
        run = run_manager.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        
        # Check if final assignments exist
        assignments = request.assignments
        if not assignments or not assignments.get("epics"):
            raise HTTPException(status_code=400, detail="No assignments found")
        
        # Run Jira sync synchronously
        sync_result = await sync_to_jira_sync(run_id, assignments)
        
        return SyncResponse(
            message="Jira synchronization completed",
            run_id=run_id,
            sync_status=sync_result.get("sync_status", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing to Jira for run {run_id}: {str(e)}")
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


async def sync_to_jira_background(run_id: str, assignments: Dict[str, Any]):
    """Background task to sync requirements to Jira using direct REST API"""
    
    try:
        logger.info(f"Starting Jira sync for run {run_id}")
        
        # Initialize Jira authentication
        auth = JiraAuth(
            base_url=settings.JIRA_BASE_URL,
            username=settings.JIRA_USERNAME,
            api_token=settings.JIRA_API_TOKEN
        )
        
        # Update status
        run_manager.update_run_step(run_id, "jira_sync", "in_progress")
        
        # Track sync results
        sync_status = {}
        epic_keys = {}
        story_keys = {}
        subtask_keys = {}
        errors = []
        tickets_created = 0
        tickets_failed = 0
        
        # Create epics first
        for epic in assignments.get("epics", []):
            try:
                sync_status[epic["id"]] = "pending"
                
                epic_key = await create_epic(auth, {
                    "project": settings.JIRA_PROJECT_KEY,
                    "summary": epic["title"],
                    "description": epic["description"],
                    "epic_name": epic["title"],
                    "assignee": epic.get("assignee")
                })
                
                epic_keys[epic["id"]] = epic_key
                sync_status[epic["id"]] = "success"
                tickets_created += 1
                logger.info(f"Created epic: {epic_key}")
                
            except Exception as e:
                error_msg = f"Failed to create epic '{epic['title']}': {str(e)}"
                errors.append(error_msg)
                sync_status[epic["id"]] = "error"
                tickets_failed += 1
                logger.error(error_msg)
        
        # Create stories
        for epic in assignments.get("epics", []):
            epic_key = epic_keys.get(epic["id"])
            if not epic_key:
                continue
            
            for story in epic.get("stories", []):
                try:
                    sync_status[story["id"]] = "pending"
                    
                    story_key = await create_issue(auth, {
                        "project": settings.JIRA_PROJECT_KEY,
                        "issuetype": "Story",
                        "summary": story["title"],
                        "description": story["description"],
                        "assignee": story.get("assignee"),
                        "priority": story.get("priority", "Medium"),
                        "labels": story.get("labels", []),
                        "parent": epic_key
                    })
                    
                    story_keys[story["id"]] = story_key
                    sync_status[story["id"]] = "success"
                    tickets_created += 1
                    logger.info(f"Created story: {story_key}")
                    
                except Exception as e:
                    error_msg = f"Failed to create story '{story['title']}': {str(e)}"
                    errors.append(error_msg)
                    sync_status[story["id"]] = "error"
                    tickets_failed += 1
                    logger.error(error_msg)
        
        # Create subtasks
        for epic in assignments.get("epics", []):
            for story in epic.get("stories", []):
                story_key = story_keys.get(story["id"])
                if not story_key:
                    continue
                
                for subtask in story.get("subtasks", []):
                    try:
                        sync_status[subtask["id"]] = "pending"
                        
                        subtask_key = await create_issue(auth, {
                            "project": settings.JIRA_PROJECT_KEY,
                            "issuetype": "Subtask",
                            "summary": subtask["title"],
                            "description": subtask["description"],
                            "assignee": subtask.get("assignee"),
                            "priority": subtask.get("priority", "Medium"),
                            "labels": subtask.get("labels", []),
                            "parent": story_key
                        })
                        
                        subtask_keys[subtask["id"]] = subtask_key
                        sync_status[subtask["id"]] = "success"
                        tickets_created += 1
                        logger.info(f"Created subtask: {subtask_key}")
                        
                    except Exception as e:
                        error_msg = f"Failed to create subtask '{subtask['title']}': {str(e)}"
                        errors.append(error_msg)
                        sync_status[subtask["id"]] = "error"
                        tickets_failed += 1
                        logger.error(error_msg)
        
        # Save sync result
        sync_result = {
            "run_id": run_id,
            "sync_date": datetime.now().isoformat(),
            "tickets_created": tickets_created,
            "tickets_failed": tickets_failed,
            "sync_status": sync_status,
            "epic_keys": epic_keys,
            "story_keys": story_keys,
            "subtask_keys": subtask_keys,
            "errors": errors
        }
        
        run_manager.save_jira_sync_result(run_id, sync_result)
        run_manager.update_run_step(run_id, "jira_sync", "completed")
        
        # Update run status
        from app.models.document import DocumentStatus
        run_manager.update_run_status(run_id, DocumentStatus.COMPLETED)
        
        logger.info(f"Successfully synced to Jira for run {run_id}: {tickets_created} tickets created, {tickets_failed} failed")
        
    except Exception as e:
        logger.error(f"Error syncing to Jira for run {run_id}: {str(e)}")
        run_manager.update_run_step(run_id, "jira_sync", "failed", {"error": str(e)})
        # Update run status to failed
        from app.models.document import DocumentStatus
        run_manager.update_run_status(run_id, DocumentStatus.FAILED)


async def sync_to_jira_sync(run_id: str, assignments: Dict[str, Any]):
    """Synchronous Jira sync - waits for completion and returns result"""
    
    try:
        logger.info(f"Starting synchronous Jira sync for run {run_id}")
        
        # Initialize Jira authentication
        auth = JiraAuth(
            base_url=settings.JIRA_BASE_URL,
            username=settings.JIRA_USERNAME,
            api_token=settings.JIRA_API_TOKEN
        )
        
        # Update status
        run_manager.update_run_step(run_id, "jira_sync", "in_progress")
        
        # Track sync results
        sync_status = {}
        epic_keys = {}
        story_keys = {}
        subtask_keys = {}
        errors = []
        tickets_created = 0
        tickets_failed = 0
        
        # Create epics first
        for epic in assignments.get("epics", []):
            try:
                sync_status[epic["id"]] = "pending"
                
                epic_key = await create_epic(auth, {
                    "project": settings.JIRA_PROJECT_KEY,
                    "summary": epic["title"],
                    "description": epic["description"],
                    "epic_name": epic["title"],
                    "assignee": epic.get("assignee")
                })
                
                epic_keys[epic["id"]] = epic_key
                sync_status[epic["id"]] = "success"
                tickets_created += 1
                logger.info(f"Created epic: {epic_key}")
                
            except Exception as e:
                error_msg = f"Failed to create epic '{epic['title']}': {str(e)}"
                errors.append(error_msg)
                sync_status[epic["id"]] = "error"
                tickets_failed += 1
                logger.error(error_msg)
        
        # Create stories
        for epic in assignments.get("epics", []):
            epic_key = epic_keys.get(epic["id"])
            if not epic_key:
                continue
            
            for story in epic.get("stories", []):
                try:
                    sync_status[story["id"]] = "pending"
                    
                    story_key = await create_issue(auth, {
                        "project": settings.JIRA_PROJECT_KEY,
                        "issuetype": "Story",
                        "summary": story["title"],
                        "description": story["description"],
                        "assignee": story.get("assignee"),
                        "priority": story.get("priority", "Medium"),
                        "labels": story.get("labels", []),
                        "parent": epic_key
                    })
                    
                    story_keys[story["id"]] = story_key
                    sync_status[story["id"]] = "success"
                    tickets_created += 1
                    logger.info(f"Created story: {story_key}")
                    
                except Exception as e:
                    error_msg = f"Failed to create story '{story['title']}': {str(e)}"
                    errors.append(error_msg)
                    sync_status[story["id"]] = "error"
                    tickets_failed += 1
                    logger.error(error_msg)
        
        # Create subtasks
        for epic in assignments.get("epics", []):
            for story in epic.get("stories", []):
                story_key = story_keys.get(story["id"])
                if not story_key:
                    continue
                
                for subtask in story.get("subtasks", []):
                    try:
                        sync_status[subtask["id"]] = "pending"
                        
                        subtask_key = await create_issue(auth, {
                            "project": settings.JIRA_PROJECT_KEY,
                            "issuetype": "Subtask",
                            "summary": subtask["title"],
                            "description": subtask["description"],
                            "assignee": subtask.get("assignee"),
                            "priority": subtask.get("priority", "Medium"),
                            "labels": subtask.get("labels", []),
                            "parent": story_key
                        })
                        
                        subtask_keys[subtask["id"]] = subtask_key
                        sync_status[subtask["id"]] = "success"
                        tickets_created += 1
                        logger.info(f"Created subtask: {subtask_key}")
                        
                    except Exception as e:
                        error_msg = f"Failed to create subtask '{subtask['title']}': {str(e)}"
                        errors.append(error_msg)
                        sync_status[subtask["id"]] = "error"
                        tickets_failed += 1
                        logger.error(error_msg)
        
        # Save sync result
        sync_result = {
            "run_id": run_id,
            "sync_date": datetime.now().isoformat(),
            "tickets_created": tickets_created,
            "tickets_failed": tickets_failed,
            "sync_status": sync_status,
            "epic_keys": epic_keys,
            "story_keys": story_keys,
            "subtask_keys": subtask_keys,
            "errors": errors
        }
        
        run_manager.save_jira_sync_result(run_id, sync_result)
        run_manager.update_run_step(run_id, "jira_sync", "completed")
        
        # Update run status
        from app.models.document import DocumentStatus
        run_manager.update_run_status(run_id, DocumentStatus.COMPLETED)
        
        logger.info(f"Successfully synced to Jira for run {run_id}: {tickets_created} tickets created, {tickets_failed} failed")
        
        return sync_result
        
    except Exception as e:
        logger.error(f"Error syncing to Jira for run {run_id}: {str(e)}")
        run_manager.update_run_step(run_id, "jira_sync", "failed", {"error": str(e)})
        # Update run status to failed
        from app.models.document import DocumentStatus
        run_manager.update_run_status(run_id, DocumentStatus.FAILED)
        raise


async def get_issue_metadata(auth: JiraAuth, project: str, issue_type: str) -> Dict[str, Any]:
    """Get issue creation metadata to validate available fields."""
    import httpx
    
    url = f"{auth.base_url}/rest/api/3/issue/createmeta?projectKeys={project}&issuetypeNames={issue_type}&expand=projects.issuetypes.fields"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=auth.build_headers(), timeout=30.0)
        
        if response.status_code == 200 and response.content:
            data = response.json()
            if data.get("projects"):
                project_data = data["projects"][0]
                if project_data.get("issuetypes"):
                    return project_data["issuetypes"][0].get("fields", {})
    return {}


async def create_epic(auth: JiraAuth, epic_data: Dict[str, Any]) -> str:
    """Create an epic in Jira using REST API"""
    import httpx
    
    fields = {
        "project": {"key": epic_data["project"]},
        "issuetype": {"name": "Epic"},
        "summary": epic_data["summary"],
    }
    
    # Add description in Atlassian Document Format (ADF)
    if epic_data.get("description"):
        fields["description"] = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": epic_data["description"]
                        }
                    ]
                }
            ]
        }
    
    # Get available fields for epic to check if epic name field exists
    available_fields = await get_issue_metadata(auth, epic_data["project"], "Epic")
    
    # Epic name field (usually customfield_10011) - only set if available
    epic_name = epic_data.get("epic_name", epic_data["summary"])
    if "customfield_10011" in available_fields:
        fields["customfield_10011"] = epic_name
    
    # Add assignee if specified and available
    if epic_data.get("assignee") and "assignee" in available_fields:
        fields["assignee"] = {"name": epic_data["assignee"], "accountId": epic_data["assignee"]}
    
    url = f"{auth.base_url}/rest/api/3/issue"
    payload = {"fields": fields}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers=auth.build_headers(),
            json=payload,
            timeout=30.0
        )
        
        if response.status_code not in (200, 201):
            error_data = response.json() if response.content else {}
            raise RuntimeError(f"Create epic failed ({response.status_code}): {json.dumps(error_data, ensure_ascii=False)}")
        
        data = response.json()
        key = data.get("key")
        if not key:
            raise RuntimeError(f"Create epic returned no key: {data}")
        
        return key


async def create_issue(auth: JiraAuth, issue: Dict[str, Any]) -> str:
    """Create an issue (Story or Subtask) in Jira using REST API"""
    import httpx
    
    issue_type = issue["issuetype"]
    
    fields = {
        "project": {"key": issue["project"]},
        "issuetype": {"name": issue_type},
        "summary": issue["summary"],
    }
    
    # Get available fields for validation
    available_fields = await get_issue_metadata(auth, issue["project"], issue_type)
    
    # Add description in ADF format
    if issue.get("description"):
        fields["description"] = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": issue["description"]
                        }
                    ]
                }
            ]
        }
    
    # Add labels if available
    labels = issue.get("labels")
    if isinstance(labels, list) and labels and "labels" in available_fields:
        fields["labels"] = labels
    
    # Add assignee if specified and available
    assignee = issue.get("assignee")
    if assignee and assignee.strip() and "assignee" in available_fields:
        fields["assignee"] = {"name": assignee, "accountId": assignee}
    
    # Add priority if specified and available
    priority = issue.get("priority")
    if priority and priority.strip() and "priority" in available_fields:
        fields["priority"] = {"name": priority}
    
    # Add parent for subtasks
    parent_key = issue.get("parent")
    if parent_key and "parent" in available_fields:
        fields["parent"] = {"key": parent_key}
    
    url = f"{auth.base_url}/rest/api/3/issue"
    payload = {"fields": fields}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers=auth.build_headers(),
            json=payload,
            timeout=30.0
        )
        
        if response.status_code not in (200, 201):
            error_data = response.json() if response.content else {}
            raise RuntimeError(f"Create {issue_type.lower()} failed ({response.status_code}): {json.dumps(error_data, ensure_ascii=False)}")
        
        data = response.json()
        key = data.get("key")
        if not key:
            raise RuntimeError(f"Create {issue_type.lower()} returned no key: {data}")
        
        return key