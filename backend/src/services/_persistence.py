"""Small persistence helpers shared by state-transition services."""

from typing import TypeVar

from sqlalchemy.orm import Session


ModelT = TypeVar("ModelT")


def commit_and_refresh(db: Session, model: ModelT, *, auto_commit: bool) -> ModelT:
    """Persist and refresh ``model`` when this function owns the transaction.

    With ``auto_commit=False``, changes remain staged so a higher-level service
    can atomically commit several related models together.
    """
    if auto_commit:
        db.commit()
        db.refresh(model)
    return model
