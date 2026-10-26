"""Индексация учебных материалов курса: извлечение текста, разбиение, векторизация."""
from __future__ import annotations

from uuid import uuid4

from langchain_text_splitters import RecursiveCharacterTextSplitter

from common.text_extraction import extract_text_from_bytes
from database.vector.repositories.storage import Chunk, StorageManager


class Indexer:
    def __init__(self, storage_id: str, chunk_size: int = 1000, chunk_overlap: int = 200):
        self._store = StorageManager.get_vector_storage(storage_id)
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def add_file(self, data: bytes, filename: str) -> tuple[str, int]:
        """Индексирует файл. Возвращает (file_id, число фрагментов)."""
        text = extract_text_from_bytes(data, filename)
        if not text.strip():
            raise ValueError(f"В файле «{filename}» не найден текст")
        file_id = uuid4().hex
        pieces = self._splitter.split_text(text)
        chunks = [Chunk(text=p, file_id=file_id, filename=filename, chunk_index=i)
                  for i, p in enumerate(pieces)]
        count = self._store.add_chunks(chunks)
        return file_id, count
