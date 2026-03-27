from pydantic import BaseModel, Field


class PageTranslationCatalogResponse(BaseModel):
    language: str
    pages: list[str] = Field(default_factory=list)


class PageTranslationsResponse(BaseModel):
    page: str
    language: str
    texts: dict[str, str] = Field(default_factory=dict)