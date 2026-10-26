import os
import sys
from pathlib import Path

# Тесты не обращаются к внешним сервисам: заглушка LLM и хеш-эмбеддинги
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMBEDDING_PROVIDER", "hash")
os.environ.setdefault("AUTH_SECRET", "test-secret-for-pytest-only-0123456789abcdef")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
