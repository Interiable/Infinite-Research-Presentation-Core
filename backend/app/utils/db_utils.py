import sqlite3
import os
import json
from datetime import datetime

# Resolve absolute path to data directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECTS_DIR = os.path.join(BASE_DIR, "data", "projects")

def get_db_path(project_id: str = "default") -> str:
    """Returns the path to the research vault db for a given project."""
    if not project_id:
        project_id = "default"
    project_dir = os.path.join(PROJECTS_DIR, project_id)
    os.makedirs(project_dir, exist_ok=True)
    return os.path.join(project_dir, "research_vault.sqlite")

def init_vault(project_id: str = "default"):
    """Initializes the research data vault for the project."""
    db_path = get_db_path(project_id)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS web_research (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            source_url TEXT,
            title TEXT,
            snippet TEXT,
            full_content TEXT,
            file_path TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def log_web_research(query, title, url, snippet, file_path=None, full_content=None, project_id="default"):
    """Logs a piece of web research into the vault."""
    db_path = get_db_path(project_id)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO web_research (query, title, source_url, snippet, file_path, full_content)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (query, title, url, snippet, file_path, full_content))
    conn.commit()
    conn.close()

def get_recent_research(query=None, limit=10, project_id="default"):
    """Retrieves recent research for a project."""
    db_path = get_db_path(project_id)
    if not os.path.exists(db_path):
        return []
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        if query:
            cursor.execute("SELECT * FROM web_research WHERE query LIKE ? ORDER BY timestamp DESC LIMIT ?", (f"%{query}%", limit))
        else:
            cursor.execute("SELECT * FROM web_research ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []
    
    conn.close()
    return rows
