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
    "layout": {
        "en": {
            "brand": "KM-M Admin Panel",
            "operations_console": "Operations Console",
            "workspace_subtitle": "Moderation-first admin workspace",
            "logout": "Log out",
            "language": "Language",
            "nav_dashboard": "Dashboard",
            "nav_users": "Users",
            "nav_listings": "Listings Moderation",
            "nav_reports": "Reports",
            "nav_categories": "Categories",
            "nav_payments": "Payments",
            "nav_audit_logs": "Audit Logs",
        },
        "ru": {
            "brand": "Панель администратора KM-M",
            "operations_console": "Операционный центр",
            "workspace_subtitle": "Админ-пространство для модерации",
            "logout": "Выйти",
            "language": "Язык",
            "nav_dashboard": "Панель",
            "nav_users": "Пользователи",
            "nav_listings": "Модерация объявлений",
            "nav_reports": "Жалобы",
            "nav_categories": "Категории",
            "nav_payments": "Платежи",
            "nav_audit_logs": "Журнал аудита",
        },
    },
    "dashboard": {
        "en": {
            "title": "Dashboard",
            "subtitle": "Operational overview and moderation shortcuts.",
            "refresh": "Refresh",
            "refreshing": "Refreshing...",
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
            "refreshing": "Обновление...",
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
            "subtitle": "Search users, inspect profile statistics, suspend and unsuspend.",
            "refresh": "Refresh",
            "refreshing": "Refreshing...",
            "status": "Status",
            "roles": "Roles",
            "language": "Language",
            "details": "Details",
            "search_placeholder": "Search by full name or email",
            "apply_filters": "Apply filters",
            "search": "Search",
        },
        "ru": {
            "title": "Пользователи",
            "subtitle": "Поиск пользователей, просмотр статистики профиля, блокировка и разблокировка.",
            "refresh": "Обновить",
            "refreshing": "Обновление...",
            "status": "Статус",
            "roles": "Роли",
            "language": "Язык",
            "details": "Подробнее",
            "search_placeholder": "Поиск по имени или email",
            "apply_filters": "Применить фильтры",
            "search": "Найти",
        },
    },
    "listings": {
        "en": {
            "title": "Listings moderation",
            "subtitle": "Review queue, apply status transitions, and keep moderation notes.",
            "refresh": "Refresh",
            "refreshing": "Refreshing...",
            "apply_action": "Apply action",
            "reset_form": "Reset form",
            "apply_filters": "Apply filters",
            "search": "Search",
        },
        "ru": {
            "title": "Модерация объявлений",
            "subtitle": "Проверяйте очередь, применяйте переходы статусов и ведите заметки модерации.",
            "refresh": "Обновить",
            "refreshing": "Обновление...",
            "apply_action": "Применить действие",
            "reset_form": "Сбросить форму",
            "apply_filters": "Применить фильтры",
            "search": "Найти",
        },
    },
    "categories": {
        "en": {
            "title": "Categories",
            "subtitle": "Manage category metadata, active state, and dynamic listing fields with a visual builder.",
            "refresh": "Refresh",
            "refreshing": "Refreshing...",
            "create": "Create category",
            "save": "Save changes",
            "new_category": "New category",
        },
        "ru": {
            "title": "Категории",
            "subtitle": "Управляйте метаданными категорий, активностью и динамическими полями объявлений.",
            "refresh": "Обновить",
            "refreshing": "Обновление...",
            "create": "Создать категорию",
            "save": "Сохранить изменения",
            "new_category": "Новая категория",
        },
    },
    "payments": {
        "en": {
            "title": "Payments",
            "subtitle": "Track payment history, providers, statuses and timestamps.",
            "refresh": "Refresh",
            "refreshing": "Refreshing...",
            "filters": "Filters",
            "details": "Payment details",
            "apply_filters": "Apply filters",
            "reset": "Reset",
        },
        "ru": {
            "title": "Платежи",
            "subtitle": "Отслеживайте историю платежей, провайдеров, статусы и метки времени.",
            "refresh": "Обновить",
            "refreshing": "Обновление...",
            "filters": "Фильтры",
            "details": "Детали платежа",
            "apply_filters": "Применить фильтры",
            "reset": "Сброс",
        },
    },
    "reports": {
        "en": {
            "title": "Reports",
            "subtitle": "Review reports, apply moderation actions, and resolve or dismiss.",
            "refresh": "Refresh",
            "refreshing": "Refreshing...",
            "apply_filters": "Apply filters",
            "apply_action": "Apply action",
            "open": "Open",
            "resolved": "Resolved",
            "dismissed": "Dismissed",
        },
        "ru": {
            "title": "Жалобы",
            "subtitle": "Проверяйте жалобы, применяйте действия модерации, решайте или отклоняйте.",
            "refresh": "Обновить",
            "refreshing": "Обновление...",
            "apply_filters": "Применить фильтры",
            "apply_action": "Применить действие",
            "open": "Открытые",
            "resolved": "Решенные",
            "dismissed": "Отклоненные",
        },
    },
    "audit_logs": {
        "en": {
            "title": "Audit logs",
            "subtitle": "Trace moderation actions, actors, targets and details.",
            "refresh": "Refresh",
            "refreshing": "Refreshing...",
            "apply_filters": "Apply filters",
            "reset": "Reset",
            "action": "Action",
            "target": "Target",
            "created": "Created",
        },
        "ru": {
            "title": "Журнал аудита",
            "subtitle": "Отслеживайте действия модерации, исполнителей, цели и детали.",
            "refresh": "Обновить",
            "refreshing": "Обновление...",
            "apply_filters": "Применить фильтры",
            "reset": "Сброс",
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
