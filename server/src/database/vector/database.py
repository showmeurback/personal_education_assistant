from weaviate import WeaviateClient
from weaviate.classes.config import Configure, DataType, Property, VectorDistances

from .client import wvt_client

FINGERPRINT_COLLECTION = "ReportFingerprint"


class VecDatabase:
    def init_db(self) -> None:
        self.__create_fingerprint_index()

    @wvt_client
    def __create_fingerprint_index(self, client: WeaviateClient = None) -> None:
        """Индекс SimHash-отпечатков отчётов.

        Вектор — 64 бита отпечатка (0/1), метрика — расстояние Хэмминга,
        поэтому поиск ближайшего соседа сразу даёт число различающихся бит.
        """
        if client.collections.exists(FINGERPRINT_COLLECTION):
            return
        client.collections.create(
            name=FINGERPRINT_COLLECTION,
            properties=[
                Property(name="report_id", data_type=DataType.INT),
                Property(name="student_id", data_type=DataType.INT),
                Property(name="lab_id", data_type=DataType.INT),
            ],
            vector_config=Configure.Vectors.self_provided(
                name="simhash",
                vector_index_config=Configure.VectorIndex.flat(
                    distance_metric=VectorDistances.HAMMING,
                ),
            ),
        )
