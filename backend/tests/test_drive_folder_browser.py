"""API contract tests for authenticated Google Drive folder browsing."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.app import create_app
from src.db.config import Settings
from src.db.database import get_db
from src.dependencies import get_current_user


def test_settings() -> Settings:
    return Settings(
        DB_USERNAME="app",
        DB_PASSWORD="database-secret",
        DB_NAME="app",
        AUTO_CREATE_TABLES=False,
        TRUSTED_HOSTS="testserver",
    )


class DriveFolderBrowserApiTests(TestCase):
    def test_returns_folder_browser_contract_for_authenticated_user(self) -> None:
        app = create_app(test_settings())
        user = SimpleNamespace(id=uuid4())
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: Mock()

        with patch("src.routers.ingestion.browse_drive_folders") as browse:
            browse.return_value = (
                {"id": "root", "name": "My Drive", "parent_id": None},
                [{"id": "photos", "name": "Photos", "parent_id": "root"}],
            )
            with TestClient(app) as client:
                response = client.get("/ingestion/drive/folders?parent_id=root")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["folders"][0]["id"], "photos")
        browse.assert_called_once()

    def test_requires_authenticated_user(self) -> None:
        app = create_app(test_settings())

        def reject_user():
            raise HTTPException(status_code=401, detail="Not authenticated")

        app.dependency_overrides[get_current_user] = reject_user
        app.dependency_overrides[get_db] = lambda: Mock()
        with TestClient(app) as client:
            response = client.get("/ingestion/drive/folders")

        self.assertEqual(response.status_code, 401)

    def test_rejects_invalid_parent_id_before_provider_call(self) -> None:
        app = create_app(test_settings())
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4())
        app.dependency_overrides[get_db] = lambda: Mock()
        with patch("src.routers.ingestion.browse_drive_folders") as browse:
            with TestClient(app) as client:
                response = client.get("/ingestion/drive/folders?parent_id=bad%27id")

        self.assertEqual(response.status_code, 422)
        browse.assert_not_called()

    def test_masks_drive_provider_failure(self) -> None:
        app = create_app(test_settings())
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4())
        app.dependency_overrides[get_db] = lambda: Mock()
        with patch("src.routers.ingestion.browse_drive_folders") as browse:
            browse.side_effect = RuntimeError("provider credential detail")
            with TestClient(app) as client:
                response = client.get("/ingestion/drive/folders")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": "Could not load Google Drive folders"})
        self.assertNotIn("credential", response.text)
