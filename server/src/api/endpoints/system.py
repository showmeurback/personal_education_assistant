from fastapi import Depends

from auth import CurrentUser, get_current_user
from settings import embedding_settings, llm_settings, verification_settings, vision_settings

from ..app import app


@app.get("/api/v1/health", tags=["Система"])
def health():
    return {"status": "ok"}


@app.get("/api/v1/system/config", tags=["Система"])
def system_config(user: CurrentUser = Depends(get_current_user)):
    """Текущая конфигурация компонентов (без секретов) — для страницы «О системе»."""
    return {
        "llm": {"provider": llm_settings.provider, "model": llm_settings.model,
                "judge_model": llm_settings.judge_model or llm_settings.model,
                "judge_models": {j: llm_settings.model_for_judge(j) for j in ("strict", "objective", "loyal")},
                "feedback_model": llm_settings.feedback_model,
                "base_url": llm_settings.base_url, "configured": bool(llm_settings.api_key)
                or llm_settings.provider == "mock"},
        "embeddings": {"provider": embedding_settings.provider, "model": embedding_settings.model},
        "vision": {"enabled": vision_settings.enabled, "model": vision_settings.model,
                   "max_images": vision_settings.max_images},
        "verification": {
            "simhash_bits": verification_settings.simhash_bits,
            "simhash_shingle": verification_settings.simhash_shingle,
            "duplicate_max_hamming": verification_settings.duplicate_max_hamming,
            "default_min_words": verification_settings.default_min_words,
            "approve_threshold": verification_settings.approve_threshold,
            "reject_threshold": verification_settings.reject_threshold,
            "min_valid_judges": verification_settings.min_valid_judges,
        },
    }
