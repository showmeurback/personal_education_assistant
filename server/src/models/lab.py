from pydantic import BaseModel, Field


class NewLab(BaseModel):
    number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=300)
    task: str = ""
    # формальные требования к отчёту (используются продукционными правилами)
    min_words: int | None = Field(default=None, ge=0, le=20000)
    required_sections: str | None = None  # разделы через перевод строки
