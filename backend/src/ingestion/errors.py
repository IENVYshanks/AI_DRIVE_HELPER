"""Stable public messages for ingestion failures.

Detailed provider and infrastructure exceptions belong in protected logs, not
in database fields that are returned by authenticated API endpoints.
"""

IMAGE_PROCESSING_FAILED_MESSAGE = "Image processing failed"
INGESTION_FAILED_MESSAGE = "Ingestion failed"

