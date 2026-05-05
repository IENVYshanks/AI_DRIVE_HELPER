from sqlalchemy import Enum


USER_STATUS = Enum(
    "active",
    "suspended",
    "deleted",
    name="user_status",
)

JOB_STATUS = Enum(
    "queued",
    "running",
    "done",
    "failed",
    "cancelled",
    name="job_status",
)

PROCESS_STATUS = Enum(
    "pending",
    "processing",
    "done",
    "failed",
    name="process_status",
)
