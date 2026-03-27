from fastapi import APIRouter, HTTPException, Query, Request, status

from app.core.i18n import (
    detect_request_language,
    get_page_translations,
    list_page_translation_keys,
    normalize_language,
)
from app.schemas.i18n import PageTranslationCatalogResponse, PageTranslationsResponse

router = APIRouter()


@router.get("/pages", response_model=PageTranslationCatalogResponse)
def list_translated_pages(
    request: Request,
    lang: str | None = Query(default=None),
) -> PageTranslationCatalogResponse:
    language = normalize_language(lang) if lang else detect_request_language(request)
    return PageTranslationCatalogResponse(
        language=language,
        pages=list_page_translation_keys(),
    )


@router.get("/pages/{page_key}", response_model=PageTranslationsResponse)
def get_translated_page(
    page_key: str,
    request: Request,
    lang: str | None = Query(default=None),
) -> PageTranslationsResponse:
    language = normalize_language(lang) if lang else detect_request_language(request)
    normalized_page = page_key.strip().lower().replace("-", "_")

    try:
        texts = get_page_translations(normalized_page, language)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation page not found",
        ) from exc

    return PageTranslationsResponse(page=normalized_page, language=language, texts=texts)