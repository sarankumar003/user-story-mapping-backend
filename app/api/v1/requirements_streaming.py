"""
Streaming Requirements API
Enhanced API endpoints with streaming support and validation
"""

import json
import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from app.services.streaming_ai_agent import StreamingAIAgent
from app.services.run_manager import RunManager
from app.models.document import DocumentStatus
from app.models.requirement import RequirementsDecomposition

logger = logging.getLogger(__name__)

router = APIRouter()
run_manager = RunManager()
streaming_ai_agent = StreamingAIAgent()


@router.post("/decompose_streaming/{run_id}")
async def decompose_requirements_streaming(run_id: str):
    """
    Trigger streaming requirements decomposition for a run.
    Returns a streaming response with progress updates.
    """
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Check if summary exists
    summary = run_manager.load_document_summary(run_id)
    if not summary:
        raise HTTPException(status_code=400, detail="Document summary not found. Please generate summary first.")

    # Update run status to processing
    run_manager.update_run_status(run_id, DocumentStatus.PROCESSING)

    async def generate_stream():
        try:
            # Yield initial status
            yield f"data: {json.dumps({'type': 'status', 'message': 'Starting decomposition...'})}\n\n"
            
            # Start streaming decomposition
            async for result in streaming_ai_agent.decompose_requirements_streaming(summary):
                if result["type"] == "progress":
                    yield f"data: {json.dumps({'type': 'progress', 'chunks_received': result['chunks_received'], 'response_length': result['response_length']})}\n\n"
                
                elif result["type"] == "chunk_start":
                    yield f"data: {json.dumps({'type': 'chunk_start', 'chunk_index': result['chunk_index'], 'total_chunks': result['total_chunks']})}\n\n"
                
                elif result["type"] == "chunk_complete":
                    yield f"data: {json.dumps({'type': 'chunk_complete', 'chunk_index': result['chunk_index'], 'epics_count': result['epics_count']})}\n\n"
                
                elif result["type"] == "complete":
                    # Save the final result
                    decomposition_data = result["data"]
                    warnings = result.get("warnings", [])
                    was_repaired = result.get("was_repaired", False)
                    
                    # Create RequirementsDecomposition object
                    decomposition = RequirementsDecomposition(
                        document_id=run_id,
                        created_at=run.get("created_at", ""),
                        epics=decomposition_data.get("epics", []),
                        total_estimated_hours=decomposition_data.get("total_estimated_hours", 0),
                        timeline_weeks=decomposition_data.get("timeline_weeks", 1)
                    )
                    
                    # Save to run manager
                    run_manager.save_requirements_decomposition(run_id, decomposition)
                    
                    # Save raw response for debugging
                    raw_response = {
                        "raw": json.dumps(decomposition_data),
                        "warnings": warnings,
                        "was_repaired": was_repaired,
                        "generated_at": run.get("created_at", "")
                    }
                    run_manager.save_intermediate(run_id, "decomposition_raw.json", raw_response)
                    
                    # Update run status
                    run_manager.update_run_status(run_id, DocumentStatus.COMPLETED)
                    
                    # Yield final result
                    yield f"data: {json.dumps({'type': 'complete', 'epics_count': len(decomposition_data.get('epics', [])), 'total_hours': decomposition_data.get('total_estimated_hours', 0), 'warnings': warnings, 'was_repaired': was_repaired})}\n\n"
                    break
                
                elif result["type"] == "error":
                    # Handle error
                    run_manager.update_run_status(run_id, DocumentStatus.FAILED)
                    yield f"data: {json.dumps({'type': 'error', 'error': result['error']})}\n\n"
                    break
            
            # Send end of stream
            yield f"data: {json.dumps({'type': 'end'})}\n\n"
            
        except Exception as e:
            logger.error(f"Error in streaming decomposition for run {run_id}: {e}")
            run_manager.update_run_status(run_id, DocumentStatus.FAILED)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


