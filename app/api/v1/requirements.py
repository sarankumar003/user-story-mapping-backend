"""
Requirements decomposition API endpoints
"""

import logging
import json
from datetime import datetime
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
import asyncio

from app.models.requirement import RequirementsDecomposition, AssigneeMapping
from app.models.document import DocumentStatus
from app.services.run_manager import RunManager
from app.services.ai_agent import AIAgent
from app.services.streaming_ai_agent import StreamingAIAgent
from app.api.v1.documents import process_document_background
from app.services.json_repair import sanitize_and_repair

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
run_manager = RunManager()
ai_agent = AIAgent()
streaming_ai_agent = StreamingAIAgent()
def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_subtasks(subtasks):
    items = _as_list(subtasks)
    normalized = []
    for i, st in enumerate(items):
        if not isinstance(st, dict):
            continue
        normalized.append({
            "id": st.get("id") or st.get("task_id") or f"SUBTASK-{i+1}",
            "title": st.get("title") or st.get("name") or "Untitled Subtask",
            "description": st.get("description") or st.get("details"),
            "assignee": st.get("assignee"),
            "priority": (st.get("priority") or "Medium"),
            "estimated_hours": st.get("estimated_hours", 0),
            "status": st.get("status", "To Do"),
        })
    return normalized


def _normalize_stories(stories):
    items = _as_list(stories)
    normalized = []
    for i, st in enumerate(items):
        if not isinstance(st, dict):
            continue
        normalized.append({
            "id": st.get("id") or st.get("story_id") or f"STORY-{i+1}",
            "title": st.get("title") or st.get("name") or "Untitled Story",
            "description": st.get("description") or st.get("details"),
            "assignee": st.get("assignee"),
            "priority": (st.get("priority") or "Medium"),
            "estimated_hours": st.get("estimated_hours", 0),
            "status": st.get("status", "To Do"),
            "acceptance_criteria": _as_list(st.get("acceptance_criteria")),
            "subtasks": _normalize_subtasks(st.get("subtasks")),
        })
    return normalized


def _normalize_epics(epics):
    items = _as_list(epics)
    normalized = []
    for i, ep in enumerate(items):
        if not isinstance(ep, dict):
            continue
        normalized.append({
            "id": ep.get("id") or ep.get("epic_id") or f"EPIC-{i+1}",
            "title": ep.get("title") or ep.get("name") or "Untitled Epic",
            "description": ep.get("description") or ep.get("details"),
            "assignee": ep.get("assignee"),
            "priority": (ep.get("priority") or "Medium"),
            "estimated_hours": ep.get("estimated_hours", 0),
            "status": ep.get("status", "To Do"),
            "stories": _normalize_stories(ep.get("stories")),
        })
    return normalized


def _normalize_decomposition_object(obj):
    """Normalize arbitrary LLM schemas into the structure the UI expects.

    Expected output shape:
    {
      "epics": [ { id, title, description, priority, assignee, stories: [ { ... , subtasks: [...] } ] } ],
      "notes": Optional[str],
      "warnings": List[str]
    }
    """
    if not isinstance(obj, dict):
        return {"epics": [], "warnings": ["object_not_dict"]}

    # Some models nest the content under top-level keys like data, result, decomposition
    for key in ["epics", "data", "result", "decomposition", "payload"]:
        if key in obj and isinstance(obj.get(key), dict) and "epics" in obj[key]:
            obj = obj[key]
            break

    epics = obj.get("epics")
    normalized = {
        "epics": _normalize_epics(epics),
        "total_estimated_hours": obj.get("total_estimated_hours", 0),
        "timeline_weeks": obj.get("timeline_weeks", 1),
        "notes": obj.get("notes") or obj.get("summary"),
        "warnings": _as_list(obj.get("warnings")),
    }
    return normalized


