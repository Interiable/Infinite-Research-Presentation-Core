import sqlite3
import os
import json
from datetime import datetime

# Resolve absolute path to data directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "research_vault.sqlite")

def init_vault():
    """Initializes the research data vault."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
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

def log_web_research(query, title, url, snippet, file_path=None, full_content=None):
    """Logs a piece of web research into the vault."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO web_research (query, title, source_url, snippet, file_path, full_content)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (query, title, url, snippet, file_path, full_content))
    conn.commit()
    conn.close()

def get_recent_research(query=None, limit=10):
    """Retrieves recent research."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if query:
        cursor.execute("SELECT * FROM web_research WHERE query LIKE ? ORDER BY timestamp DESC LIMIT ?", (f"%{query}%", limit))
    else:
        cursor.execute("SELECT * FROM web_research ORDER BY timestamp DESC LIMIT ?", (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    return rows
