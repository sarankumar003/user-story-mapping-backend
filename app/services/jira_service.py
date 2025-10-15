"""
Jira Service
Handles Jira integration using the existing MCP Atlassian connection
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.models.jira_mapping import JiraTicket, JiraProject, JiraUser, JiraSyncResult, JiraBoard
import subprocess
from pathlib import Path
import os

logger = logging.getLogger(__name__)


class JiraService:
    """Service for Jira integration"""
    
    def __init__(self):
        self.base_url = settings.JIRA_BASE_URL
        self.username = settings.JIRA_USERNAME
        self.api_token = settings.JIRA_API_TOKEN
        self.project_key = settings.JIRA_PROJECT_KEY
    
    async def get_projects(self) -> List[JiraProject]:
        """Get available Jira projects"""
        # This would integrate with the MCP Atlassian server
        # For now, return a mock project
        return [
            JiraProject(
                key=self.project_key,
                name="New Project",
                project_type="software",
                lead=self.username
            )
        ]

    async def refresh_projects_via_mcp(self) -> List[JiraProject]:
        """Trigger MCP script to refresh projects cache (projects.json) and return it.

        Looks for scripts/get_jira_projects.py; if not found, falls back to get_projects().
        """
        try:
            backend_root = Path(__file__).resolve().parents[2]
            script = backend_root / "scripts" / "get_jira_projects.py"
            projects_path = backend_root / "projects.json"
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            if script.exists():
                subprocess.run(["python", "-X", "utf8", str(script)], cwd=str(backend_root), capture_output=True, text=True, encoding="utf-8", timeout=120, env=env)
            if projects_path.exists():
                import json
                with open(projects_path, "r", encoding="utf-8") as f:
                    arr = json.load(f)
                projects: List[JiraProject] = []
                for p in arr or []:
                    projects.append(JiraProject(
                        key=p.get("key", ""),
                        name=p.get("name", ""),
                        project_type=p.get("project_type", "software"),
                        lead=p.get("lead")
                    ))
                return projects
            return await self.get_projects()
        except Exception as e:
            logger.error(f"Error refreshing projects via MCP: {e}")
            return await self.get_projects()

    async def bootstrap_cache(self) -> Dict[str, Any]:
        """Refresh users and projects cache via MCP and return both."""
        users = await self.refresh_users_via_mcp()
        projects = await self.refresh_projects_via_mcp()
        return {"users": users, "projects": projects}
    
    async def get_users(self) -> List[JiraUser]:
        """Get Jira users for assignment.

        Implementation notes:
        - Reads from users.json file which contains user data with roles
        - Falls back to teams.json if users.json is not available
        """
        try:
            import json
            from pathlib import Path

            # Look for users.json in backend directory first
            backend_root = Path(__file__).resolve().parents[2]
            users_path = backend_root / "users.json"
            
            if users_path.exists():
                # Read from users.json (preferred)
                with open(users_path, "r", encoding="utf-8") as f:
                    users_data = json.load(f)

                users: List[JiraUser] = []
                for u in users_data:
                    users.append(
                        JiraUser(
                            account_id=u.get("account_id", ""),
                            display_name=u.get("display_name", ""),
                            email_address=u.get("email_address"),
                            role=u.get("role")
                        )
                    )
                return users
            else:
                # Fallback to teams.json
                teams_path = backend_root / "teams.json"
                if not teams_path.exists():
                    logger.warning(f"Neither users.json nor teams.json found, returning empty user list")
                    return []

                with open(teams_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                users: List[JiraUser] = []
                for u in data.get("all_users", []):
                    users.append(
                        JiraUser(
                            account_id=u.get("account_id", ""),
                            display_name=u.get("display_name", ""),
                            email_address=u.get("email_address"),
                            role=None  # teams.json doesn't have roles
                        )
                    )
                return users
        except Exception as e:
            logger.error(f"Error reading users data: {e}")
            # Return empty list instead of raising exception
            return []

    async def refresh_users_via_mcp(self) -> List[JiraUser]:
        """Trigger MCP script to refresh users and return them."""
        try:
            # Use the backend script
            script_path = Path(__file__).parent.parent / "scripts" / "jira_operations.py"
            if not script_path.exists():
                logger.warning(f"jira_operations.py not found at {script_path}")
                return await self.get_users()

            # Execute script non-interactively
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            
            result = subprocess.run(
                ["python", str(script_path)],
                cwd=str(script_path.parent),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
                env=env,
            )
            
            if result.returncode != 0:
                safe_err = (result.stderr or "").encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
                logger.error(f"jira_operations.py failed: {safe_err}")
                # Return empty list instead of calling get_users() to avoid recursion
                return []

            # Parse the JSON output
            try:
                users_data = json.loads(result.stdout)
                users = []
                for user_data in users_data:
                    users.append(JiraUser(
                        account_id=user_data.get("account_id", ""),
                        display_name=user_data.get("display_name", ""),
                        email_address=user_data.get("email_address")
                    ))
                logger.info(f"Refreshed {len(users)} users via MCP script")
                return users
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse users JSON: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Error refreshing users via MCP: {e}")
            return []
    
    async def get_boards(self, project_key: str = None) -> List[JiraBoard]:
        """Get Jira boards"""
        # This would integrate with the MCP Atlassian server
        return [
            JiraBoard(
                id=1,
                name="Project Board",
                type="scrum",
                project_key=project_key or self.project_key
            )
        ]
    
    async def create_epic(self, epic_data: Dict[str, Any]) -> str:
        """Create an epic in Jira"""
        # This would use the MCP Atlassian server to create epics
        # For now, return a mock key
        return f"{self.project_key}-{len(epic_data.get('title', ''))}"
    
    async def create_story(self, story_data: Dict[str, Any], epic_key: str = None) -> str:
        """Create a story in Jira"""
        # This would use the MCP Atlassian server to create stories
        # For now, return a mock key
        return f"{self.project_key}-{len(story_data.get('title', ''))}"
    
    async def create_subtask(self, subtask_data: Dict[str, Any], parent_key: str) -> str:
        """Create a subtask in Jira"""
        # This would use the MCP Atlassian server to create subtasks
        # For now, return a mock key
        return f"{self.project_key}-{len(subtask_data.get('title', ''))}"
    
    async def sync_requirements_to_jira(
        self, 
        decomposition: Dict[str, Any], 
        project_key: str, 
        assignee_mappings: Dict[str, str]
    ) -> JiraSyncResult:
        """Sync requirements decomposition to Jira"""
        
        try:
            epic_keys = {}
            story_keys = {}
            subtask_keys = {}
            errors = []
            tickets_created = 0
            tickets_failed = 0
            
            # Create epics first
            for epic in decomposition.get("epics", []):
                try:
                    epic_data = {
                        "title": epic["title"],
                        "description": epic["description"],
                        "priority": epic.get("priority", "Medium"),
                        "assignee": assignee_mappings.get(epic["id"])
                    }
                    
                    epic_key = await self.create_epic(epic_data)
                    epic_keys[epic["id"]] = epic_key
                    tickets_created += 1
                    
                except Exception as e:
                    error_msg = f"Failed to create epic '{epic['title']}': {str(e)}"
                    errors.append(error_msg)
                    tickets_failed += 1
                    logger.error(error_msg)
            
            # Create stories
            for epic in decomposition.get("epics", []):
                epic_key = epic_keys.get(epic["id"])
                if not epic_key:
                    continue
                
                for story in epic.get("stories", []):
                    try:
                        story_data = {
                            "title": story["title"],
                            "description": story["description"],
                            "priority": story.get("priority", "Medium"),
                            "assignee": assignee_mappings.get(story["id"]),
                            "acceptance_criteria": story.get("acceptance_criteria", [])
                        }
                        
                        story_key = await self.create_story(story_data, epic_key)
                        story_keys[story["id"]] = story_key
                        tickets_created += 1
                        
                    except Exception as e:
                        error_msg = f"Failed to create story '{story['title']}': {str(e)}"
                        errors.append(error_msg)
                        tickets_failed += 1
                        logger.error(error_msg)
            
            # Create subtasks
            for epic in decomposition.get("epics", []):
                for story in epic.get("stories", []):
                    story_key = story_keys.get(story["id"])
                    if not story_key:
                        continue
                    
                    for subtask in story.get("subtasks", []):
                        try:
                            subtask_data = {
                                "title": subtask["title"],
                                "description": subtask["description"],
                                "priority": subtask.get("priority", "Medium"),
                                "assignee": assignee_mappings.get(subtask["id"])
                            }
                            
                            subtask_key = await self.create_subtask(subtask_data, story_key)
                            subtask_keys[subtask["id"]] = subtask_key
                            tickets_created += 1
                            
                        except Exception as e:
                            error_msg = f"Failed to create subtask '{subtask['title']}': {str(e)}"
                            errors.append(error_msg)
                            tickets_failed += 1
                            logger.error(error_msg)
            
            return JiraSyncResult(
                document_id=decomposition.get("document_id", ""),
                sync_date=datetime.now(),
                tickets_created=tickets_created,
                tickets_updated=0,
                tickets_failed=tickets_failed,
                epic_keys=epic_keys,
                story_keys=story_keys,
                subtask_keys=subtask_keys,
                errors=errors
            )
            
        except Exception as e:
            logger.error(f"Error syncing requirements to Jira: {str(e)}")
            raise

