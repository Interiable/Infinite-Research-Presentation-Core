import json
import os
from typing import List, Dict

class ConfigManager:
    """Manages workspace/project specific folder configurations."""
    
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.config_path = os.path.join(self.base_dir, "data", "projects_config.json")
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        # Initialize default config if it doesn't exist
        if not os.path.exists(self.config_path):
            # Fallback to legacy env var if possible
            legacy_dir = os.environ.get("LOCAL_RESEARCH_DIR", "")
            legacy_dirs = [d.strip() for d in legacy_dir.split(",") if d.strip()] if legacy_dir else []
            default_config = {"default": {"folders": legacy_dirs}}
            self._save_config(default_config)
            
    def _load_config(self) -> Dict:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"default": {"folders": []}}
            
    def _save_config(self, data: Dict):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
            
    def get_project_folders(self, project_id: str) -> List[str]:
        if not project_id:
            project_id = "default"
        config = self._load_config()
        return config.get(project_id, {}).get("folders", [])
        
    def get_all_projects(self) -> List[str]:
        config = self._load_config()
        projects = {k for k in config.keys() if not k.startswith('_')}
        
        # Scan for implicitly created workspace directories (e.g. from web/media research)
        projects_dir = os.path.join(self.base_dir, "data", "projects")
        if os.path.exists(projects_dir):
            for d in os.listdir(projects_dir):
                if os.path.isdir(os.path.join(projects_dir, d)) and not d.startswith('.'):
                    projects.add(d)
                    
        return sorted(list(projects))
        
    def add_project_folder(self, project_id: str, path: str):
        if not project_id:
            project_id = "default"
        config = self._load_config()
        
        if project_id not in config:
            config[project_id] = {"folders": []}
            
        folders = config[project_id].get("folders", [])
        if path not in folders:
            folders.append(path)
            config[project_id]["folders"] = folders
            self._save_config(config)

    def get_thread_projects(self) -> Dict[str, str]:
        config = self._load_config()
        return config.get("_thread_projects", {})
        
    def set_thread_project(self, thread_id: str, project_id: str):
        if not thread_id: return
        if not project_id: project_id = "default"
        config = self._load_config()
        if "_thread_projects" not in config:
            config["_thread_projects"] = {}
        if config["_thread_projects"].get(thread_id) != project_id:
            config["_thread_projects"][thread_id] = project_id
            self._save_config(config)
