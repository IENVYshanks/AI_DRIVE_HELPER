"""ASGI entrypoint used by ``uvicorn main:app``."""

from src.app import create_app


app = create_app()
