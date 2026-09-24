from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

import numpy as np

from src.services.demo_people_service import (
    DemoPersonResult,
    DemoPersonMatch,
    _resolve_matches,
    analyze_demo_people,
    build_demo_people_manifest,
)


class DemoPeopleAnalysisTests(TestCase):
    @patch("src.services.demo_people_service.extract_primary_face_embedding")
    def test_two_portraits_form_one_normalized_centroid(self, extract_face) -> None:
        extract_face.side_effect = [
            {"embedding": [1.0, 0.0]},
            {"embedding": [0.8, 0.2]},
            {"embedding": [0.0, 1.0]},
            {"embedding": [0.2, 0.8]},
            {"embedding": [-1.0, 0.0]},
            {"embedding": [-0.8, 0.2]},
            {"embedding": [0.0, -1.0]},
            {"embedding": [0.2, -0.8]},
        ]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name in (
                "chris1.jpg",
                "chris2.jpg",
                "jeremy1.jpg",
                "jemery2.jpg",
                "robertd1.webp",
                "robertd2.jpg",
                "scarlet.jpg",
                "sacrlet1.jpg",
            ):
                (root / name).write_bytes(name.encode())

            people = analyze_demo_people(root)

        self.assertEqual([person.name for person in people], [
            "Chris Hemsworth",
            "Jeremy Renner",
            "Robert Downey Jr.",
            "Scarlett Johansson",
        ])
        self.assertTrue(all(len(person.portrait_paths) == 2 for person in people))
        self.assertTrue(
            all(np.isclose(np.linalg.norm(person.centroid), 1.0) for person in people)
        )

    def test_manifest_maps_named_results_to_public_photo_ids(self) -> None:
        result = DemoPersonResult(
            id="person-id",
            name="Example Person",
            portraits=("one.jpg", "two.jpg"),
            matches=(DemoPersonMatch(photo_name="group.jpg", score=0.8),),
        )

        manifest = build_demo_people_manifest(
            [result],
            photos=[{"id": "photo-id", "src": "/demo/photos/group.jpg"}],
        )

        self.assertEqual(manifest[0]["name"], "Example Person")
        self.assertEqual(manifest[0]["portraits"], [
            "/demo/people/one.jpg",
            "/demo/people/two.jpg",
        ])
        self.assertEqual(manifest[0]["matches"], [
            {"photoId": "photo-id", "score": 0.9}
        ])


class DemoPeopleMatchTests(TestCase):
    def test_matches_are_user_scoped_thresholded_and_deduplicated_by_image(self) -> None:
        image_id = uuid4()
        first = SimpleNamespace(id=uuid4(), image_id=image_id)
        second = SimpleNamespace(id=uuid4(), image_id=image_id)
        third = SimpleNamespace(id=uuid4(), image_id=uuid4())
        query = Mock()
        query.join.return_value = query
        query.filter.return_value = query
        query.all.return_value = [first, second, third]
        db = Mock()
        db.query.return_value = query
        hits = [
            SimpleNamespace(payload={"face_id": str(first.id)}, score=0.8),
            SimpleNamespace(payload={"face_id": str(second.id)}, score=0.7),
            SimpleNamespace(payload={"face_id": str(third.id)}, score=0.2),
        ]

        matches = _resolve_matches(
            db,
            user_id=uuid4(),
            hits=hits,
            minimum_similarity=0.3,
        )

        self.assertEqual(matches, [{"face": first, "score": 0.8}])
