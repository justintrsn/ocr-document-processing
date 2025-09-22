"""
History retrieval endpoint for processing history with 7-day retention
"""

import logging
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.history_service import HistoryService

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize history service
history_service = HistoryService()


class HistoryResponse(BaseModel):
    """Processing history response"""
    history_id: str
    document_id: str
    format_detected: Optional[str] = None
    processed_at: str
    expires_at: str
    status: str
    text_extracted: Optional[str] = None
    confidence: Optional[float] = None
    pages_processed: Optional[int] = None
    total_pages: Optional[int] = None
    processing_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    metadata: Optional[dict] = None


class HistoryListResponse(BaseModel):
    """List of history records"""
    total_records: int
    records: List[HistoryResponse]


class HistoryStatistics(BaseModel):
    """History database statistics"""
    total_records: int
    active_records: int
    expired_records: int
    status_distribution: dict
    format_distribution: dict
    average_processing_time_ms: Optional[float] = None
    retention_days: int


@router.get("/api/v1/ocr/history/{document_id}", response_model=HistoryResponse)
async def get_document_history(document_id: str):
    """
    Get processing history for a specific document

    Retrieves the most recent processing record for the given document ID.
    Records are automatically deleted after 7 days.

    Args:
        document_id: Document identifier

    Returns:
        Processing history record

    Raises:
        404: Document not found or expired
    """
    try:
        history = history_service.get_by_document_id(document_id)

        if not history:
            raise HTTPException(
                status_code=404,
                detail=f"No history found for document {document_id}. "
                       f"Records may have expired (7-day retention) or document was never processed."
            )

        # Convert datetime strings if needed
        if isinstance(history.get("processed_at"), str):
            processed_at = history["processed_at"]
        else:
            processed_at = history["processed_at"].isoformat() if history.get("processed_at") else None

        if isinstance(history.get("expires_at"), str):
            expires_at = history["expires_at"]
        else:
            expires_at = history["expires_at"].isoformat() if history.get("expires_at") else None

        return HistoryResponse(
            history_id=history["history_id"],
            document_id=history["document_id"],
            format_detected=history.get("format_detected"),
            processed_at=processed_at,
            expires_at=expires_at,
            status=history["status"],
            text_extracted=history.get("text_extracted"),
            confidence=history.get("confidence"),
            pages_processed=history.get("pages_processed"),
            total_pages=history.get("total_pages"),
            processing_time_ms=history.get("processing_time_ms"),
            error_message=history.get("error_message"),
            metadata=history.get("metadata")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve history for document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/ocr/history/id/{history_id}", response_model=HistoryResponse)
async def get_history_by_id(history_id: str):
    """
    Get processing history by history ID

    Args:
        history_id: History record identifier

    Returns:
        Processing history record

    Raises:
        404: History record not found or expired
    """
    try:
        history = history_service.get_by_history_id(history_id)

        if not history:
            raise HTTPException(
                status_code=404,
                detail=f"History record {history_id} not found or expired"
            )

        # Convert datetime strings
        if isinstance(history.get("processed_at"), str):
            processed_at = history["processed_at"]
        else:
            processed_at = history["processed_at"].isoformat() if history.get("processed_at") else None

        if isinstance(history.get("expires_at"), str):
            expires_at = history["expires_at"]
        else:
            expires_at = history["expires_at"].isoformat() if history.get("expires_at") else None

        return HistoryResponse(
            history_id=history["history_id"],
            document_id=history["document_id"],
            format_detected=history.get("format_detected"),
            processed_at=processed_at,
            expires_at=expires_at,
            status=history["status"],
            text_extracted=history.get("text_extracted"),
            confidence=history.get("confidence"),
            pages_processed=history.get("pages_processed"),
            total_pages=history.get("total_pages"),
            processing_time_ms=history.get("processing_time_ms"),
            error_message=history.get("error_message"),
            metadata=history.get("metadata")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve history {history_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/ocr/history", response_model=HistoryListResponse)
async def get_recent_history(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    format_type: Optional[str] = Query(None, description="Filter by format type"),
    status: Optional[str] = Query(None, description="Filter by processing status"),
    start_date: Optional[str] = Query(None, description="Filter by start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Filter by end date (ISO format)")
):
    """
    Get recent processing history with optional filters

    Returns recent processing records that haven't expired.
    Records older than 7 days are automatically deleted.

    Args:
        limit: Maximum number of records to return
        format_type: Optional filter by file format
        status: Optional filter by processing status
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        List of recent processing history records
    """
    try:
        # Parse dates if provided
        start_datetime = None
        end_datetime = None

        if start_date:
            try:
                start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid start_date format. Use ISO format (e.g., 2024-01-01T00:00:00)"
                )

        if end_date:
            try:
                end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid end_date format. Use ISO format (e.g., 2024-01-01T23:59:59)"
                )

        # Search with filters
        if any([format_type, status, start_datetime, end_datetime]):
            records = history_service.search_history(
                format_type=format_type,
                status=status,
                start_date=start_datetime,
                end_date=end_datetime,
                limit=limit
            )
        else:
            # Get recent history without filters
            records = history_service.get_recent_history(limit=limit)

        # Convert to response format
        history_records = []
        for record in records:
            # Handle datetime conversion
            if isinstance(record.get("processed_at"), str):
                processed_at = record["processed_at"]
            else:
                processed_at = record["processed_at"].isoformat() if record.get("processed_at") else None

            if isinstance(record.get("expires_at"), str):
                expires_at = record["expires_at"]
            else:
                expires_at = record["expires_at"].isoformat() if record.get("expires_at") else None

            history_records.append(HistoryResponse(
                history_id=record.get("history_id", ""),
                document_id=record.get("document_id", ""),
                format_detected=record.get("format_detected"),
                processed_at=processed_at,
                expires_at=expires_at,
                status=record.get("status", "unknown"),
                text_extracted=record.get("text_extracted"),
                confidence=record.get("confidence"),
                pages_processed=record.get("pages_processed"),
                total_pages=record.get("total_pages"),
                processing_time_ms=record.get("processing_time_ms"),
                error_message=record.get("error_message"),
                metadata=record.get("metadata")
            ))

        return HistoryListResponse(
            total_records=len(history_records),
            records=history_records
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve history list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/ocr/history/batch/{job_id}")
async def get_batch_history(job_id: str):
    """
    Get batch processing history

    Args:
        job_id: Batch job identifier

    Returns:
        Batch processing history

    Raises:
        404: Batch job not found or expired
    """
    try:
        batch_history = history_service.get_batch_history(job_id)

        if not batch_history:
            raise HTTPException(
                status_code=404,
                detail=f"No history found for batch job {job_id}. "
                       f"Records may have expired (7-day retention) or job was never processed."
            )

        return batch_history

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve batch history for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/ocr/history/statistics", response_model=HistoryStatistics)
async def get_history_statistics():
    """
    Get statistics about processing history

    Returns statistics including total records, format distribution,
    and average processing times.

    Returns:
        History database statistics
    """
    try:
        stats = history_service.get_statistics()

        return HistoryStatistics(
            total_records=stats["total_records"],
            active_records=stats["active_records"],
            expired_records=stats["expired_records"],
            status_distribution=stats["status_distribution"],
            format_distribution=stats["format_distribution"],
            average_processing_time_ms=stats.get("average_processing_time_ms"),
            retention_days=stats["retention_days"]
        )

    except Exception as e:
        logger.error(f"Failed to get history statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/ocr/history/cleanup")
async def trigger_cleanup():
    """
    Manually trigger cleanup of expired records

    Removes all records older than 7 days.
    This happens automatically daily, but can be triggered manually.

    Returns:
        Number of records deleted
    """
    try:
        deleted_count = history_service.cleanup_expired_records()

        return {
            "status": "success",
            "deleted_records": deleted_count,
            "message": f"Cleaned up {deleted_count} expired records"
        }

    except Exception as e:
        logger.error(f"Failed to trigger cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/v1/ocr/history/{document_id}")
async def delete_document_history(
    document_id: str,
    confirm: bool = Query(False, description="Confirm deletion")
):
    """
    Delete history for a specific document (admin only)

    This endpoint should be restricted to admin users in production.

    Args:
        document_id: Document identifier
        confirm: Must be true to confirm deletion

    Returns:
        Deletion status
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Deletion not confirmed. Set confirm=true to delete."
        )

    # In production, add authentication/authorization check here
    # if not is_admin(current_user):
    #     raise HTTPException(status_code=403, detail="Admin access required")

    try:
        # Note: We'd need to add a delete method to HistoryService
        # For now, return not implemented
        raise HTTPException(
            status_code=501,
            detail="Delete operation not yet implemented. Records auto-expire after 7 days."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete history for document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))