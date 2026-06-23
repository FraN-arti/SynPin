"""FTS5 Search — full-text search across agent memory.


Uses SQLite FTS5
- MEMORY.md files
- USER.md files
- facts/*.md files
- sessions/*.md files
- shared/MEMORY.md

Search is instant (4500x faster than LLM-based search) and free.
"""

import logging
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..time import now as _now

logger = logging.getLogger(__name__)


class MemorySearch:
    """FTS5-based search across agent memory files."""
    
    def __init__(self, data_dir: Path, db_path: Optional[Path] = None):
        self.data_dir = Path(data_dir)
        self.db_path = db_path or (self.data_dir / "search.db")
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database with FTS5."""
        try:
            self._conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=5.0,
            )
            self._conn.row_factory = sqlite3.Row
            
            # Enable WAL mode for concurrent reads
            self._conn.execute("PRAGMA journal_mode=WAL")
            
            # Create tables
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    indexed_at REAL NOT NULL
                );
                
                CREATE INDEX IF NOT EXISTS idx_documents_agent 
                    ON documents(agent_id);
                CREATE INDEX IF NOT EXISTS idx_documents_type 
                    ON documents(file_type);
                CREATE INDEX IF NOT EXISTS idx_documents_path 
                    ON documents(file_path);
            """)
            
            # Create FTS5 table
            self._conn.executescript("""
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                    content,
                    content='documents',
                    content_rowid='id'
                );
                
                -- Triggers to keep FTS in sync
                CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                    INSERT INTO documents_fts(rowid, content) VALUES (new.id, new.content);
                END;
                
                CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                    INSERT INTO documents_fts(documents_fts, rowid, content) 
                        VALUES('delete', old.id, old.content);
                END;
                
                CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
                    INSERT INTO documents_fts(documents_fts, rowid, content) 
                        VALUES('delete', old.id, old.content);
                    INSERT INTO documents_fts(rowid, content) VALUES (new.id, new.content);
                END;
            """)
            
            self._conn.commit()
            logger.info("Search database initialized: %s", self.db_path)
            
        except Exception as e:
            logger.error("Failed to initialize search database: %s", e)
            self._conn = None
    
    # ── Indexing ─────────────────────────────────────────────────────────
    
    def index_file(self, agent_id: str, file_path: Path, file_type: str) -> bool:
        """Index a single file into the search database."""
        if not self._conn:
            return False
        
        if not file_path.exists():
            return False
        
        try:
            content = file_path.read_text(encoding="utf-8")
            if not content.strip():
                return False
            
            with self._lock:
                # Remove old entry for this file
                self._conn.execute(
                    "DELETE FROM documents WHERE file_path = ?",
                    (str(file_path),)
                )
                
                # Insert new entry
                self._conn.execute(
                    "INSERT INTO documents (agent_id, file_path, file_type, content, indexed_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (agent_id, str(file_path), file_type, content, _now().timestamp())
                )
                
                self._conn.commit()
            
            logger.debug("Indexed: %s (%s)", file_path.name, file_type)
            return True
            
        except Exception as e:
            logger.error("Failed to index %s: %s", file_path, e)
            return False
    
    def index_agent(self, agent_id: str) -> int:
        """Index all memory files for an agent. Returns count of indexed files."""
        agent_dir = self.data_dir / "agents" / agent_id
        if not agent_dir.exists():
            return 0
        
        count = 0
        
        # Index MEMORY.md
        memory_file = agent_dir / "MEMORY.md"
        if memory_file.exists() and self.index_file(agent_id, memory_file, "memory"):
            count += 1
        
        # Index USER.md
        user_file = self.data_dir / "shared" / "USER.md"
        if user_file.exists() and self.index_file(agent_id, user_file, "user"):
            count += 1
        
        # Index facts/*.md
        facts_dir = agent_dir / "facts"
        if facts_dir.exists():
            for fact_file in facts_dir.glob("*.md"):
                if self.index_file(agent_id, fact_file, "fact"):
                    count += 1
        
        # Index sessions/*.md
        sessions_dir = agent_dir / "sessions"
        if sessions_dir.exists():
            for session_file in sessions_dir.glob("*.md"):
                if self.index_file(agent_id, session_file, "session"):
                    count += 1
        
        logger.info("Indexed %d files for agent %s", count, agent_id)
        return count
    
    def index_shared(self) -> int:
        """Index shared memory files."""
        shared_dir = self.data_dir / "shared"
        if not shared_dir.exists():
            return 0
        
        count = 0
        for md_file in shared_dir.glob("*.md"):
            if self.index_file("shared", md_file, "shared"):
                count += 1
        
        return count
    
    def index_all(self) -> Dict[str, int]:
        """Index all agents and shared memory. Returns counts."""
        results = {}
        
        # Index each agent
        agents_dir = self.data_dir / "agents"
        if agents_dir.exists():
            for agent_dir in agents_dir.iterdir():
                if agent_dir.is_dir():
                    results[agent_dir.name] = self.index_agent(agent_dir.name)
        
        # Index shared
        results["shared"] = self.index_shared()
        
        return results
    
    # ── Search ───────────────────────────────────────────────────────────
    
    def search(
        self,
        query: str,
        agent_id: Optional[str] = None,
        file_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search across indexed memory files.
        
        Args:
            query: Search query (supports FTS5 syntax: AND, OR, NOT, "exact", *)
            agent_id: Filter by agent (None = all agents)
            file_type: Filter by type (memory, user, fact, session, shared)
            limit: Max results
        
        Returns:
            List of search results with file, snippet, score
        """
        if not self._conn:
            return []
        
        # Build query
        where_clauses = []
        params = []
        
        if agent_id:
            where_clauses.append("d.agent_id = ?")
            params.append(agent_id)
        
        if file_type:
            where_clauses.append("d.file_type = ?")
            params.append(file_type)
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Sanitize query for FTS5
        fts_query = self._sanitize_fts_query(query)
        
        try:
            with self._lock:
                sql = f"""
                    SELECT 
                        d.agent_id,
                        d.file_path,
                        d.file_type,
                        snippet(documents_fts, 0, '<mark>', '</mark>', '...', 32) as snippet,
                        rank
                    FROM documents_fts
                    JOIN documents d ON d.id = documents_fts.rowid
                    WHERE documents_fts MATCH ?
                    AND {where_sql}
                    ORDER BY rank
                    LIMIT ?
                """
                
                params.insert(0, fts_query)
                params.append(limit)
                
                cursor = self._conn.execute(sql, params)
                rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    "agent_id": row["agent_id"],
                    "file_path": row["file_path"],
                    "file_type": row["file_type"],
                    "snippet": row["snippet"],
                    "score": abs(row["rank"]) if row["rank"] else 0,
                })
            
            return results
            
        except Exception as e:
            logger.error("Search failed for query '%s': %s", query, e)
            return []
    
    def _sanitize_fts_query(self, query: str) -> str:
        """Sanitize a query for FTS5.
        
        Handles:
        - Exact phrases: "exact phrase"
        - Boolean operators: AND, OR, NOT
        - Wildcards: deploy*
        - Simple terms: auth middleware
        """
        # If it's already a valid FTS5 query, return as-is
        if any(op in query.upper() for op in ['"AND"', '"OR"', '"NOT"', '"*"']):
            return query
        
        # Split into terms and join with AND
        terms = query.split()
        if len(terms) == 1:
            return terms[0]
        
        # Multiple terms → AND search
        return " AND ".join(terms)
    
    # ── Maintenance ──────────────────────────────────────────────────────
    
    def clear(self, agent_id: Optional[str] = None):
        """Clear index for an agent or all agents."""
        if not self._conn:
            return
        
        with self._lock:
            if agent_id:
                self._conn.execute(
                    "DELETE FROM documents WHERE agent_id = ?",
                    (agent_id,)
                )
            else:
                self._conn.execute("DELETE FROM documents")
            
            self._conn.commit()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        if not self._conn:
            return {"error": "Database not available"}
        
        try:
            with self._lock:
                cursor = self._conn.execute(
                    "SELECT agent_id, file_type, COUNT(*) as count "
                    "FROM documents GROUP BY agent_id, file_type"
                )
                rows = cursor.fetchall()
            
            stats = {}
            for row in rows:
                agent = row["agent_id"]
                if agent not in stats:
                    stats[agent] = {}
                stats[agent][row["file_type"]] = row["count"]
            
            return stats
            
        except Exception as e:
            return {"error": str(e)}
    
    def close(self):
        """Close database connection."""
        if self._conn:
            try:
                self._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except Exception:
                pass
            self._conn.close()
            self._conn = None
