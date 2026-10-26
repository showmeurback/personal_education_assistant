"""Хранилище учебных материалов курса в Weaviate.

Каждому курсу соответствует коллекция VectorStorage_<id>. Векторы фрагментов
вычисляются в приложении (llm.embeddings) и передаются в Weaviate как
«собственные» (self-provided): база знаний не зависит от конкретной модели
эмбеддингов, а модель можно заменить без перенастройки Weaviate.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from weaviate import WeaviateClient
from weaviate.classes.config import Configure, DataType, Property
from weaviate.classes.query import Filter, HybridFusion, MetadataQuery

from database.vector.client import weaviate_client, wvt_client
from llm.embeddings import embed_documents, embed_query


@dataclass
class Chunk:
    text: str
    file_id: str
    filename: str
    chunk_index: int
    score: float | None = None


def _collection_name(storage_id: str) -> str:
    return f"VectorStorage_{storage_id}"


class MaterialStore:
    def __init__(self, storage_id: str) -> None:
        self.storage_id = storage_id
        self.name = _collection_name(storage_id)

    def add_chunks(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0
        vectors = embed_documents([c.text for c in chunks])
        with weaviate_client() as client:
            collection = client.collections.get(self.name)
            with collection.batch.fixed_size(batch_size=64) as batch:
                for chunk, vector in zip(chunks, vectors):
                    batch.add_object(
                        properties={
                            "text": chunk.text,
                            "file_id": chunk.file_id,
                            "filename": chunk.filename,
                            "chunk_index": chunk.chunk_index,
                        },
                        vector={"main_vector": vector},
                    )
            failed = collection.batch.failed_objects
            if failed:
                raise RuntimeError(f"Weaviate: не удалось сохранить {len(failed)} фрагментов")
        return len(chunks)

    def hybrid_search(self, query: str, k: int = 5, alpha: float = 0.75) -> list[Chunk]:
        """Гибридный поиск: BM25 (символьное совпадение терминов) + векторная близость.

        alpha=0 — только BM25, alpha=1 — только векторный поиск.
        """
        vector = embed_query(query)
        with weaviate_client() as client:
            collection = client.collections.get(self.name)
            result = collection.query.hybrid(
                query=query,
                vector=vector,
                target_vector="main_vector",
                alpha=alpha,
                limit=k,
                fusion_type=HybridFusion.RELATIVE_SCORE,
                return_metadata=MetadataQuery(score=True),
            )
        return [
            Chunk(
                text=o.properties.get("text", ""),
                file_id=o.properties.get("file_id", ""),
                filename=o.properties.get("filename", ""),
                chunk_index=int(o.properties.get("chunk_index") or 0),
                score=o.metadata.score,
            )
            for o in result.objects
        ]

    def delete_by_file_id(self, file_id: str) -> int:
        with weaviate_client() as client:
            collection = client.collections.get(self.name)
            result = collection.data.delete_many(where=Filter.by_property("file_id").equal(file_id))
            return int(result.successful)

    def count(self) -> int:
        with weaviate_client() as client:
            collection = client.collections.get(self.name)
            return int(collection.aggregate.over_all(total_count=True).total_count or 0)


class StorageManager:
    @staticmethod
    @wvt_client
    def exists(storage_id: str, client: WeaviateClient = None) -> bool:
        return client.collections.exists(_collection_name(storage_id))

    @staticmethod
    def get_vector_storage(storage_id: str) -> MaterialStore:
        if not StorageManager.exists(storage_id):
            raise ValueError(f"storage with id {storage_id} is missing from the database")
        return MaterialStore(storage_id)

    @staticmethod
    @wvt_client
    def create_storage(client: WeaviateClient = None) -> str:
        storage_id = uuid4().hex
        while client.collections.exists(_collection_name(storage_id)):
            storage_id = uuid4().hex
        client.collections.create(
            name=_collection_name(storage_id),
            properties=[
                Property(name="text", data_type=DataType.TEXT),
                Property(name="file_id", data_type=DataType.TEXT, skip_vectorization=True),
                Property(name="filename", data_type=DataType.TEXT, skip_vectorization=True),
                Property(name="chunk_index", data_type=DataType.INT),
            ],
            vector_config=Configure.Vectors.self_provided(name="main_vector"),
        )
        return storage_id

    @staticmethod
    @wvt_client
    def delete_storage(storage_id: str, client: WeaviateClient = None) -> None:
        name = _collection_name(storage_id)
        if client.collections.exists(name):
            client.collections.delete(name)
