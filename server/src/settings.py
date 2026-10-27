"""Конфигурация приложения.

Все параметры читаются из переменных окружения (или файла .env).
Параметры сгруппированы по компонентам гибридной системы, чтобы каждый
компонент можно было перенастроить независимо от остальных.
"""
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class _Base(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        frozen=True,
        populate_by_name=True,
    )


# Пресеты OpenAI-совместимых поставщиков: адрес API и модели по умолчанию.
# Любое значение переопределяется переменными окружения LLM_BASE_URL, LLM_MODEL и т. п.
PROVIDER_PRESETS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "deepseek/deepseek-v4.1-flash",
        "embedding_model": "baai/bge-m3",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "openai/gpt-oss-120b",
        "embedding_model": "",  # Groq не предоставляет эмбеддингов: EMBEDDING_PROVIDER=local
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "minimaxai/minimax-m3.1-flash",
        "embedding_model": "nvidia/nemotron-3.5-embed-8b",
        # оценщики на моделях разных семейств и размеров: ошибки меньше коррелируют;
        # «@nothink» — без этапа рассуждения (ответ за секунды, а не минуты)
        "judge_models": {
            "strict": "nvidia/nemotron-3-ultra-550b-a55b@nothink",
            "objective": "openai/gpt-oss-20b",
            # лояльный: выбран на наборе настройки из 8 кандидатов (точность 25 из 26, устойчив
            # к внедрённой инструкции 6 из 6, медиана 7 с); прежний lightning-30b — 18 из 26, 0 из 6
            "loyal": "nvidia/nemotron-3-ultra-550b-a55b@nothink",
        },
        "vision_model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
        # пояснение при отклонении: короткий связный текст без этапа рассуждения
        "feedback_model": "nvidia/nemotron-3-ultra-550b-a55b@nothink",
    },
}


def _preset(provider: str, key: str) -> str:
    return PROVIDER_PRESETS.get(provider.lower(), PROVIDER_PRESETS["nvidia"])[key]


class LLMSettings(_Base):
    """Статистический (нейросетевой) компонент: языковая модель."""

    # openrouter | nvidia | openai (любой OpenAI-совместимый API) | mock (заглушка для тестов)
    provider: str = Field(default="nvidia", alias="LLM_PROVIDER")
    base_url_override: str | None = Field(default=None, alias="LLM_BASE_URL")
    api_key: str = Field(default="", validation_alias=AliasChoices(
        "LLM_API_KEY", "OPENROUTER_API_KEY", "NVIDIA_API_KEY"))
    model_override: str | None = Field(default=None, alias="LLM_MODEL")
    # модель для оценщиков проверки отчётов (по умолчанию — основная модель)
    judge_model: str | None = Field(default=None, alias="LLM_JUDGE_MODEL")
    # отдельная модель для каждого оценщика: «strict=…,objective=…,loyal=…»;
    # разные модели делают ошибки оценщиков менее коррелированными
    judge_models: str = Field(default="", alias="LLM_JUDGE_MODELS")
    # модель генератора пояснений (по умолчанию — из пресета поставщика или основная)
    feedback_model_override: str | None = Field(default=None, alias="LLM_FEEDBACK_MODEL")
    # с запасом: модели с рассуждением тратят часть токенов до ответа
    judge_max_tokens: int = Field(default=1024, alias="LLM_JUDGE_MAX_TOKENS")
    temperature: float = Field(default=0.3, alias="LLM_TEMPERATURE")
    max_tokens: int = Field(default=2048, alias="LLM_MAX_TOKENS")
    # модели с рассуждением (minimax, deepseek и др.) тратят часть лимита токенов до ответа:
    # к лимиту каждого вызова добавляется запас; для обычных моделей это лишь верхняя граница
    reasoning_reserve: int = Field(default=6144, alias="LLM_REASONING_RESERVE")
    timeout: float = Field(default=300.0, alias="LLM_TIMEOUT")
    max_retries: int = Field(default=5, alias="LLM_MAX_RETRIES")
    # бесплатные тарифы ограничивают запросы и токены в минуту: повтор с ожиданием
    rate_limit_retries: int = Field(default=6, alias="LLM_RATE_LIMIT_RETRIES")
    max_concurrency: int = Field(default=3, alias="LLM_MAX_CONCURRENCY")

    @property
    def base_url(self) -> str:
        return self.base_url_override or _preset(self.provider, "base_url")

    @property
    def model(self) -> str:
        return self.model_override or _preset(self.provider, "model")

    @property
    def feedback_model(self) -> str:
        if self.feedback_model_override:
            return self.feedback_model_override
        if self.model_override:
            return self.model_override
        return PROVIDER_PRESETS.get(self.provider.lower(), {}).get("feedback_model") or self.model

    def model_for_judge(self, judge: str) -> str:
        """Модель оценщика: LLM_JUDGE_MODELS → пресет поставщика → LLM_JUDGE_MODEL → основная."""
        spec = self.judge_models.strip()
        if spec.lower() == "same":  # все оценщики на одной модели (вариант v2)
            return self.judge_model or self.model
        pairs = {k.strip(): v.strip() for k, v in (p.split("=", 1) for p in spec.split(",") if "=" in p)} if spec else \
            ({} if self.judge_model or self.model_override else
             PROVIDER_PRESETS.get(self.provider.lower(), {}).get("judge_models", {}))
        return pairs.get(judge, "").strip() or self.judge_model or self.model


