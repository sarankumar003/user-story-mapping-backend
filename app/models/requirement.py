"""
Requirement decomposition models
"""

from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from enum import Enum


class Priority(str, Enum):
    """Task priority levels"""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class TaskType(str, Enum):
    """Task types"""
    EPIC = "Epic"
    STORY = "Story"
    SUBTASK = "Subtask"


class TaskStatus(str, Enum):
    """Task status"""
    TODO = "To Do"
    IN_PROGRESS = "In Progress"
    DONE = "Done"


class Subtask(BaseModel):
    """Subtask model"""
    id: str
    title: str
    description: str
    priority: Priority = Priority.MEDIUM
    estimated_hours: Optional[int] = None
    assignee: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    dependencies: List[str] = Field(default_factory=list)


class Story(BaseModel):
    """User story model"""
    id: str
    title: str
    description: str
    acceptance_criteria: List[str] = Field(default_factory=list)
    priority: Priority = Priority.MEDIUM
    estimated_hours: Optional[int] = None
    assignee: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    subtasks: List[Subtask] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)


class Epic(BaseModel):
    """Epic model"""
    id: str
    title: str
    description: str
    priority: Priority = Priority.MEDIUM
    estimated_hours: Optional[int] = None
    assignee: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    stories: List[Story] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)


class RequirementsDecomposition(BaseModel):
    """Complete requirements decomposition"""
    document_id: str
    created_at: datetime
    epics: List[Epic] = Field(default_factory=list)
    total_estimated_hours: Optional[int] = None
    timeline_weeks: Optional[int] = None


class AssigneeMapping(BaseModel):
    """Assignee mapping for tasks"""
    task_id: str
    task_type: TaskType
    assignee_id: str
    assignee_name: str
    team: Optional[str] = None
