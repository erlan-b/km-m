from __future__ import annotations

from fastapi import Request

from app.core.config import get_settings

DEFAULT_LANGUAGE = "en"

RU_TRANSLATIONS: dict[str, str] = {
    "Request failed": "Запрос не выполнен",
    "Request validation failed": "Ошибка валидации запроса",
    "Internal server error": "Внутренняя ошибка сервера",
    "Invalid refresh token": "Неверный refresh токен",
    "User not found": "Пользователь не найден",
    "Account is blocked": "Аккаунт заблокирован",
    "Refresh token is expired or revoked": "Refresh токен просрочен или отозван",
    "Logged out": "Выход выполнен",
    "If an account with that email exists, reset instructions were generated": "Если аккаунт с таким email существует, инструкции по восстановлению были сформированы",
    "Invalid or expired reset token": "Неверный или просроченный токен восстановления",
    "Password has been reset": "Пароль был сброшен",
    "Current password is incorrect": "Текущий пароль указан неверно",
    "New password must be different from current password": "Новый пароль должен отличаться от текущего",
    "Password changed successfully": "Пароль успешно изменен",
    "Unsupported language": "Неподдерживаемый язык",
    "User with this email already exists": "Пользователь с таким email уже существует",
    "Invalid credentials": "Неверные учетные данные",
    "Admin or moderator role required": "Требуется роль администратора или модератора",
    "Not enough permissions": "Недостаточно прав",
    "Listing not found": "Объявление не найдено",
    "Category not found": "Категория не найдена",
    "Report not found": "Жалоба не найдена",
    "Notification not found": "Уведомление не найдено",
    "Conversation not found": "Диалог не найден",
    "Message not found": "Сообщение не найдено",
    "No files provided": "Файлы не переданы",
    "Invalid action": "Недопустимое действие",
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