class VisionSettings(_Base):
    """Агент описания изображений отчёта (модель зрения того же поставщика)."""

    enabled: bool = Field(default=True, alias="VISION_ENABLED")
    model_override: str | None = Field(default=None, alias="VISION_MODEL")
    max_images: int = Field(default=12, alias="VISION_MAX_IMAGES")
    concurrency: int = Field(default=6, alias="VISION_CONCURRENCY")
    max_side: int = Field(default=1024, alias="VISION_MAX_SIDE")
    min_side: int = Field(default=80, alias="VISION_MIN_SIDE")
    max_tokens: int = Field(default=400, alias="VISION_MAX_TOKENS")
    max_chars: int = Field(default=700, alias="VISION_MAX_CHARS")
    # описание рисунка не требует рассуждения: без него ответ в 3–5 раз быстрее
    thinking: bool = Field(default=False, alias="VISION_THINKING")
    timeout: float = Field(default=15.0, alias="VISION_TIMEOUT")

    @property
    def model(self) -> str:
        return self.model_override or PROVIDER_PRESETS.get(
            llm_settings.provider.lower(), {}).get("vision_model", "") or llm_settings.model


class EmbeddingSettings(_Base):
    """Векторные представления текста для семантического поиска."""

    # openrouter | nvidia | openai (OpenAI-совместимый /embeddings) | local (t2v-transformers) | hash (заглушка)
    provider: str = Field(default="nvidia", alias="EMBEDDING_PROVIDER")
    base_url_override: str | None = Field(default=None, alias="EMBEDDING_BASE_URL")
    api_key: str = Field(default="", validation_alias=AliasChoices(
        "EMBEDDING_API_KEY", "LLM_API_KEY", "OPENROUTER_API_KEY", "NVIDIA_API_KEY"))
    model_override: str | None = Field(default=None, alias="EMBEDDING_MODEL")
    local_url: str = Field(default="http://t2v-transformers:8080", alias="EMBEDDING_LOCAL_URL")
    hash_dim: int = Field(default=256, alias="EMBEDDING_HASH_DIM")
    batch_size: int = Field(default=32, alias="EMBEDDING_BATCH_SIZE")

    @property
    def base_url(self) -> str:
        return self.base_url_override or _preset(self.provider, "base_url")

    @property
    def model(self) -> str:
        return self.model_override or _preset(self.provider, "embedding_model")


