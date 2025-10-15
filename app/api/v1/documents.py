"""
Document upload and processing API endpoints
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from app.models.document import BRDDocument, DocumentStatus, DocumentUploadResponse
from app.services.run_manager import RunManager
from app.services.document_processor import DocumentProcessor
from app.services.ai_agent import AIAgent

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
run_manager = RunManager()
document_processor = DocumentProcessor()
ai_agent = AIAgent()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Upload and process a BRD document"""
    
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Check file size
        file_content = await file.read()
        file_size = len(file_content)
        
        # Reset file pointer
        await file.seek(0)
        
        # Create uploads directory
        uploads_dir = Path("uploads")
        uploads_dir.mkdir(exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = Path(file.filename).suffix
        unique_filename = f"{timestamp}_{file.filename}"
        file_path = uploads_dir / unique_filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Validate file
        is_valid, error_message = document_processor.validate_file(str(file_path), file_size)
        if not is_valid:
            # Clean up invalid file
            file_path.unlink()
            raise HTTPException(status_code=400, detail=error_message)
        
        # Create run
        run_id = run_manager.create_run(file.filename, str(file_path), file_size)
        
        # Start background processing
        background_tasks.add_task(process_document_background, run_id, str(file_path))
        
        return DocumentUploadResponse(
            document_id=run_id,
            file_name=file.filename,
            status=DocumentStatus.UPLOADED,
            message="Document uploaded successfully. Processing started."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/runs", response_model=List[dict])
async def get_runs(limit: int = 20):
    """Get all document processing runs"""
    try:
        runs = run_manager.get_all_runs(limit=limit)
        return runs
    except Exception as e:
        logger.error(f"Error getting runs: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/runs/{run_id}", response_model=dict)
async def get_run(run_id: str):
    """Get specific run details"""
    try:
        run = run_manager.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return run
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting run {run_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/runs/{run_id}/summary")
async def get_document_summary(run_id: str):
    """Get document summary for a run"""
    try:
        run = run_manager.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        
        summary = run_manager.load_document_summary(run_id)
        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found")
        
        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting summary for run {run_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def process_document_background(run_id: str, file_path: str):
    """Background task to process document"""
    try:
        logger.info(f"Starting background processing for run {run_id}")
        
        # Update status to processing
        run_manager.update_run_status(run_id, DocumentStatus.PROCESSING)
        
        # Extract text from document
        text = document_processor.extract_text(file_path)
        if not text:
            raise Exception("Failed to extract text from document")
        
        # Generate summary using AI
        summary = await ai_agent.generate_summary(text)
        
        # Save summary
        summary_dict = summary.dict()
        run_manager.save_document_summary(run_id, summary_dict)
        run_manager.update_run_step(run_id, "summary", "completed", {"summary_id": run_id})
        
        # Update status to summarized
        run_manager.update_run_status(run_id, DocumentStatus.SUMMARIZED)
        
        logger.info(f"Successfully processed document for run {run_id}")
        
    except Exception as e:
        logger.error(f"Error processing document for run {run_id}: {str(e)}")
        run_manager.update_run_status(run_id, DocumentStatus.ERROR)
        run_manager.update_run_step(run_id, "summary", "failed", {"error": str(e)})

