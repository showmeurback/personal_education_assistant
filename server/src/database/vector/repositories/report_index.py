"""Индекс SimHash-отпечатков отчётов в Weaviate."""
from __future__ import annotations

from dataclasses import dataclass

from weaviate import WeaviateClient
from weaviate.classes.query import Filter, MetadataQuery

from database.vector.client import wvt_client
from database.vector.database import FINGERPRINT_COLLECTION


@dataclass
class NearestFingerprint:
    report_id: int
    student_id: int
    hamming: int


class ReportIndex:
    """Хранит отпечатки и ищет ближайший отпечаток чужого отчёта по той же лабораторной."""

    @wvt_client
    def find_nearest(self, bits: list[int], *, lab_id: int, exclude_student_id: int,
                     client: WeaviateClient = None) -> NearestFingerprint | None:
        collection = client.collections.get(FINGERPRINT_COLLECTION)
        result = collection.query.near_vector(
            near_vector=[float(b) for b in bits],
            target_vector="simhash",
            limit=1,
            filters=(
                Filter.by_property("lab_id").equal(lab_id)
                & Filter.by_property("student_id").not_equal(exclude_student_id)
            ),
            return_metadata=MetadataQuery(distance=True),
        )
        for obj in result.objects:
            return NearestFingerprint(
                report_id=int(obj.properties["report_id"]),
                student_id=int(obj.properties["student_id"]),
                hamming=int(round(obj.metadata.distance)),
            )
        return None

    @wvt_client
    def add(self, bits: list[int], *, report_id: int, student_id: int, lab_id: int,
            client: WeaviateClient = None) -> None:
        collection = client.collections.get(FINGERPRINT_COLLECTION)
        collection.data.insert(
            properties={"report_id": report_id, "student_id": student_id, "lab_id": lab_id},
            vector={"simhash": [float(b) for b in bits]},
        )


class InMemoryReportIndex:
    """Реализация того же интерфейса в памяти — для тестов и экспериментов."""

    def __init__(self) -> None:
        self._items: list[tuple[list[int], int, int, int]] = []

    def find_nearest(self, bits, *, lab_id, exclude_student_id):
        best = None
        for other, report_id, student_id, item_lab in self._items:
            if item_lab != lab_id or student_id == exclude_student_id:
                continue
            d = sum(a != b for a, b in zip(bits, other))
            if best is None or d < best.hamming:
                best = NearestFingerprint(report_id=report_id, student_id=student_id, hamming=d)
        return best

    def add(self, bits, *, report_id, student_id, lab_id):
        self._items.append((list(bits), report_id, student_id, lab_id))
