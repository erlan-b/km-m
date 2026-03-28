import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { API_ROOT } from "../../shared/config/env";

type Language = "en" | "ru";
type TranslationMap = Record<string, string>;
type LanguageCache = Record<string, TranslationMap>;
type CacheByLanguage = Record<Language, LanguageCache>;
type LoadingByLanguage = Record<Language, Record<string, boolean>>;

type PageResponse = {
  page: string;
  language: string;
  texts: Record<string, string>;
};

type I18nContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
  toggleLanguage: () => void;
  translate: (pageKey: string, key: string, fallback: string) => string;
  loadPage: (pageKey: string) => Promise<void>;
  isPageLoading: (pageKey: string) => boolean;
};

const LANGUAGE_STORAGE_KEY = "km_admin_language";

const I18nContext = createContext<I18nContextValue | null>(null);

function normalizeLanguage(raw: string | null | undefined): Language {
  const value = (raw ?? "").trim().toLowerCase();
  return value.startsWith("ru") ? "ru" : "en";
}

function normalizePageKey(pageKey: string): string {
  return pageKey.trim().toLowerCase().replace(/-/g, "_");
}

function readStoredLanguage(): Language {
  if (typeof window === "undefined") {
    return "en";
  }

  return normalizeLanguage(localStorage.getItem(LANGUAGE_STORAGE_KEY));
}

function persistLanguage(language: Language): void {
  if (typeof window === "undefined") {
    return;
  }

  localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
}

const emptyCache: CacheByLanguage = { en: {}, ru: {} };
const emptyLoading: LoadingByLanguage = { en: {}, ru: {} };

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() => readStoredLanguage());
  const [cacheByLanguage, setCacheByLanguage] = useState<CacheByLanguage>(emptyCache);
  const [loadingByLanguage, setLoadingByLanguage] = useState<LoadingByLanguage>(emptyLoading);

  const setLanguage = useCallback((nextLanguage: Language) => {
    setLanguageState(nextLanguage);
    persistLanguage(nextLanguage);
  }, []);

  const toggleLanguage = useCallback(() => {
    setLanguageState((current) => {
      const nextLanguage: Language = current === "en" ? "ru" : "en";
      persistLanguage(nextLanguage);
      return nextLanguage;
    });
  }, []);

  const loadPage = useCallback(
    async (pageKey: string): Promise<void> => {
      const normalizedPage = normalizePageKey(pageKey);
      if (!normalizedPage) {
        return;
      }

      if (cacheByLanguage[language][normalizedPage]) {
        return;
      }
      if (loadingByLanguage[language][normalizedPage]) {
        return;
      }

      setLoadingByLanguage((prev) => ({
        ...prev,
        [language]: {
          ...prev[language],
          [normalizedPage]: true,
        },
      }));

      try {
        const url = `${API_ROOT}/i18n/pages/${encodeURIComponent(normalizedPage)}?lang=${language}`;
        const response = await fetch(url, { method: "GET" });
        if (!response.ok) {
          throw new Error("Failed to load page translations");
        }

        const payload = (await response.json()) as PageResponse;
        const texts = payload.texts ?? {};

        setCacheByLanguage((prev) => ({
          ...prev,
          [language]: {
            ...prev[language],
            [normalizedPage]: texts,
          },
        }));
      } catch {
        setCacheByLanguage((prev) => ({
          ...prev,
          [language]: {
            ...prev[language],
            [normalizedPage]: {},
          },
        }));
      } finally {
        setLoadingByLanguage((prev) => ({
          ...prev,
          [language]: {
            ...prev[language],
            [normalizedPage]: false,
          },
        }));
      }
    },
    [cacheByLanguage, language, loadingByLanguage],
  );

  const translate = useCallback(
    (pageKey: string, key: string, fallback: string): string => {
      const normalizedPage = normalizePageKey(pageKey);
      const pageMap = cacheByLanguage[language][normalizedPage];
      if (!pageMap) {
        return fallback;
      }

      const text = pageMap[key];
      if (typeof text !== "string" || text.length === 0) {
        return fallback;
      }
      return text;
    },
    [cacheByLanguage, language],
  );

  const isPageLoading = useCallback(
    (pageKey: string): boolean => {
      const normalizedPage = normalizePageKey(pageKey);
      return Boolean(loadingByLanguage[language][normalizedPage]);
    },
    [language, loadingByLanguage],
  );

  const contextValue = useMemo<I18nContextValue>(
    () => ({
      language,
      setLanguage,
      toggleLanguage,
      translate,
      loadPage,
      isPageLoading,
    }),
    [isPageLoading, language, loadPage, setLanguage, toggleLanguage, translate],
  );

  return <I18nContext.Provider value={contextValue}>{children}</I18nContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used inside I18nProvider");
  }
  return context;
}

// eslint-disable-next-line react-refresh/only-export-components
export function usePageI18n(pageKey: string): {
  language: Language;
  t: (key: string, fallback: string) => string;
  isLoading: boolean;
} {
  const { language, loadPage, translate, isPageLoading } = useI18n();

  useEffect(() => {
    void loadPage(pageKey);
  }, [language, loadPage, pageKey]);

  const t = useCallback(
    (key: string, fallback: string) => translate(pageKey, key, fallback),
    [pageKey, translate],
  );

  return {
    language,
    t,
    isLoading: isPageLoading(pageKey),
  };
}