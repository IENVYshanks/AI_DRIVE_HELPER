"""Security regression tests for face-search result reconciliation."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4

from src.services.search_service import persist_search_results


class SearchResultTenantIsolationTests(TestCase):
    def setUp(self) -> None:
        self.db = Mock()
        self.delete_query = Mock()
        self.face_query = Mock()
        self.db.query.side_effect = [self.delete_query, self.face_query]
        self.delete_query.filter.return_value.delete.return_value = 0
        self.face_query.join.return_value.options.return_value.filter.return_value = (
            self.face_query
        )

    def test_ignores_face_owned_by_another_user(self) -> None:
        owner_id = uuid4()
        other_user_id = uuid4()
        face_id = uuid4()
        query = SimpleNamespace(id=uuid4(), user_id=owner_id)
        foreign_face = SimpleNamespace(
            id=face_id,
            user_id=other_user_id,
            image=SimpleNamespace(id=uuid4(), user_id=other_user_id),
        )
        self.face_query.all.return_value = [foreign_face]
        hit = SimpleNamespace(payload={"face_id": str(face_id)}, score=0.99)

        results = persist_search_results(self.db, query=query, qdrant_results=[hit])

        self.assertEqual(results, [])
        self.db.add.assert_not_called()

    def test_ignores_face_whose_image_belongs_to_another_user(self) -> None:
        owner_id = uuid4()
        face_id = uuid4()
        query = SimpleNamespace(id=uuid4(), user_id=owner_id)
        inconsistent_face = SimpleNamespace(
            id=face_id,
            user_id=owner_id,
            image=SimpleNamespace(id=uuid4(), user_id=uuid4()),
        )
        self.face_query.all.return_value = [inconsistent_face]
        hit = SimpleNamespace(payload={"face_id": str(face_id)}, score=0.95)

        results = persist_search_results(self.db, query=query, qdrant_results=[hit])

        self.assertEqual(results, [])
        self.db.add.assert_not_called()

    def test_persists_face_and_image_owned_by_query_user(self) -> None:
        owner_id = uuid4()
        face_id = uuid4()
        image_id = uuid4()
        query = SimpleNamespace(id=uuid4(), user_id=owner_id)
        owned_face = SimpleNamespace(
            id=face_id,
            user_id=owner_id,
            image=SimpleNamespace(id=image_id, user_id=owner_id),
        )
        self.face_query.all.return_value = [owned_face]
        hit = SimpleNamespace(payload={"face_id": str(face_id)}, score=0.91)

        results = persist_search_results(self.db, query=query, qdrant_results=[hit])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].query_id, query.id)
        self.assertEqual(results[0].face_id, face_id)
        self.assertEqual(results[0].image_id, image_id)
        self.assertEqual(results[0].rank, 1)
        self.db.add.assert_called_once_with(results[0])
