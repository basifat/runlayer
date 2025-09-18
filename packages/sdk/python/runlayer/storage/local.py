"""
Local ProofLake Storage

SQLite-based local storage for validation proofs with:
- Fast local queries and caching
- Automatic schema migration
- Efficient indexing for lookups
- Optional encryption at rest
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from ..models.proof import RunProof, ProofStatus
from ..utils.logging import get_logger, PerformanceLogger

logger = get_logger(__name__)


class LocalProofLake:
    """
    Local SQLite-based storage for validation proofs.
    
    Provides fast local storage and querying of RunProofs with
    automatic schema management and efficient indexing.
    """
    
    SCHEMA_VERSION = 1
    
    def __init__(self, db_path: Path, encrypt: bool = False):
        """
        Initialize LocalProofLake.
        
        Args:
            db_path: Path to SQLite database file
            encrypt: Whether to encrypt the database (future feature)
        """
        self.db_path = db_path
        self.encrypt = encrypt
        
        # Ensure directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        logger.info("LocalProofLake initialized", db_path=str(db_path))
    
    def _init_database(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            # Create proofs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS proofs (
                    id TEXT PRIMARY KEY,
                    validator_name TEXT NOT NULL,
                    validator_version TEXT NOT NULL,
                    input_hash TEXT NOT NULL,
                    output_hash TEXT NOT NULL,
                    input_data TEXT NOT NULL,
                    output_data TEXT NOT NULL,
                    execution_time_ms INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    signature TEXT,
                    synced_to_cloud BOOLEAN DEFAULT FALSE,
                    sync_timestamp TEXT,
                    metadata TEXT
                )
            """)
            
            # Create indexes for efficient queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_proofs_validator 
                ON proofs(validator_name, validator_version)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_proofs_workspace 
                ON proofs(workspace_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_proofs_sync 
                ON proofs(synced_to_cloud, workspace_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_proofs_created 
                ON proofs(created_at)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_proofs_input_hash 
                ON proofs(input_hash)
            """)
            
            # Create metadata table for schema versioning
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            
            # Set schema version
            conn.execute("""
                INSERT OR REPLACE INTO metadata (key, value) 
                VALUES ('schema_version', ?)
            """, (str(self.SCHEMA_VERSION),))
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling."""
        conn = None
        try:
            conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,  # 30 second timeout
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row  # Enable column access by name
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error("Database error", error=str(e), db_path=str(self.db_path))
            raise
        finally:
            if conn:
                conn.close()
    
    def store_proof(self, proof: RunProof) -> bool:
        """
        Store a proof in the local database.
        
        Args:
            proof: RunProof to store
            
        Returns:
            True if stored successfully
        """
        with PerformanceLogger(logger, "store_proof"):
            try:
                with self._get_connection() as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO proofs (
                            id, validator_name, validator_version,
                            input_hash, output_hash, input_data, output_data,
                            execution_time_ms, status, created_at, workspace_id,
                            signature, synced_to_cloud, sync_timestamp, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        proof.id,
                        proof.validator_name,
                        proof.validator_version,
                        proof.input_hash,
                        proof.output_hash,
                        json.dumps(proof.input_data),
                        json.dumps(proof.output_data),
                        proof.execution_time_ms,
                        proof.status.value,
                        proof.created_at.isoformat(),
                        proof.workspace_id,
                        proof.signature,
                        proof.synced_to_cloud,
                        proof.sync_timestamp.isoformat() if proof.sync_timestamp else None,
                        json.dumps(proof.metadata)
                    ))
                    conn.commit()
                
                logger.debug("Proof stored", proof_id=proof.id)
                return True
                
            except Exception as e:
                logger.error("Failed to store proof", proof_id=proof.id, error=str(e))
                return False
    
    def get_proof(self, proof_id: str) -> Optional[RunProof]:
        """
        Get a proof by ID.
        
        Args:
            proof_id: Proof identifier
            
        Returns:
            RunProof if found, None otherwise
        """
        with PerformanceLogger(logger, "get_proof"):
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT * FROM proofs WHERE id = ?
                    """, (proof_id,))
                    
                    row = cursor.fetchone()
                    if row:
                        return self._row_to_proof(row)
                    
                return None
                
            except Exception as e:
                logger.error("Failed to get proof", proof_id=proof_id, error=str(e))
                return None
    
    def find_proof_by_input_hash(self, validator_name: str, validator_version: str, input_hash: str) -> Optional[RunProof]:
        """
        Find existing proof for the same input.
        
        Args:
            validator_name: Name of the validator
            validator_version: Version of the validator
            input_hash: Hash of the input data
            
        Returns:
            Existing RunProof if found, None otherwise
        """
        with PerformanceLogger(logger, "find_proof_by_input_hash"):
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT * FROM proofs 
                        WHERE validator_name = ? AND validator_version = ? AND input_hash = ?
                        ORDER BY created_at DESC
                        LIMIT 1
                    """, (validator_name, validator_version, input_hash))
                    
                    row = cursor.fetchone()
                    if row:
                        return self._row_to_proof(row)
                    
                return None
                
            except Exception as e:
                logger.error("Failed to find proof by input hash", error=str(e))
                return None
    
    def list_proofs(
        self,
        workspace_id: Optional[str] = None,
        validator_name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[RunProof]:
        """
        List proofs with optional filtering.
        
        Args:
            workspace_id: Filter by workspace
            validator_name: Filter by validator name
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of RunProofs
        """
        with PerformanceLogger(logger, "list_proofs"):
            try:
                with self._get_connection() as conn:
                    query = "SELECT * FROM proofs WHERE 1=1"
                    params = []
                    
                    if workspace_id:
                        query += " AND workspace_id = ?"
                        params.append(workspace_id)
                    
                    if validator_name:
                        query += " AND validator_name = ?"
                        params.append(validator_name)
                    
                    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
                    params.extend([limit, offset])
                    
                    cursor = conn.execute(query, params)
                    rows = cursor.fetchall()
                    
                    return [self._row_to_proof(row) for row in rows]
                
            except Exception as e:
                logger.error("Failed to list proofs", error=str(e))
                return []
    
    def get_unsynced_proofs(self, workspace_id: str, limit: int = 50) -> List[RunProof]:
        """
        Get proofs that haven't been synced to cloud.
        
        Args:
            workspace_id: Workspace identifier
            limit: Maximum number of results
            
        Returns:
            List of unsynced RunProofs
        """
        with PerformanceLogger(logger, "get_unsynced_proofs"):
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT * FROM proofs 
                        WHERE workspace_id = ? AND synced_to_cloud = FALSE
                        ORDER BY created_at ASC
                        LIMIT ?
                    """, (workspace_id, limit))
                    
                    rows = cursor.fetchall()
                    return [self._row_to_proof(row) for row in rows]
                
            except Exception as e:
                logger.error("Failed to get unsynced proofs", error=str(e))
                return []
    
    def mark_proof_synced(self, proof_id: str) -> bool:
        """
        Mark a proof as synced to cloud.
        
        Args:
            proof_id: Proof identifier
            
        Returns:
            True if updated successfully
        """
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE proofs 
                    SET synced_to_cloud = TRUE, sync_timestamp = ?
                    WHERE id = ?
                """, (datetime.utcnow().isoformat(), proof_id))
                conn.commit()
                
                return conn.total_changes > 0
                
        except Exception as e:
            logger.error("Failed to mark proof as synced", proof_id=proof_id, error=str(e))
            return False
    
    def get_stats(self, workspace_id: str) -> Dict[str, Any]:
        """
        Get storage statistics for a workspace.
        
        Args:
            workspace_id: Workspace identifier
            
        Returns:
            Dictionary with statistics
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_proofs,
                        COUNT(CASE WHEN synced_to_cloud = TRUE THEN 1 END) as synced_proofs,
                        COUNT(DISTINCT validator_name) as unique_validators,
                        MIN(created_at) as oldest_proof,
                        MAX(created_at) as newest_proof
                    FROM proofs 
                    WHERE workspace_id = ?
                """, (workspace_id,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        "total_proofs": row["total_proofs"],
                        "synced_proofs": row["synced_proofs"],
                        "pending_sync": row["total_proofs"] - row["synced_proofs"],
                        "unique_validators": row["unique_validators"],
                        "oldest_proof": row["oldest_proof"],
                        "newest_proof": row["newest_proof"],
                        "storage_size_mb": self._get_db_size_mb()
                    }
                
                return {}
                
        except Exception as e:
            logger.error("Failed to get stats", error=str(e))
            return {}
    
    def cleanup_old_proofs(self, workspace_id: str, days: int = 30) -> int:
        """
        Clean up proofs older than specified days.
        
        Args:
            workspace_id: Workspace identifier
            days: Number of days to keep proofs
            
        Returns:
            Number of proofs deleted
        """
        try:
            cutoff_date = datetime.utcnow().replace(microsecond=0)
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)
            
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    DELETE FROM proofs 
                    WHERE workspace_id = ? AND created_at < ? AND synced_to_cloud = TRUE
                """, (workspace_id, cutoff_date.isoformat()))
                conn.commit()
                
                deleted_count = cursor.rowcount
                logger.info("Cleaned up old proofs", 
                           workspace_id=workspace_id, 
                           deleted_count=deleted_count,
                           cutoff_days=days)
                
                return deleted_count
                
        except Exception as e:
            logger.error("Failed to cleanup old proofs", error=str(e))
            return 0
    
    def _row_to_proof(self, row: sqlite3.Row) -> RunProof:
        """Convert database row to RunProof object."""
        return RunProof(
            id=row["id"],
            validator_name=row["validator_name"],
            validator_version=row["validator_version"],
            input_hash=row["input_hash"],
            output_hash=row["output_hash"],
            input_data=json.loads(row["input_data"]),
            output_data=json.loads(row["output_data"]),
            execution_time_ms=row["execution_time_ms"],
            status=ProofStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            workspace_id=row["workspace_id"],
            signature=row["signature"],
            synced_to_cloud=bool(row["synced_to_cloud"]),
            sync_timestamp=datetime.fromisoformat(row["sync_timestamp"]) if row["sync_timestamp"] else None,
            metadata=json.loads(row["metadata"]) if row["metadata"] else {}
        )
    
    def _get_db_size_mb(self) -> float:
        """Get database file size in MB."""
        try:
            size_bytes = self.db_path.stat().st_size
            return round(size_bytes / (1024 * 1024), 2)
        except Exception:
            return 0.0
