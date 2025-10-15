"""
Jira integration models
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class JiraIssueType(str, Enum):
    """Jira issue types"""
    EPIC = "Epic"
    STORY = "Story"
    SUBTASK = "Subtask"


class JiraTicket(BaseModel):
    """Jira ticket model"""
    key: Optional[str] = None
    issue_type: JiraIssueType
    summary: str
    description: str
    project_key: str
    assignee: Optional[str] = None
    priority: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    epic_link: Optional[str] = None
    parent_key: Optional[str] = None
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class JiraProject(BaseModel):
    """Jira project model"""
    key: str
    name: str
    project_type: str
    lead: Optional[str] = None


class JiraUser(BaseModel):
    """Jira user model"""
    account_id: str
    display_name: str
    email_address: Optional[str] = None
    active: bool = True
    role: Optional[str] = None


class JiraSyncResult(BaseModel):
    """Result of Jira synchronization"""
    document_id: str
    sync_date: datetime
    tickets_created: int
    tickets_updated: int
    tickets_failed: int
    epic_keys: Dict[str, str] = Field(default_factory=dict)  # epic_id -> jira_key
    story_keys: Dict[str, str] = Field(default_factory=dict)  # story_id -> jira_key
    subtask_keys: Dict[str, str] = Field(default_factory=dict)  # subtask_id -> jira_key
    errors: List[str] = Field(default_factory=list)


class JiraBoard(BaseModel):
    """Jira board model"""
    id: int
    name: str
    type: str
    project_key: str
    location: Optional[Dict[str, Any]] = None
