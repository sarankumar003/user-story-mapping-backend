"""
Document-related data models
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class DocumentStatus(str, Enum):
    """Document processing status"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    SUMMARIZED = "summarized"
    DECOMPOSED = "decomposed"
    COMPLETED = "completed"
    ERROR = "error"


class DocumentSummary(BaseModel):
    """BRD document summary"""
    project_name: str
    project_description: str
    objectives: List[str]
    scope: List[str]
    stakeholders: List[str]
    key_features: List[str]
    technical_requirements: List[str]
    timeline_estimate: str
    risks: List[str]
    assumptions: List[str]


class BRDDocument(BaseModel):
    """BRD document model"""
    id: str
    file_name: str
    file_path: str
    file_size: int
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    status: DocumentStatus = DocumentStatus.UPLOADED
    summary: Optional[DocumentSummary] = None
    error_message: Optional[str] = None


class DocumentUploadResponse(BaseModel):
    """Response for document upload"""
    document_id: str
    file_name: str
    status: DocumentStatus
    message: str

