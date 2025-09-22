"""
Initialize and manage SQLite database for processing history
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from contextlib import contextmanager

from src.core.config import settings

logger = logging.getLogger(__name__)


class HistoryDatabase:
    """Manage SQLite database for processing history"""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection"""
        self.db_path = db_path or settings.history_db_path
        self.init_database()

        # Run cleanup on startup if configured
        if settings.history_cleanup_on_startup:
            self.cleanup_expired_records()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(
            str(self.db_path),
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def init_database(self):
        """Initialize database with schema"""
        schema_file = Path(__file__).parent / "history_schema.sql"

        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # If schema file exists, use it
            if schema_file.exists():
                with open(schema_file, 'r') as f:
                    schema_sql = f.read()
                cursor.executescript(schema_sql)
            else:
                # Fallback: create schema directly
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS processing_history (
                        history_id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL,
                        user_id TEXT,
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        file_format TEXT NOT NULL,
                        file_name TEXT NOT NULL,
                        file_size_bytes INTEGER NOT NULL,
                        processing_time_ms REAL NOT NULL,
                        success BOOLEAN NOT NULL,
                        error_code TEXT,
                        result_summary TEXT,
                        expires_at TIMESTAMP NOT NULL
                    )
                """)

                # Create indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_id ON processing_history(document_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_processed_at ON processing_history(processed_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_expires_at ON processing_history(expires_at)")

                # Create cleanup trigger
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS cleanup_expired_records
                    AFTER INSERT ON processing_history
                    BEGIN
                        DELETE FROM processing_history
                        WHERE expires_at < datetime('now');
                    END
                """)

            logger.info(f"Database initialized at {self.db_path}")

    def cleanup_expired_records(self) -> int:
        """
        Remove expired records from the database
        Returns the number of records deleted
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Count records to be deleted
            cursor.execute("SELECT COUNT(*) FROM processing_history WHERE expires_at < datetime('now')")
            count = cursor.fetchone()[0]

            # Delete expired records
            cursor.execute("DELETE FROM processing_history WHERE expires_at < datetime('now')")

            if count > 0:
                logger.info(f"Cleaned up {count} expired history records")

            return count

    def add_history(
        self,
        history_id: str,
        document_id: str,
        file_format: str,
        file_name: str,
        file_size_bytes: int,
        processing_time_ms: float,
        success: bool,
        error_code: Optional[str] = None,
        result_summary: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Add a new processing history record
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Calculate expiry date (7 days from now)
                expires_at = datetime.now() + timedelta(days=settings.history_retention_days)

                cursor.execute("""
                    INSERT INTO processing_history (
                        history_id, document_id, user_id, file_format,
                        file_name, file_size_bytes, processing_time_ms,
                        success, error_code, result_summary, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    history_id, document_id, user_id, file_format,
                    file_name, file_size_bytes, processing_time_ms,
                    success, error_code, result_summary, expires_at
                ))

                logger.debug(f"Added history record for document {document_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to add history record: {e}")
            return False

    def get_history_by_document_id(self, document_id: str) -> Optional[dict]:
        """
        Retrieve history for a specific document
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM processing_history
                WHERE document_id = ? AND expires_at > datetime('now')
                ORDER BY processed_at DESC
                LIMIT 1
            """, (document_id,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_recent_history(self, limit: int = 100) -> list[dict]:
        """
        Get recent processing history
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM processing_history
                WHERE expires_at > datetime('now')
                ORDER BY processed_at DESC
                LIMIT ?
            """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self) -> dict:
        """
        Get processing statistics from history
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total records
            cursor.execute("SELECT COUNT(*) FROM processing_history WHERE expires_at > datetime('now')")
            total = cursor.fetchone()[0]

            # Success rate
            cursor.execute("""
                SELECT
                    COUNT(CASE WHEN success = 1 THEN 1 END) as successful,
                    COUNT(*) as total
                FROM processing_history
                WHERE expires_at > datetime('now')
            """)
            row = cursor.fetchone()
            success_rate = (row[0] / row[1] * 100) if row[1] > 0 else 0

            # Format distribution
            cursor.execute("""
                SELECT file_format, COUNT(*) as count
                FROM processing_history
                WHERE expires_at > datetime('now')
                GROUP BY file_format
                ORDER BY count DESC
            """)
            format_distribution = {row[0]: row[1] for row in cursor.fetchall()}

            # Average processing time
            cursor.execute("""
                SELECT AVG(processing_time_ms)
                FROM processing_history
                WHERE expires_at > datetime('now') AND success = 1
            """)
            avg_time = cursor.fetchone()[0] or 0

            return {
                "total_records": total,
                "success_rate": round(success_rate, 2),
                "format_distribution": format_distribution,
                "average_processing_time_ms": round(avg_time, 2)
            }


# Initialize singleton database instance
history_db = None

def get_history_db() -> HistoryDatabase:
    """Get singleton database instance"""
    global history_db
    if history_db is None:
        history_db = HistoryDatabase()
    return history_db


if __name__ == "__main__":
    # Test database initialization
    logging.basicConfig(level=logging.INFO)

    db = HistoryDatabase()
    print("✓ Database initialized successfully")

    # Test adding a record
    import uuid
    test_id = str(uuid.uuid4())
    success = db.add_history(
        history_id=test_id,
        document_id="test_doc_001",
        file_format="PDF",
        file_name="test.pdf",
        file_size_bytes=1024000,
        processing_time_ms=1500.5,
        success=True,
        result_summary='{"pages": 5, "words": 500}'
    )

    if success:
        print("✓ Test record added successfully")

        # Retrieve the record
        history = db.get_history_by_document_id("test_doc_001")
        if history:
            print(f"✓ Retrieved history: {history['file_name']} processed at {history['processed_at']}")

        # Get statistics
        stats = db.get_statistics()
        print(f"✓ Statistics: {stats}")

        # Cleanup test
        cleaned = db.cleanup_expired_records()
        print(f"✓ Cleanup complete: {cleaned} expired records removed")