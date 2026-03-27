export type UiLanguage = "en" | "ru";

export function localeFromLanguage(language: UiLanguage): string {
  return language === "ru" ? "ru-RU" : "en-US";
}

export function formatDateTime(value: string | null, language: UiLanguage): string {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString(localeFromLanguage(language));
}

export function formatInteger(value: number, language: UiLanguage): string {
  return value.toLocaleString(localeFromLanguage(language));
}

export function formatCurrency(value: string | number, currency: string, language: UiLanguage): string {
  const numericValue = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(numericValue)) {
    return `${String(value)} ${currency}`;
  }

  try {
    return new Intl.NumberFormat(localeFromLanguage(language), {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(numericValue);
  } catch {
    return `${numericValue.toFixed(2)} ${currency}`;
  }
}