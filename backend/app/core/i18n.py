from __future__ import annotations

from fastapi import Request

from app.core.config import get_settings

DEFAULT_LANGUAGE = "en"

RU_TRANSLATIONS: dict[str, str] = {
    "Logged out": "Выход выполнен",
    "If an account with that email exists, reset instructions were generated": "Если аккаунт с таким email существует, инструкции по восстановлению были сформированы",
    "Password has been reset": "Пароль был сброшен",
    "Password changed successfully": "Пароль успешно изменен",
    "Unsupported language": "Неподдерживаемый язык",
}

PAGE_TRANSLATIONS: dict[str, dict[str, dict[str, str]]] = {
    "dashboard": {
        "en": {
            "title": "Dashboard",
            "subtitle": "Operational overview and moderation shortcuts.",
            "refresh": "Refresh",
            "generated_at": "Generated at",
            "total_users": "Total users",
            "pending_listings": "Pending listings",
            "total_reports": "Total reports",
            "active_subscriptions": "Active subscriptions",
        },
        "ru": {
            "title": "Панель управления",
            "subtitle": "Оперативная сводка и быстрые действия модерации.",
            "refresh": "Обновить",
            "generated_at": "Сформировано",
            "total_users": "Всего пользователей",
            "pending_listings": "Объявлений на проверке",
            "total_reports": "Всего жалоб",
            "active_subscriptions": "Активные подписки",
        },
    },
    "users": {
        "en": {
            "title": "Users",
            "search_placeholder": "Search by email or name",
            "status": "Status",
            "roles": "Roles",
            "language": "Language",
            "details": "Details",
        },
        "ru": {
            "title": "Пользователи",
            "search_placeholder": "Поиск по email или имени",
            "status": "Статус",
            "roles": "Роли",
            "language": "Язык",
            "details": "Подробнее",
        },
    },
    "listings": {
        "en": {
            "title": "Listings moderation",
            "apply_action": "Apply action",
            "reset_form": "Reset form",
        },
        "ru": {
            "title": "Модерация объявлений",
            "apply_action": "Применить действие",
            "reset_form": "Сбросить форму",
        },
    },
    "categories": {
        "en": {
            "title": "Categories",
            "create": "Create category",
            "save": "Save changes",
        },
        "ru": {
            "title": "Категории",
            "create": "Создать категорию",
            "save": "Сохранить изменения",
        },
    },
    "payments": {
        "en": {
            "title": "Payments",
            "filters": "Filters",
            "details": "Payment details",
        },
        "ru": {
            "title": "Платежи",
            "filters": "Фильтры",
            "details": "Детали платежа",
        },
    },
    "reports": {
        "en": {
            "title": "Reports",
            "open": "Open",
            "resolved": "Resolved",
            "dismissed": "Dismissed",
        },
        "ru": {
            "title": "Жалобы",
            "open": "Открытые",
            "resolved": "Решенные",
            "dismissed": "Отклоненные",
        },
    },
    "audit_logs": {
        "en": {
            "title": "Audit logs",
            "action": "Action",
            "target": "Target",
            "created": "Created",
        },
        "ru": {
            "title": "Журнал аудита",
            "action": "Действие",
            "target": "Объект",
            "created": "Создано",
        },
    },
    "messages": {
        "en": {
            "title": "Messages",
            "conversation": "Conversation",
            "sender": "Sender",
            "content": "Content",
        },
        "ru": {
            "title": "Сообщения",
            "conversation": "Диалог",
            "sender": "Отправитель",
            "content": "Содержание",
        },
    },
}


def normalize_language(language: str | None) -> str:
    settings = get_settings()
    supported = settings.supported_languages
    if not supported:
        return DEFAULT_LANGUAGE

    if not language:
        return supported[0]

    normalized = language.strip().lower().replace("_", "-")
    if not normalized:
        return supported[0]

    primary = normalized.split("-", 1)[0]
    if primary in supported:
        return primary

    return supported[0]


def detect_request_language(request: Request, user_language: str | None = None) -> str:
    header_lang = request.headers.get("x-language")
    if header_lang:
        return normalize_language(header_lang)

    accept_language = request.headers.get("accept-language", "")
    if accept_language:
        first = accept_language.split(",", 1)[0]
        if first:
            return normalize_language(first)

    return normalize_language(user_language)


def translate_text(text: str, language: str) -> str:
    if language == "ru":
        return RU_TRANSLATIONS.get(text, text)
    return text


def list_page_translation_keys() -> list[str]:
    return sorted(PAGE_TRANSLATIONS.keys())


def get_page_translations(page_key: str, language: str) -> dict[str, str]:
    normalized_page = page_key.strip().lower().replace("-", "_")
    page_translations = PAGE_TRANSLATIONS.get(normalized_page)
    if page_translations is None:
        raise KeyError(normalized_page)

    return page_translations.get(language) or page_translations.get(DEFAULT_LANGUAGE, {})