@router.post("/decompose/{run_id}")
async def decompose_requirements(run_id: str):
    """Trigger requirements decomposition for a run.
    - If summary missing, it will start summary generation first, then decompose.
    - Waits for completion and returns the result.
    """
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    try:
        # Run orchestrator synchronously
        await orchestrate_decomposition_sync(run_id)
        
        # Return the decomposition result
        decomposition = run_manager.load_requirements_decomposition(run_id)
        if not decomposition:
            raise HTTPException(status_code=500, detail="Decomposition failed to complete")
        
        return {
            "status": "completed", 
            "message": "Decomposition completed successfully", 
            "run_id": run_id,
            "decomposition": decomposition
        }
    except Exception as e:
        logger.error(f"Decomposition failed for run {run_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Decomposition failed: {str(e)}")


@router.post("/decompose_enhanced/{run_id}")
async def decompose_requirements_enhanced(run_id: str):
    """Enhanced requirements decomposition with streaming and validation.
    - Uses streaming AI agent to avoid truncation
    - Includes real-time validation
    - Returns detailed progress and validation results
    """
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Check if summary exists
    summary_data = run_manager.load_document_summary(run_id)
    if not summary_data:
        raise HTTPException(status_code=400, detail="Document summary not found. Please generate summary first.")

    try:
        # Convert dict to DocumentSummary object
        from app.models.document import DocumentSummary
        summary = DocumentSummary(**summary_data)
        
        # Update run status to processing
        run_manager.update_run_status(run_id, DocumentStatus.PROCESSING)
        
        # Use streaming AI agent for decomposition
        final_result = None
        warnings = []
        was_repaired = False
        
        async for result in streaming_ai_agent.decompose_requirements_streaming(summary):
            if result["type"] == "complete":
                final_result = result["data"]
                warnings = result.get("warnings", [])
                was_repaired = result.get("was_repaired", False)
                break
            elif result["type"] == "error":
                run_manager.update_run_status(run_id, DocumentStatus.ERROR)
                raise HTTPException(status_code=500, detail=f"Decomposition failed: {result['error']}")
        
        if not final_result:
            raise HTTPException(status_code=500, detail="Decomposition did not complete")
        
        # Create RequirementsDecomposition object
        decomposition = RequirementsDecomposition(
            document_id=run_id,
            created_at=run.get("created_at", ""),
            epics=final_result.get("epics", []),
            total_estimated_hours=final_result.get("total_estimated_hours", 0),
            timeline_weeks=final_result.get("timeline_weeks", 1)
        )
        
        # Save to run manager
        run_manager.save_requirements_decomposition(run_id, decomposition.model_dump(mode='json'))
        
        # Save raw response with validation info
        raw_response = {
            "raw": json.dumps(final_result),
            "warnings": warnings,
            "was_repaired": was_repaired,
            "generated_at": run.get("created_at", "")
        }
        run_manager.save_intermediate(run_id, "decomposition_raw.json", raw_response)
        
        # Update run status
        run_manager.update_run_status(run_id, DocumentStatus.COMPLETED)
        
        return {
            "status": "completed",
            "message": "Enhanced decomposition completed successfully",
            "run_id": run_id,
            "decomposition": decomposition.model_dump(mode='json'),
            "warnings": warnings,
            "was_repaired": was_repaired,
            "epics_count": len(final_result.get("epics", [])),
            "total_hours": final_result.get("total_estimated_hours", 0)
        }
        
    except Exception as e:
        logger.error(f"Error in enhanced decomposition for run {run_id}: {e}")
        run_manager.update_run_status(run_id, DocumentStatus.ERROR)
        raise HTTPException(status_code=500, detail=f"Enhanced decomposition failed: {str(e)}")