class VerificationSettings(_Base):
    """Параметры гибридного конвейера проверки отчётов."""

    # SimHash: 64-битный отпечаток, порог по расстоянию Хэмминга
    simhash_bits: int = Field(default=64, alias="SIMHASH_BITS")
    simhash_shingle: int = Field(default=3, alias="SIMHASH_SHINGLE")
    duplicate_max_hamming: int = Field(default=10, alias="SIMHASH_MAX_HAMMING")
    # продукционные правила по умолчанию (переопределяются в настройках лабы)
    default_min_words: int = Field(default=120, alias="REPORT_MIN_WORDS")
    # предел текста, передаваемого оценщикам (современные модели принимают длинный контекст);
    # длиннее — предупреждение R5 и передача начала текста
    max_report_chars: int = Field(default=60000, alias="REPORT_MAX_CHARS")
    # агрегация вердиктов
    approve_threshold: float = Field(default=0.65, alias="AGG_APPROVE_THRESHOLD")
    reject_threshold: float = Field(default=0.35, alias="AGG_REJECT_THRESHOLD")
    min_valid_judges: int = Field(default=2, alias="AGG_MIN_VALID_JUDGES")
    # правило A6: при голосах 2:1 решение принимается, если «за» большинство голосовали
    # оба сильных оценщика с уверенностью не ниже порога, а несогласен — третий
    strong_judges: str = Field(default="strict,objective", alias="AGG_STRONG_JUDGES")
    strong_min_confidence: float = Field(default=0.8, alias="AGG_STRONG_MIN_CONFIDENCE")
    # правило R7: соответствие отчёта своей лабораторной по векторам
    lab_match_enabled: bool = Field(default=True, alias="LAB_MATCH_ENABLED")
    lab_match_min_sim: float = Field(default=0.45, alias="LAB_MATCH_MIN_SIM")
    lab_match_margin: float = Field(default=0.05, alias="LAB_MATCH_MARGIN")
    lab_match_timeout: float = Field(default=15.0, alias="LAB_MATCH_TIMEOUT")
    # число одновременных проверок отчётов (остальные ждут в очереди)
    check_concurrency: int = Field(default=4, alias="VERIFICATION_CONCURRENCY")


class AuthSettings(_Base):
    secret: str = Field(default="change-me-in-production", alias="AUTH_SECRET")
    token_ttl_hours: int = Field(default=72, alias="AUTH_TOKEN_TTL_HOURS")


class AppSettings(_Base):
    uploads_dir: str = Field(default="/app/uploads", alias="UPLOADS_DIR")
    weaviate_host: str = Field(default="weaviate", alias="WEAVIATE_HOST")
    weaviate_port: int = Field(default=8080, alias="WEAVIATE_PORT")
    weaviate_grpc_port: int = Field(default=50051, alias="WEAVIATE_GRPC_PORT")
    dev_reload: bool = Field(default=False, alias="DEV_RELOAD")
    # наполнение демонстрационными данными при первом запуске (пустая база)
    seed_demo: bool = Field(default=False, alias="SEED_DEMO")


class PostgreDatabaseConfig(_Base):
    host: str
    port: int
    user: str
    password: str
    name: str


class EducationDatabaseConfig(PostgreDatabaseConfig):
    host: str = Field(default="sql_database", alias="EDUCATION_DATABASE_HOST")
    port: int = Field(default=5432, alias="EDUCATION_DATABASE_PORT")
    user: str = Field(default="postgres", alias="EDUCATION_DATABASE_USER")
    password: str = Field(default="postgres", alias="EDUCATION_DATABASE_PASS")
    name: str = Field(default="education_database", alias="EDUCATION_DATABASE_NAME")


llm_settings = LLMSettings()
vision_settings = VisionSettings()
embedding_settings = EmbeddingSettings()
verification_settings = VerificationSettings()
auth_settings = AuthSettings()
settings = AppSettings()
