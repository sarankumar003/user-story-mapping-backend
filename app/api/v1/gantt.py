"""
Gantt chart generation API endpoints
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.services.run_manager import RunManager

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
run_manager = RunManager()


@router.post("/generate/{run_id}")
async def generate_gantt_chart(
    background_tasks: BackgroundTasks,
    run_id: str,
    start_date: str = None,
    team_size: int = 5
):
    """Generate Gantt chart for requirements decomposition"""
    
    try:
        # Check if run exists
        run = run_manager.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        
        # Check if decomposition exists
        decomposition = run_manager.load_requirements_decomposition(run_id)
        if not decomposition:
            raise HTTPException(status_code=404, detail="Requirements decomposition not found")
        
        # Start background Gantt generation
        background_tasks.add_task(
            generate_gantt_background, 
            run_id, 
            decomposition, 
            start_date, 
            team_size
        )
        
        return {"message": "Gantt chart generation started", "run_id": run_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting Gantt generation for run {run_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/chart/{run_id}")
async def get_gantt_chart(run_id: str):
    """Get Gantt chart data for a run"""
    
    try:
        run = run_manager.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        
        gantt_data = run_manager.load_gantt_data(run_id)
        if not gantt_data:
            raise HTTPException(status_code=404, detail="Gantt chart not found")
        
        return gantt_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Gantt chart for run {run_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def generate_gantt_background(
    run_id: str, 
    decomposition: Dict[str, Any], 
    start_date: str = None, 
    team_size: int = 5
):
    """Background task to generate Gantt chart"""
    
    try:
        logger.info(f"Starting Gantt chart generation for run {run_id}")
        
        # Update status
        run_manager.update_run_step(run_id, "gantt", "in_progress")
        
        # Parse start date
        if start_date:
            project_start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        else:
            project_start = datetime.now()
        
        # Generate Gantt data
        gantt_data = generate_gantt_data(decomposition, project_start, team_size)
        
        # Save Gantt data
        run_manager.save_gantt_data(run_id, gantt_data)
        run_manager.update_run_step(run_id, "gantt", "completed")
        
        logger.info(f"Successfully generated Gantt chart for run {run_id}")
        
    except Exception as e:
        logger.error(f"Error generating Gantt chart for run {run_id}: {str(e)}")
        run_manager.update_run_step(run_id, "gantt", "failed", {"error": str(e)})


def generate_gantt_data(decomposition: Dict[str, Any], start_date: datetime, team_size: int) -> Dict[str, Any]:
    """Generate Gantt chart data structure"""
    
    gantt_tasks = []
    current_date = start_date
    task_id = 1
    
    # Process epics
    for epic in decomposition.get("epics", []):
        epic_start = current_date
        epic_duration = 0
        
        # Process stories in epic
        for story in epic.get("stories", []):
            story_start = current_date
            story_duration = 0
            
            # Process subtasks in story
            for subtask in story.get("subtasks", []):
                estimated_hours = subtask.get("estimated_hours", 8)
                duration_days = max(1, estimated_hours // 8)  # Convert hours to days
                
                gantt_tasks.append({
                    "id": f"task_{task_id}",
                    "text": subtask["title"],
                    "start_date": current_date.isoformat(),
                    "duration": duration_days,
                    "progress": 0,
                    "parent": f"story_{story['id']}",
                    "type": "task",
                    "priority": subtask.get("priority", "Medium"),
                    "assignee": subtask.get("assignee"),
                    "estimated_hours": estimated_hours
                })
                
                current_date += timedelta(days=duration_days)
                story_duration += duration_days
                task_id += 1
            
            # Add story task
            gantt_tasks.append({
                "id": f"story_{story['id']}",
                "text": story["title"],
                "start_date": story_start.isoformat(),
                "duration": story_duration,
                "progress": 0,
                "parent": f"epic_{epic['id']}",
                "type": "project",
                "priority": story.get("priority", "Medium"),
                "assignee": story.get("assignee"),
                "estimated_hours": story.get("estimated_hours", 0)
            })
            
            epic_duration += story_duration
        
        # Add epic task
        gantt_tasks.append({
            "id": f"epic_{epic['id']}",
            "text": epic["title"],
            "start_date": epic_start.isoformat(),
            "duration": epic_duration,
            "progress": 0,
            "parent": "project",
            "type": "project",
            "priority": epic.get("priority", "Medium"),
            "assignee": epic.get("assignee"),
            "estimated_hours": epic.get("estimated_hours", 0)
        })
    
    # Calculate project end date
    project_end = current_date
    
    # Add project summary task
    gantt_tasks.append({
        "id": "project",
        "text": "Project Timeline",
        "start_date": start_date.isoformat(),
        "duration": (project_end - start_date).days,
        "progress": 0,
        "type": "project"
    })
    
    # Calculate milestones
    milestones = []
    milestone_date = start_date
    for i, epic in enumerate(decomposition.get("epics", [])):
        epic_duration = sum(
            sum(subtask.get("estimated_hours", 8) // 8 for subtask in story.get("subtasks", []))
            for story in epic.get("stories", [])
        )
        milestone_date += timedelta(days=epic_duration)
        milestones.append({
            "id": f"milestone_{i+1}",
            "text": f"{epic['title']} Complete",
            "date": milestone_date.isoformat()
        })
    
    return {
        "tasks": gantt_tasks,
        "milestones": milestones,
        "project_start": start_date.isoformat(),
        "project_end": project_end.isoformat(),
        "total_duration_days": (project_end - start_date).days,
        "team_size": team_size,
        "generated_at": datetime.now().isoformat()
    }