@router.post("/decompose_streaming/{run_id}")
async def decompose_requirements_streaming(run_id: str):
    """Streaming requirements decomposition for a run."""
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Check if summary exists
    summary_data = run_manager.load_document_summary(run_id)
    if not summary_data:
        raise HTTPException(status_code=400, detail="Document summary not found. Please generate summary first.")

    try:
        # Convert dict to DocumentSummary object
        from app.models.document import DocumentSummary
        summary = DocumentSummary(**summary_data)
        
        # Update run status to processing
        run_manager.update_run_status(run_id, DocumentStatus.PROCESSING)
        
        # Use streaming AI agent for decomposition
        final_result = None
        warnings = []
        was_repaired = False
        
        async for result in streaming_ai_agent.decompose_requirements_streaming(summary):
            if result["type"] == "complete":
                final_result = result["data"]
                warnings = result.get("warnings", [])
                was_repaired = result.get("was_repaired", False)
                break
            elif result["type"] == "error":
                run_manager.update_run_status(run_id, DocumentStatus.ERROR)
                raise HTTPException(status_code=500, detail=f"Decomposition failed: {result['error']}")
        
        if not final_result:
            raise HTTPException(status_code=500, detail="Decomposition did not complete")
        
        # Create RequirementsDecomposition object
        decomposition = RequirementsDecomposition(
            document_id=run_id,
            created_at=run.get("created_at", ""),
            epics=final_result.get("epics", []),
            total_estimated_hours=final_result.get("total_estimated_hours", 0),
            timeline_weeks=final_result.get("timeline_weeks", 1)
        )
        
        # Save to run manager
        run_manager.save_requirements_decomposition(run_id, decomposition.model_dump(mode='json'))
        
        # Save raw response with validation info
        raw_response = {
            "raw": json.dumps(final_result),
            "warnings": warnings,
            "was_repaired": was_repaired,
            "generated_at": run.get("created_at", "")
        }
        run_manager.save_intermediate(run_id, "decomposition_raw.json", raw_response)
        
        # Update run status
        run_manager.update_run_status(run_id, DocumentStatus.COMPLETED)
        
        return {
            "status": "completed",
            "message": "Streaming decomposition completed successfully",
            "run_id": run_id,
            "decomposition": decomposition.model_dump(mode='json'),
            "warnings": warnings,
            "was_repaired": was_repaired,
            "epics_count": len(final_result.get("epics", [])),
            "total_hours": final_result.get("total_estimated_hours", 0)
        }
        
    except Exception as e:
        logger.error(f"Error in streaming decomposition for run {run_id}: {e}")
        run_manager.update_run_status(run_id, DocumentStatus.ERROR)
        raise HTTPException(status_code=500, detail=f"Streaming decomposition failed: {str(e)}")


@router.get("/decomposition_validation/{run_id}")
async def validate_decomposition(run_id: str):
    """Validate the decomposition for a run and return validation results."""
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Load raw decomposition
    raw_data = run_manager.load_intermediate(run_id, "decomposition_raw.json")
    if not raw_data:
        raise HTTPException(status_code=404, detail="Raw decomposition not found")

    validation_result = {
        "run_id": run_id,
        "is_valid": True,
        "warnings": [],
        "errors": [],
        "statistics": {
            "epics_count": 0,
            "stories_count": 0,
            "subtasks_count": 0,
            "total_hours": 0
        }
    }

    try:
        # Parse the raw data
        raw_content = raw_data.get("raw", "")
        if isinstance(raw_content, str):
            try:
                parsed_data = json.loads(raw_content)
            except json.JSONDecodeError as e:
                validation_result["is_valid"] = False
                validation_result["errors"].append(f"JSON parsing failed: {str(e)}")
                return validation_result
        else:
            parsed_data = raw_content

        # Validate structure
        if not isinstance(parsed_data, dict):
            validation_result["is_valid"] = False
            validation_result["errors"].append("Root object is not a dictionary")
            return validation_result

        # Check for required fields
        if "epics" not in parsed_data:
            validation_result["is_valid"] = False
            validation_result["errors"].append("Missing 'epics' field")
            return validation_result

        epics = parsed_data.get("epics", [])
        if not isinstance(epics, list):
            validation_result["is_valid"] = False
            validation_result["errors"].append("'epics' field is not a list")
            return validation_result

        # Calculate statistics
        validation_result["statistics"]["epics_count"] = len(epics)
        validation_result["statistics"]["total_hours"] = parsed_data.get("total_estimated_hours", 0)
        
        total_stories = 0
        total_subtasks = 0
        for epic in epics:
            if isinstance(epic, dict):
                stories = epic.get("stories", [])
                if isinstance(stories, list):
                    total_stories += len(stories)
                    for story in stories:
                        if isinstance(story, dict):
                            subtasks = story.get("subtasks", [])
                            if isinstance(subtasks, list):
                                total_subtasks += len(subtasks)

        validation_result["statistics"]["stories_count"] = total_stories
        validation_result["statistics"]["subtasks_count"] = total_subtasks

        # Check for potential issues
        if validation_result["statistics"]["epics_count"] == 0:
            validation_result["warnings"].append("No epics found in decomposition")
        
        if validation_result["statistics"]["total_hours"] == 0:
            validation_result["warnings"].append("Total estimated hours is 0")

    except Exception as e:
        logger.error(f"Error validating decomposition for run {run_id}: {e}")
        validation_result["is_valid"] = False
        validation_result["errors"].append(f"Validation error: {str(e)}")

    return validation_result


