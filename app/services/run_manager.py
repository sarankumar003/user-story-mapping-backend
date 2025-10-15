"""
Run Manager Service
Manages document processing runs and maintains history
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from app.core.config import settings
from app.models.document import BRDDocument, DocumentStatus
from app.models.requirement import RequirementsDecomposition
from app.models.jira_mapping import JiraSyncResult


class RunManager:
    """Manages document processing runs"""
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path or settings.STORAGE_BASE_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.runs_file = self.base_path / "runs.json"
        self._load_runs()
    
    def _load_runs(self):
        """Load runs from storage"""
        if self.runs_file.exists():
            with open(self.runs_file, 'r', encoding='utf-8') as f:
                self.runs = json.load(f)
        else:
            self.runs = []
    
    def _save_runs(self):
        """Save runs to storage"""
        with open(self.runs_file, 'w', encoding='utf-8') as f:
            json.dump(self.runs, f, indent=2, ensure_ascii=False)
    
    def create_run(self, file_name: str, file_path: str, file_size: int) -> str:
        """Create a new processing run"""
        run_id = str(uuid.uuid4())
        run_data = {
            "id": run_id,
            "file_name": file_name,
            "file_path": file_path,
            "file_size": file_size,
            "created_at": datetime.now().isoformat(),
            "status": DocumentStatus.UPLOADED.value,
            "steps": {
                "upload": {"status": "completed", "timestamp": datetime.now().isoformat()},
                "summary": {"status": "pending", "timestamp": None},
                "decomposition": {"status": "pending", "timestamp": None},
                "gantt": {"status": "pending", "timestamp": None},
                "jira_sync": {"status": "pending", "timestamp": None}
            }
        }
        
        # Create run directory
        run_dir = self.base_path / run_id
        run_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        (run_dir / "input").mkdir(exist_ok=True)
        (run_dir / "intermediate").mkdir(exist_ok=True)
        (run_dir / "output").mkdir(exist_ok=True)
        
        self.runs.append(run_data)
        self._save_runs()
        
        return run_id
    
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get run by ID"""
        # Reload from disk to reflect runs created by other service instances
        self._load_runs()
        for run in self.runs:
            if run["id"] == run_id:
                return run
        return None
    
    def get_all_runs(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get all runs, optionally limited"""
        # Reload to ensure latest state
        self._load_runs()
        runs = sorted(self.runs, key=lambda x: x["created_at"], reverse=True)
        if limit:
            runs = runs[:limit]
        return runs
    
    def update_run_status(self, run_id: str, status: DocumentStatus, step: str = None):
        """Update run status"""
        # Reload to get latest before mutating
        self._load_runs()
        for run in self.runs:
            if run["id"] == run_id:
                run["status"] = status.value
                if step:
                    run["steps"][step]["status"] = "completed"
                    run["steps"][step]["timestamp"] = datetime.now().isoformat()
                self._save_runs()
                break
    
    def update_run_step(self, run_id: str, step: str, status: str, data: Dict[str, Any] = None):
        """Update specific step in run"""
        # Reload to get latest before mutating
        self._load_runs()
        for run in self.runs:
            if run["id"] == run_id:
                run["steps"][step]["status"] = status
                run["steps"][step]["timestamp"] = datetime.now().isoformat()
                if data:
                    run["steps"][step]["data"] = data
                self._save_runs()
                break
    
    def save_document_summary(self, run_id: str, summary: Dict[str, Any]):
        """Save document summary for a run"""
        run_dir = self.base_path / run_id / "intermediate"
        summary_file = run_dir / "summary.json"
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
    
    def load_document_summary(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Load document summary for a run"""
        run_dir = self.base_path / run_id / "intermediate"
        summary_file = run_dir / "summary.json"
        
        if summary_file.exists():
            with open(summary_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def save_requirements_decomposition(self, run_id: str, decomposition: Dict[str, Any]):
        """Save requirements decomposition for a run"""
        run_dir = self.base_path / run_id / "intermediate"
        decomposition_file = run_dir / "decomposition.json"
        
        with open(decomposition_file, 'w', encoding='utf-8') as f:
            json.dump(decomposition, f, indent=2, ensure_ascii=False)
    
    def load_requirements_decomposition(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Load requirements decomposition for a run"""
        run_dir = self.base_path / run_id / "intermediate"
        decomposition_file = run_dir / "decomposition.json"
        
        if decomposition_file.exists():
            with open(decomposition_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def save_intermediate(self, run_id: str, filename: str, data: Dict[str, Any]):
        """Save any intermediate JSON under the run's intermediate folder"""
        run_dir = self.base_path / run_id / "intermediate"
        run_dir.mkdir(parents=True, exist_ok=True)
        target = run_dir / filename
        with open(target, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load_intermediate(self, run_id: str, filename: str) -> Optional[Dict[str, Any]]:
        """Load an intermediate JSON file from the run's intermediate folder"""
        run_dir = self.base_path / run_id / "intermediate"
        target = run_dir / filename
        if target.exists():
            with open(target, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def load_or_create_users_cache(self) -> list:
        """Load users cache from users_cache.json; return [] if missing."""
        try:
            backend_root = Path(__file__).resolve().parents[2]
            path = backend_root / "users_cache.json"
            if not path.exists():
                return []
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def save_users_cache(self, users: list) -> bool:
        """Persist users cache to users_cache.json."""
        try:
            backend_root = Path(__file__).resolve().parents[2]
            path = backend_root / "users_cache.json"
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    def save_gantt_data(self, run_id: str, gantt_data: Dict[str, Any]):
        """Save Gantt chart data for a run"""
        run_dir = self.base_path / run_id / "output"
        gantt_file = run_dir / "gantt.json"
        
        with open(gantt_file, 'w', encoding='utf-8') as f:
            json.dump(gantt_data, f, indent=2, default=str)
    
    def load_gantt_data(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Load Gantt chart data for a run"""
        run_dir = self.base_path / run_id / "output"
        gantt_file = run_dir / "gantt.json"
        
        if gantt_file.exists():
            with open(gantt_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def save_jira_sync_result(self, run_id: str, sync_result: Dict[str, Any]):
        """Save Jira sync result for a run"""
        run_dir = self.base_path / run_id / "output"
        jira_file = run_dir / "jira_sync.json"
        
        with open(jira_file, 'w', encoding='utf-8') as f:
            json.dump(sync_result, f, indent=2, default=str)
    
    def load_jira_sync_result(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Load Jira sync result for a run"""
        run_dir = self.base_path / run_id / "output"
        jira_file = run_dir / "jira_sync.json"
        
        if jira_file.exists():
            with open(jira_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def cleanup_old_runs(self, max_runs: int = None):
        """Clean up old runs to maintain storage limits"""
        max_runs = max_runs or settings.MAX_RUN_HISTORY
        
        if len(self.runs) > max_runs:
            # Sort by creation date and keep only the most recent
            self.runs = sorted(self.runs, key=lambda x: x["created_at"], reverse=True)[:max_runs]
            self._save_runs()