@router.get("/decomposition_validation/{run_id}")
async def validate_decomposition(run_id: str):
    """
    Validate the decomposition for a run and return validation results.
    """
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

        # Validate each epic
        for i, epic in enumerate(epics):
            if not isinstance(epic, dict):
                validation_result["warnings"].append(f"Epic {i} is not a dictionary")
                continue

            # Check required epic fields
            required_epic_fields = ["id", "title", "description", "priority", "stories"]
            for field in required_epic_fields:
                if field not in epic:
                    validation_result["warnings"].append(f"Epic {i} missing required field: {field}")

            # Validate stories
            stories = epic.get("stories", [])
            if isinstance(stories, list):
                for j, story in enumerate(stories):
                    if not isinstance(story, dict):
                        validation_result["warnings"].append(f"Epic {i}, Story {j} is not a dictionary")
                        continue

                    # Check required story fields
                    required_story_fields = ["id", "title", "description", "acceptance_criteria", "priority", "subtasks"]
                    for field in required_story_fields:
                        if field not in story:
                            validation_result["warnings"].append(f"Epic {i}, Story {j} missing required field: {field}")

                    # Validate subtasks
                    subtasks = story.get("subtasks", [])
                    if isinstance(subtasks, list):
                        for k, subtask in enumerate(subtasks):
                            if not isinstance(subtask, dict):
                                validation_result["warnings"].append(f"Epic {i}, Story {j}, Subtask {k} is not a dictionary")
                                continue

                            # Check required subtask fields
                            required_subtask_fields = ["id", "title", "description", "priority"]
                            for field in required_subtask_fields:
                                if field not in subtask:
                                    validation_result["warnings"].append(f"Epic {i}, Story {j}, Subtask {k} missing required field: {field}")

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

        # Check for duplicate IDs
        all_ids = []
        for epic in epics:
            if isinstance(epic, dict) and "id" in epic:
                all_ids.append(epic["id"])
                stories = epic.get("stories", [])
                if isinstance(stories, list):
                    for story in stories:
                        if isinstance(story, dict) and "id" in story:
                            all_ids.append(story["id"])
                            subtasks = story.get("subtasks", [])
                            if isinstance(subtasks, list):
                                for subtask in subtasks:
                                    if isinstance(subtask, dict) and "id" in subtask:
                                        all_ids.append(subtask["id"])

        duplicate_ids = [id for id in set(all_ids) if all_ids.count(id) > 1]
        if duplicate_ids:
            validation_result["warnings"].append(f"Duplicate IDs found: {duplicate_ids}")

    except Exception as e:
        logger.error(f"Error validating decomposition for run {run_id}: {e}")
        validation_result["is_valid"] = False
        validation_result["errors"].append(f"Validation error: {str(e)}")

    return validation_result


@router.post("/decompose_with_validation/{run_id}")
async def decompose_requirements_with_validation(run_id: str):
    """
    Decompose requirements with real-time validation and progress updates.
    This endpoint combines streaming decomposition with validation.
    """
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Check if summary exists
    summary = run_manager.load_document_summary(run_id)
    if not summary:
        raise HTTPException(status_code=400, detail="Document summary not found. Please generate summary first.")

    # Update run status to processing
    run_manager.update_run_status(run_id, DocumentStatus.PROCESSING)

    async def generate_validated_stream():
        try:
            # Yield initial status
            yield f"data: {json.dumps({'type': 'status', 'message': 'Starting decomposition with validation...'})}\n\n"
            
            # Start streaming decomposition
            async for result in streaming_ai_agent.decompose_requirements_streaming(summary):
                if result["type"] == "progress":
                    yield f"data: {json.dumps({'type': 'progress', 'chunks_received': result['chunks_received'], 'response_length': result['response_length']})}\n\n"
                
                elif result["type"] == "chunk_start":
                    yield f"data: {json.dumps({'type': 'chunk_start', 'chunk_index': result['chunk_index'], 'total_chunks': result['total_chunks']})}\n\n"
                
                elif result["type"] == "chunk_complete":
                    yield f"data: {json.dumps({'type': 'chunk_complete', 'chunk_index': result['chunk_index'], 'epics_count': result['epics_count']})}\n\n"
                
                elif result["type"] == "complete":
                    # Validate the result before saving
                    decomposition_data = result["data"]
                    warnings = result.get("warnings", [])
                    was_repaired = result.get("was_repaired", False)
                    
                    # Perform validation
                    validation_result = await validate_decomposition(run_id)
                    
                    # Add validation warnings to the result
                    if validation_result["warnings"]:
                        warnings.extend(validation_result["warnings"])
                    
                    # Create RequirementsDecomposition object
                    decomposition = RequirementsDecomposition(
                        document_id=run_id,
                        created_at=run.get("created_at", ""),
                        epics=decomposition_data.get("epics", []),
                        total_estimated_hours=decomposition_data.get("total_estimated_hours", 0),
                        timeline_weeks=decomposition_data.get("timeline_weeks", 1)
                    )
                    
                    # Save to run manager
                    run_manager.save_requirements_decomposition(run_id, decomposition)
                    
                    # Save raw response with validation info
                    raw_response = {
                        "raw": json.dumps(decomposition_data),
                        "warnings": warnings,
                        "was_repaired": was_repaired,
                        "validation_result": validation_result,
                        "generated_at": run.get("created_at", "")
                    }
                    run_manager.save_intermediate(run_id, "decomposition_raw.json", raw_response)
                    
                    # Update run status
                    if validation_result["is_valid"]:
                        run_manager.update_run_status(run_id, DocumentStatus.COMPLETED)
                    else:
                        run_manager.update_run_status(run_id, DocumentStatus.FAILED)
                    
                    # Yield final result with validation
                    yield f"data: {json.dumps({'type': 'complete', 'epics_count': len(decomposition_data.get('epics', [])), 'total_hours': decomposition_data.get('total_estimated_hours', 0), 'warnings': warnings, 'was_repaired': was_repaired, 'validation': validation_result})}\n\n"
                    break
                
                elif result["type"] == "error":
                    # Handle error
                    run_manager.update_run_status(run_id, DocumentStatus.FAILED)
                    yield f"data: {json.dumps({'type': 'error', 'error': result['error']})}\n\n"
                    break
            
            # Send end of stream
            yield f"data: {json.dumps({'type': 'end'})}\n\n"
            
        except Exception as e:
            logger.error(f"Error in validated streaming decomposition for run {run_id}: {e}")
            run_manager.update_run_status(run_id, DocumentStatus.FAILED)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_validated_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )




