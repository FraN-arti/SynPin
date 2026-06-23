"""
Project config — load/save projects from YAML files.
"""
from __future__ import annotations

from pathlib import Path

from ..time import now as _now
from .models import (
    Project,
    load_project,
    load_all_projects,
    save_project,
)


class ProjectConfig:
    """Manages project storage."""
    
    def __init__(self, data_dir: Path):
        """
        Initialize project config.
        
        Args:
            data_dir: Path to data/ directory (e.g., ~/.synpin/data/)
        """
        self.projects_dir = data_dir / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
    
    def get_project_dir(self, project_id: str) -> Path:
        """Get directory for a specific project."""
        return self.projects_dir / project_id
    
    def get_archive_dir(self, project_id: str) -> Path:
        """Get archive directory for a project."""
        return self.get_project_dir(project_id) / "archive"
    
    def get_togle_path(self, project_id: str) -> Path:
        """Get TOGLE.md path for a project."""
        return self.get_project_dir(project_id) / "TOGLE.md"
    
    def load_project(self, project_id: str) -> Project | None:
        """Load a single project by ID."""
        yaml_file = self.get_project_dir(project_id) / "project.yaml"
        if not yaml_file.exists():
            return None
        try:
            return load_project(yaml_file)
        except Exception as e:
            print(f"Warning: Failed to load project {project_id}: {e}")
            return None
    
    def load_all_projects(self) -> list[Project]:
        """Load all projects."""
        return load_all_projects(self.projects_dir)
    
    def save_project(self, project: Project) -> Path:
        """Save a project to disk."""
        return save_project(project, self.projects_dir)
    
    def delete_project(self, project_id: str) -> bool:
        """Delete a project directory."""
        import shutil
        project_dir = self.get_project_dir(project_id)
        if project_dir.exists():
            shutil.rmtree(project_dir)
            return True
        return False
    
    def project_exists(self, project_id: str) -> bool:
        """Check if a project exists."""
        return (self.get_project_dir(project_id) / "project.yaml").exists()
    
    # ── TOGLE.md ────────────────────────────────────────────────────────
    
    def read_togle(self, project_id: str) -> str:
        """Read TOGLE.md content."""
        togle_path = self.get_togle_path(project_id)
        if not togle_path.exists():
            return ""
        return togle_path.read_text(encoding="utf-8")
    
    def write_togle(self, project_id: str, content: str) -> None:
        """Write TOGLE.md content."""
        togle_path = self.get_togle_path(project_id)
        togle_path.parent.mkdir(parents=True, exist_ok=True)
        togle_path.write_text(content, encoding="utf-8")
    
    def append_togle(self, project_id: str, entry: str) -> None:
        """Append entry to TOGLE.md."""
        current = self.read_togle(project_id)
        from datetime import datetime
        timestamp = _now().strftime("%Y-%m-%d %H:%M")
        new_entry = f"\n\n## [{timestamp}]\n{entry}"
        self.write_togle(project_id, current + new_entry)
