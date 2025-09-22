-- Processing History Table Schema
-- Stores 7-day history of all document processing

CREATE TABLE IF NOT EXISTS processing_history (
    history_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    user_id TEXT,  -- For future user tracking
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_format TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    processing_time_ms REAL NOT NULL,
    success BOOLEAN NOT NULL,
    error_code TEXT,
    result_summary TEXT,  -- JSON string with summary data
    expires_at TIMESTAMP NOT NULL
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_document_id ON processing_history(document_id);
CREATE INDEX IF NOT EXISTS idx_processed_at ON processing_history(processed_at);
CREATE INDEX IF NOT EXISTS idx_expires_at ON processing_history(expires_at);

-- Cleanup trigger to automatically remove expired records
-- This trigger runs after each insert to clean up old records
CREATE TRIGGER IF NOT EXISTS cleanup_expired_records
    AFTER INSERT ON processing_history
    BEGIN
        DELETE FROM processing_history
        WHERE expires_at < datetime('now');
    END;