async def orchestrate_decomposition_sync(run_id: str):
    """Generate summary if needed, then decompose. Waits for completion."""
    try:
        run = run_manager.get_run(run_id)
        if not run:
            logger.error(f"Orchestrator: run {run_id} not found")
            raise HTTPException(status_code=404, detail="Run not found")

        # If summary missing, start document processing
        summary = run_manager.load_document_summary(run_id)
        if not summary:
            file_path = run.get("file_path")
            if not file_path:
                logger.error(f"Orchestrator: run {run_id} missing file_path")
                raise HTTPException(status_code=400, detail="File path not found")
            
            # Process document synchronously
            await process_document_sync(run_id, file_path)
            
            # Wait for summary to be available
            for _ in range(30):
                summary = run_manager.load_document_summary(run_id)
                if summary:
                    break
                await asyncio.sleep(2)

            if not summary:
                logger.error(f"Orchestrator: summary still not available for run {run_id}")
                raise HTTPException(status_code=500, detail="Summary generation failed")

        # Start decomposition synchronously
        await decompose_requirements_sync(run_id, summary)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Orchestrator error for run {run_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Orchestration failed: {str(e)}")


async def orchestrate_decomposition_background(run_id: str):
    """Generate summary if needed, then decompose. Polls until summary appears or times out."""
    try:
        run = run_manager.get_run(run_id)
        if not run:
            logger.error(f"Orchestrator: run {run_id} not found")
            return

        # If summary missing, start document processing
        summary = run_manager.load_document_summary(run_id)
        if not summary:
            file_path = run.get("file_path")
            if not file_path:
                logger.error(f"Orchestrator: run {run_id} missing file_path")
                return
            await process_document_background(run_id, file_path)

        # Poll for summary (up to ~60s)
        for _ in range(30):
            summary = run_manager.load_document_summary(run_id)
            if summary:
                break
            await asyncio.sleep(2)

        if not summary:
            logger.error(f"Orchestrator: summary still not available for run {run_id}")
            return

        # Start decomposition
        await decompose_requirements_background(run_id, summary)

    except Exception as e:
        logger.error(f"Orchestrator error for run {run_id}: {e}")


@router.get("/decomposition/{run_id}")
async def get_requirements_decomposition(run_id: str):
    """Return the latest requirements decomposition for the run."""
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    decomposition = run_manager.load_requirements_decomposition(run_id)
    if not decomposition:
        raise HTTPException(status_code=404, detail="Decomposition not found")

    return decomposition


@router.get("/decomposition_raw/{run_id}")
async def get_requirements_decomposition_raw(run_id: str):
    """Return the parsed raw decomposition JSON (LLM output parsed and structured)."""
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    raw = run_manager.load_intermediate(run_id, "decomposition_raw.json")
    if not raw:
        raise HTTPException(status_code=404, detail="Raw decomposition not found")

    # Extract and parse the raw JSON from LLM response with robust normalization
    payload = raw.get("raw", raw.get("raw_text", raw))
    import json
    try:
        if isinstance(payload, str):
            # Prefer a direct decode first (fast path for already-valid JSON strings)
            try:
                obj = json.loads(payload)
            except Exception:
                # 1) Best-effort repair for common LLM artifacts
                text, _ = sanitize_and_repair(payload)
                try:
                    # Some responses may still include surrounding quotes or code fences
                    cleaned = ai_agent._clean_and_validate_json(text)  # type: ignore[attr-defined]
                except Exception:
                    cleaned = text
                obj = json.loads(cleaned)
        elif isinstance(payload, dict):
            obj = payload
        else:
            raise ValueError("Unsupported payload type")

        normalized = _normalize_decomposition_object(obj)

        # Fallbacks: if epics parsed empty but we still have a raw string, try alternate decodes
        if not normalized.get("epics"):
            raw_text = raw.get("raw") if isinstance(raw, dict) else None
            if isinstance(raw_text, str):
                try:
                    alt_obj = json.loads(raw_text)
                    alt_norm = _normalize_decomposition_object(alt_obj)
                    if alt_norm.get("epics"):
                        normalized = alt_norm
                except Exception:
                    # Try double-decoding if the payload was encoded twice
                    try:
                        alt_obj2 = json.loads(json.loads(raw_text))
                        alt_norm2 = _normalize_decomposition_object(alt_obj2)
                        if alt_norm2.get("epics"):
                            normalized = alt_norm2
                    except Exception:
                        pass

        return {
            "run_id": run_id,
            "source_summary_path": f"runs/{run_id}/intermediate/summary.json",
            "generated_at": run.get("created_at", ""),
            "epics": normalized.get("epics", []),
            "total_estimated_hours": normalized.get("total_estimated_hours", 0),
            "timeline_weeks": normalized.get("timeline_weeks", 1),
            "notes": normalized.get("notes"),
            "warnings": normalized.get("warnings", []),
            "schema_version": "raw-1.0.1"
        }
    except Exception as e:
        logger.error(f"Failed to parse/normalize raw JSON for run {run_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse raw decomposition data")


@router.post("/assignees/{run_id}")
async def suggest_assignees(run_id: str, team_members: List[Dict[str, Any]]):
    """Endpoint disabled: assignee suggestion not required currently."""
    raise HTTPException(status_code=410, detail="Assignee suggestion feature removed")


@router.put("/assignees/{run_id}")
async def update_assignees(run_id: str, assignee_mappings: List[AssigneeMapping]):
    """Endpoint disabled: assignee update not required currently."""
    raise HTTPException(status_code=410, detail="Assignee update feature removed")


async def decompose_requirements_background(run_id: str, summary: Dict[str, Any]):
    """Background task to decompose requirements"""
    
    try:
        logger.info(f"Starting requirements decomposition for run {run_id}")
        
        # Update status
        run_manager.update_run_step(run_id, "decomposition", "in_progress")
        
        # Convert summary to DocumentSummary model
        from app.models.document import DocumentSummary
        document_summary = DocumentSummary(**summary)
        
        # Decompose requirements using AI with retries and raw logging
        logger.info(f"Starting AI decomposition for run {run_id}")
        raw_attempts = []
        last_exception = None
        for attempt in range(3):
            try:
                decomposition, raw_text = await ai_agent.decompose_requirements(document_summary)
                try:
                    # Save raw response for debugging
                    run_manager.save_intermediate(run_id, "decomposition_raw.json", {"raw": raw_text})
                except Exception:
                    pass
                logger.info(f"AI decomposition completed for run {run_id} on attempt {attempt+1}")
                break
            except Exception as e:
                last_exception = e
        else:
            logger.error(f"AI decomposition failed after retries for run {run_id}: {last_exception}")
            raise last_exception
        
        # Set document_id and created_at
        decomposition.document_id = run_id
        decomposition.created_at = datetime.now()
        logger.info(f"Set document_id and created_at for run {run_id}")
        
        # Save decomposition (Pydantic v2)
        decomposition_dict = decomposition.model_dump(mode='json')
        run_manager.save_requirements_decomposition(run_id, decomposition_dict)
        run_manager.update_run_step(run_id, "decomposition", "completed")
        
        # Update run status
        from app.models.document import DocumentStatus
        run_manager.update_run_status(run_id, DocumentStatus.SUMMARIZED)
        
        logger.info(f"Successfully decomposed requirements for run {run_id}")
        
    except Exception as e:
        logger.error(f"Error decomposing requirements for run {run_id}: {str(e)}")
        run_manager.update_run_step(run_id, "decomposition", "failed", {"error": str(e)})


async def process_document_sync(run_id: str, file_path: str):
    """Synchronous document processing"""
    try:
        logger.info(f"Starting synchronous processing for run {run_id}")
        
        # Update status to processing
        from app.models.document import DocumentStatus
        run_manager.update_run_status(run_id, DocumentStatus.PROCESSING)
        
        # Extract text from document
        from app.services.document_processor import DocumentProcessor
        document_processor = DocumentProcessor()
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
        from app.models.document import DocumentStatus
        run_manager.update_run_status(run_id, DocumentStatus.ERROR)
        run_manager.update_run_step(run_id, "summary", "failed", {"error": str(e)})
        raise


async def decompose_requirements_sync(run_id: str, summary: Dict[str, Any]):
    """Synchronous requirements decomposition"""
    try:
        logger.info(f"Starting synchronous requirements decomposition for run {run_id}")
        
        # Update status
        run_manager.update_run_step(run_id, "decomposition", "in_progress")
        
        # Convert summary to DocumentSummary model
        from app.models.document import DocumentSummary
        document_summary = DocumentSummary(**summary)
        
        # Decompose requirements using AI with retries and raw logging
        logger.info(f"Starting AI decomposition for run {run_id}")
        last_exception = None
        for attempt in range(3):
            try:
                decomposition, raw_text = await ai_agent.decompose_requirements(document_summary)
                try:
                    # Save raw response for debugging
                    run_manager.save_intermediate(run_id, "decomposition_raw.json", {"raw": raw_text})
                except Exception:
                    pass
                logger.info(f"AI decomposition completed for run {run_id} on attempt {attempt+1}")
                break
            except Exception as e:
                last_exception = e
        else:
            logger.error(f"AI decomposition failed after retries for run {run_id}: {last_exception}")
            raise last_exception
        
        # Set document_id and created_at
        decomposition.document_id = run_id
        decomposition.created_at = datetime.now()
        logger.info(f"Set document_id and created_at for run {run_id}")
        
        # Save decomposition (Pydantic v2)
        decomposition_dict = decomposition.model_dump(mode='json')
        run_manager.save_requirements_decomposition(run_id, decomposition_dict)
        run_manager.update_run_step(run_id, "decomposition", "completed")
        
        # Update run status
        from app.models.document import DocumentStatus
        run_manager.update_run_status(run_id, DocumentStatus.SUMMARIZED)
        
        logger.info(f"Successfully decomposed requirements for run {run_id}")
        
    except Exception as e:
        logger.error(f"Error decomposing requirements for run {run_id}: {str(e)}")
        run_manager.update_run_step(run_id, "decomposition", "failed", {"error": str(e)})
        from app.models.document import DocumentStatus
        run_manager.update_run_status(run_id, DocumentStatus.ERROR)
        raise
