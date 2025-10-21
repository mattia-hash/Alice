"""
Local memory management using SQLite.
Stores conversation history and command execution logs.
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class Memory:
    """SQLite-based conversation and command memory."""
    
    def __init__(self, db_path: str = "data/db.sqlite"):
        """Initialize the database connection and create tables if needed."""
        self.db_path = db_path
        
        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
    
    def _create_tables(self):
        """Create the database schema if it doesn't exist."""
        cursor = self.conn.cursor()
        
        # Messages table for conversation history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Commands table for executed commands
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                cmd TEXT NOT NULL,
                args_json TEXT,
                approved BOOLEAN DEFAULT 0,
                exit_code INTEGER,
                stdout TEXT,
                stderr TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.conn.commit()
    
    def add_message(self, session_id: str, role: str, content: str) -> int:
        """Add a message to the conversation history."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def get_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict]:
        """Retrieve conversation history for a session."""
        cursor = self.conn.cursor()
        
        query = """
            SELECT role, content, created_at 
            FROM messages 
            WHERE session_id = ? 
            ORDER BY created_at DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, (session_id,))
        messages = cursor.fetchall()
        
        # Return in chronological order (oldest first)
        return [dict(msg) for msg in reversed(messages)]
    
    def add_command(self, session_id: str, cmd: str, args: List[str], 
                   approved: bool, exit_code: Optional[int] = None,
                   stdout: Optional[str] = None, stderr: Optional[str] = None) -> int:
        """Log a command execution."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO commands 
            (session_id, cmd, args_json, approved, exit_code, stdout, stderr) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, cmd, json.dumps(args), approved, exit_code, stdout, stderr)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def get_recent_commands(self, session_id: str, limit: int = 10) -> List[Dict]:
        """Get recent command history."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT cmd, args_json, approved, exit_code, created_at 
            FROM commands 
            WHERE session_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
            """,
            (session_id, limit)
        )
        
        commands = []
        for row in cursor.fetchall():
            cmd_dict = dict(row)
            cmd_dict['args'] = json.loads(cmd_dict['args_json'])
            del cmd_dict['args_json']
            commands.append(cmd_dict)
        
        return commands
    
    def close(self):
        """Close the database connection."""
        self.conn.close()

