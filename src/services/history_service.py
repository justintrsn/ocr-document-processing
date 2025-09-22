"""
History service for managing processing history with auto-cleanup
"""

import logging
import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import json
import threading
import schedule
import time

from src.models.history import ProcessingHistory
from src.core.config import settings

logger = logging.getLogger(__name__)


class HistoryService:
    """
    Manages processing history with SQLite backend
    - CRUD operations for history entries
    - Automatic 7-day retention with cleanup
    - Thread-safe database operations
    - Query by document_id with expiry checks
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize history service

        Args:
            db_path: Optional database path, defaults to settings.history_db_path
        """
        self.db_path = db_path or settings.history_db_path
        self.retention_days = settings.history_retention_days  # Default: 7

        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

        # Start cleanup scheduler in background
        self._start_cleanup_scheduler()

        logger.info(f"HistoryService initialized with database at {self.db_path}")

    def _init_database(self):
        """Initialize database schema"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Create history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processing_history (
                    history_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    format_detected TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    status TEXT NOT NULL,
                    text_extracted TEXT,
                    confidence REAL,
                    pages_processed INTEGER,
                    total_pages INTEGER,
                    processing_time_ms INTEGER,
                    error_message TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for efficient queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_id
                ON processing_history(document_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at
                ON processing_history(expires_at)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_processed_at
                ON processing_history(processed_at)
            """)

            # Create batch history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS batch_history (
                    batch_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    total_documents INTEGER,
                    successful_documents INTEGER,
                    failed_documents INTEGER,
                    status TEXT NOT NULL,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    results TEXT,
                    errors TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_batch_job_id
                ON batch_history(job_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_batch_expires_at
                ON batch_history(expires_at)
            """)

            conn.commit()
            logger.debug("Database schema initialized")

        finally:
            conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def add_processing_record(
        self,
        document_id: str,
        format_detected: str,
        status: str,
        text_extracted: Optional[str] = None,
        confidence: Optional[float] = None,
        pages_processed: Optional[int] = None,
        total_pages: Optional[int] = None,
        processing_time_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProcessingHistory:
        """
        Add a new processing record to history

        Args:
            document_id: Unique document identifier
            format_detected: Detected file format
            status: Processing status (success, failed, partial_success)
            text_extracted: Extracted text content
            confidence: OCR confidence score
            pages_processed: Number of pages successfully processed
            total_pages: Total pages in document
            processing_time_ms: Processing time in milliseconds
            error_message: Error message if failed
            metadata: Additional metadata

        Returns:
            ProcessingHistory object
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Create history entry with required fields
            history = ProcessingHistory(
                document_id=document_id,
                file_format=format_detected,
                format_detected=format_detected,
                file_name=metadata.get("filename", f"{document_id}.{format_detected.lower()}") if metadata else f"{document_id}.{format_detected.lower()}",
                file_size_bytes=metadata.get("file_size", 0) if metadata else 0,
                processing_time_ms=processing_time_ms or 0,
                success=(status == "success"),
                result_summary=text_extracted[:500] if text_extracted else None,
                error_message=error_message,
                pages_processed=pages_processed,
                ocr_confidence=confidence,
                processed_at=datetime.now(),
                metadata=metadata or {}
            )

            # Calculate expiry
            expires_at = history.processed_at + timedelta(days=self.retention_days)

            # Insert record
            cursor.execute("""
                INSERT INTO processing_history (
                    history_id, document_id, format_detected,
                    processed_at, expires_at, status,
                    text_extracted, confidence, pages_processed,
                    total_pages, processing_time_ms, error_message,
                    metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                history.history_id,
                document_id,
                format_detected,
                history.processed_at,
                expires_at,
                status,
                text_extracted[:10000] if text_extracted else None,  # Limit text size
                confidence,
                pages_processed,
                total_pages,
                processing_time_ms,
                error_message,
                json.dumps(metadata) if metadata else None
            ))

            conn.commit()

            # Update history object
            history.expires_at = expires_at
            # Note: status is stored in DB but not in model (uses 'success' field instead)

            logger.info(f"Added history record {history.history_id} for document {document_id}")
            return history

        except Exception as e:
            logger.error(f"Failed to add history record: {e}")
            raise
        finally:
            conn.close()

    def get_by_document_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get processing history by document ID

        Args:
            document_id: Document identifier

        Returns:
            History record or None if not found/expired
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Query with expiry check
            cursor.execute("""
                SELECT * FROM processing_history
                WHERE document_id = ? AND expires_at > datetime('now')
                ORDER BY processed_at DESC
                LIMIT 1
            """, (document_id,))

            row = cursor.fetchone()

            if not row:
                return None

            # Convert to dictionary
            result = dict(row)

            # Parse metadata if present
            if result.get("metadata"):
                try:
                    result["metadata"] = json.loads(result["metadata"])
                except json.JSONDecodeError:
                    result["metadata"] = {}

            return result

        finally:
            conn.close()

    def get_by_history_id(self, history_id: str) -> Optional[Dict[str, Any]]:
        """
        Get processing history by history ID

        Args:
            history_id: History record identifier

        Returns:
            History record or None if not found/expired
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM processing_history
                WHERE history_id = ? AND expires_at > datetime('now')
            """, (history_id,))

            row = cursor.fetchone()

            if not row:
                return None

            result = dict(row)

            # Parse metadata
            if result.get("metadata"):
                try:
                    result["metadata"] = json.loads(result["metadata"])
                except json.JSONDecodeError:
                    result["metadata"] = {}

            return result

        finally:
            conn.close()

    def get_recent_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent processing history

        Args:
            limit: Maximum number of records to return

        Returns:
            List of history records
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT history_id, document_id, format_detected,
                       processed_at, status, confidence,
                       pages_processed, total_pages, processing_time_ms
                FROM processing_history
                WHERE expires_at > datetime('now')
                ORDER BY processed_at DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        finally:
            conn.close()

    def add_batch_record(
        self,
        job_id: str,
        total_documents: int,
        successful_documents: int,
        failed_documents: int,
        status: str,
        started_at: datetime,
        completed_at: Optional[datetime] = None,
        results: Optional[Dict[str, Any]] = None,
        errors: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add batch processing record

        Args:
            job_id: Batch job identifier
            total_documents: Total documents in batch
            successful_documents: Number of successful documents
            failed_documents: Number of failed documents
            status: Batch status
            started_at: Processing start time
            completed_at: Processing completion time
            results: Processing results
            errors: Processing errors

        Returns:
            Batch history ID
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            batch_id = f"batch_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{job_id}"
            expires_at = datetime.now() + timedelta(days=self.retention_days)

            cursor.execute("""
                INSERT INTO batch_history (
                    batch_id, job_id, total_documents,
                    successful_documents, failed_documents, status,
                    started_at, completed_at, expires_at,
                    results, errors
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                batch_id,
                job_id,
                total_documents,
                successful_documents,
                failed_documents,
                status,
                started_at,
                completed_at,
                expires_at,
                json.dumps(results) if results else None,
                json.dumps(errors) if errors else None
            ))

            conn.commit()
            logger.info(f"Added batch history record {batch_id}")
            return batch_id

        except Exception as e:
            logger.error(f"Failed to add batch history: {e}")
            raise
        finally:
            conn.close()

    def get_batch_history(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get batch processing history

        Args:
            job_id: Batch job identifier

        Returns:
            Batch history record or None
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM batch_history
                WHERE job_id = ? AND expires_at > datetime('now')
                ORDER BY created_at DESC
                LIMIT 1
            """, (job_id,))

            row = cursor.fetchone()

            if not row:
                return None

            result = dict(row)

            # Parse JSON fields
            for field in ["results", "errors"]:
                if result.get(field):
                    try:
                        result[field] = json.loads(result[field])
                    except json.JSONDecodeError:
                        result[field] = {}

            return result

        finally:
            conn.close()

    def cleanup_expired_records(self) -> int:
        """
        Remove expired records from database

        Returns:
            Number of records deleted
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Delete expired processing history
            cursor.execute("""
                DELETE FROM processing_history
                WHERE expires_at <= datetime('now')
            """)

            processing_deleted = cursor.rowcount

            # Delete expired batch history
            cursor.execute("""
                DELETE FROM batch_history
                WHERE expires_at <= datetime('now')
            """)

            batch_deleted = cursor.rowcount

            conn.commit()

            total_deleted = processing_deleted + batch_deleted

            if total_deleted > 0:
                logger.info(f"Cleaned up {total_deleted} expired records "
                          f"({processing_deleted} processing, {batch_deleted} batch)")

            return total_deleted

        except Exception as e:
            logger.error(f"Failed to cleanup expired records: {e}")
            return 0
        finally:
            conn.close()

    def _start_cleanup_scheduler(self):
        """Start background thread for periodic cleanup"""
        def run_scheduler():
            # Schedule daily cleanup at 2 AM
            schedule.every().day.at("02:00").do(self.cleanup_expired_records)

            # Also run cleanup on startup
            self.cleanup_expired_records()

            while True:
                schedule.run_pending()
                time.sleep(3600)  # Check every hour

        # Start scheduler in background thread
        cleanup_thread = threading.Thread(target=run_scheduler, daemon=True)
        cleanup_thread.start()
        logger.info("Started background cleanup scheduler")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics

        Returns:
            Statistics about stored records
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Total records
            cursor.execute("SELECT COUNT(*) as total FROM processing_history")
            total_records = cursor.fetchone()["total"]

            # Active records
            cursor.execute("""
                SELECT COUNT(*) as active FROM processing_history
                WHERE expires_at > datetime('now')
            """)
            active_records = cursor.fetchone()["active"]

            # Records by status
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM processing_history
                WHERE expires_at > datetime('now')
                GROUP BY status
            """)
            status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

            # Records by format
            cursor.execute("""
                SELECT format_detected, COUNT(*) as count
                FROM processing_history
                WHERE expires_at > datetime('now')
                GROUP BY format_detected
            """)
            format_counts = {row["format_detected"]: row["count"] for row in cursor.fetchall()}

            # Average processing time
            cursor.execute("""
                SELECT AVG(processing_time_ms) as avg_time
                FROM processing_history
                WHERE expires_at > datetime('now') AND processing_time_ms IS NOT NULL
            """)
            avg_processing_time = cursor.fetchone()["avg_time"]

            # Batch statistics
            cursor.execute("SELECT COUNT(*) as total FROM batch_history")
            total_batches = cursor.fetchone()["total"]

            cursor.execute("""
                SELECT COUNT(*) as active FROM batch_history
                WHERE expires_at > datetime('now')
            """)
            active_batches = cursor.fetchone()["active"]

            return {
                "total_records": total_records,
                "active_records": active_records,
                "expired_records": total_records - active_records,
                "status_distribution": status_counts,
                "format_distribution": format_counts,
                "average_processing_time_ms": avg_processing_time,
                "total_batches": total_batches,
                "active_batches": active_batches,
                "retention_days": self.retention_days
            }

        finally:
            conn.close()

    def search_history(
        self,
        format_type: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search processing history with filters

        Args:
            format_type: Filter by format
            status: Filter by status
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum results

        Returns:
            List of matching history records
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Build query
            query = """
                SELECT * FROM processing_history
                WHERE expires_at > datetime('now')
            """
            params = []

            if format_type:
                query += " AND format_detected = ?"
                params.append(format_type)

            if status:
                query += " AND status = ?"
                params.append(status)

            if start_date:
                query += " AND processed_at >= ?"
                params.append(start_date)

            if end_date:
                query += " AND processed_at <= ?"
                params.append(end_date)

            query += " ORDER BY processed_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            results = []
            for row in rows:
                record = dict(row)
                if record.get("metadata"):
                    try:
                        record["metadata"] = json.loads(record["metadata"])
                    except json.JSONDecodeError:
                        record["metadata"] = {}
                results.append(record)

            return results

        finally:
            conn.close()

    def close(self):
        """Close the service and cleanup resources"""
        # Scheduler will stop when daemon thread exits
        logger.info("HistoryService closed")