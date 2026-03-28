import { useCallback, useEffect, useState } from "react";

import { useAuth } from "../../app/auth/AuthContext";
import { usePageI18n } from "../../app/i18n/I18nContext";

type CategoryItem = {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
};

type PromotionPackageItem = {
  id: number;
  title: string;
  description: string | null;
  duration_days: number;
  price: string;
  currency: string;
  is_active: boolean;
};

type TranslationRow = {
  entityId: number;
  entityLabel: string;
  en: string;
  ru: string;
  enDirty: boolean;
  ruDirty: boolean;
  saving: boolean;
};

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "Request failed";
}

export function LocalizationPage() {
  const { authFetch } = useAuth();
  const { t } = usePageI18n("localization_admin");

  const [activeTab, setActiveTab] = useState<"categories" | "promotions">("categories");
  const [categoryRows, setCategoryRows] = useState<TranslationRow[]>([]);
  const [promoRows, setPromoRows] = useState<TranslationRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const [catRes, promoRes, i18nRes] = await Promise.all([
        authFetch("/categories"),
        authFetch("/promotions/packages/admin"),
        authFetch("/i18n/admin/entries?page_size=100&include_inactive=false"),
      ]);

      if (!catRes.ok || !promoRes.ok || !i18nRes.ok) {
        throw new Error("Failed to load data");
      }

      const categories = ((await catRes.json()) as { items: CategoryItem[] }).items;
      const promoPackages = ((await promoRes.json()) as { items: PromotionPackageItem[] }).items;
      const i18nEntries = ((await i18nRes.json()) as {
        items: { page_key: string; text_key: string; language: string; text_value: string }[];
      }).items;

      // Build lookup: page_key -> text_key -> language -> value
      const lookup = new Map<string, Map<string, Map<string, string>>>();
      for (const entry of i18nEntries) {
        if (!lookup.has(entry.page_key)) lookup.set(entry.page_key, new Map());
        const pageMap = lookup.get(entry.page_key)!;
        if (!pageMap.has(entry.text_key)) pageMap.set(entry.text_key, new Map());
        pageMap.get(entry.text_key)!.set(entry.language, entry.text_value);
      }

      const getTranslation = (pageKey: string, textKey: string, lang: string): string => {
        return lookup.get(pageKey)?.get(textKey)?.get(lang) ?? "";
      };

      setCategoryRows(
        categories.map((cat) => ({
          entityId: cat.id,
          entityLabel: `${cat.name} (${cat.slug})`,
          en: getTranslation("categories", `category_${cat.id}_name`, "en") || cat.name,
          ru: getTranslation("categories", `category_${cat.id}_name`, "ru"),
          enDirty: false,
          ruDirty: false,
          saving: false,
        }))
      );

      setPromoRows(
        promoPackages.map((pkg) => ({
          entityId: pkg.id,
          entityLabel: `${pkg.title} (${pkg.duration_days}d / ${pkg.price} ${pkg.currency})`,
          en: getTranslation("promotions", `package_${pkg.id}_title`, "en") || pkg.title,
          ru: getTranslation("promotions", `package_${pkg.id}_title`, "ru"),
          enDirty: false,
          ruDirty: false,
          saving: false,
        }))
      );
    } catch (loadError) {
      setError(extractErrorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, [authFetch]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const updateRow = (
    tab: "categories" | "promotions",
    entityId: number,
    lang: "en" | "ru",
    value: string
  ) => {
    const setter = tab === "categories" ? setCategoryRows : setPromoRows;
    setter((prev) =>
      prev.map((row) =>
        row.entityId === entityId
          ? { ...row, [lang]: value, [`${lang}Dirty`]: true }
          : row
      )
    );
  };

  const saveRow = async (tab: "categories" | "promotions", entityId: number) => {
    const rows = tab === "categories" ? categoryRows : promoRows;
    const row = rows.find((r) => r.entityId === entityId);
    if (!row) return;

    const setter = tab === "categories" ? setCategoryRows : setPromoRows;
    setter((prev) =>
      prev.map((r) => (r.entityId === entityId ? { ...r, saving: true } : r))
    );
    setError(null);
    setSuccessMessage(null);

    const pageKey = tab === "categories" ? "categories" : "promotions";
    const textKey =
      tab === "categories"
        ? `category_${entityId}_name`
        : `package_${entityId}_title`;

    try {
      for (const lang of ["en", "ru"] as const) {
        const value = row[lang].trim();
        if (!value) continue;

        // Try to find existing entry to update, otherwise create
        const searchRes = await authFetch(
          `/i18n/admin/entries?page_key=${pageKey}&page_size=100&include_inactive=true`
        );
        if (!searchRes.ok) throw new Error("Failed to search entries");

        const searchData = (await searchRes.json()) as {
          items: { id: number; page_key: string; text_key: string; language: string }[];
        };

        const existing = searchData.items.find(
          (e) => e.page_key === pageKey && e.text_key === textKey && e.language === lang
        );

        if (existing) {
          const res = await authFetch(`/i18n/admin/entries/${existing.id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text_value: value, is_active: true }),
          });
          if (!res.ok) throw new Error(`Failed to update ${lang} translation`);
        } else {
          const res = await authFetch("/i18n/admin/entries", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              page_key: pageKey,
              text_key: textKey,
              language: lang,
              text_value: value,
              is_active: true,
            }),
          });
          if (!res.ok) throw new Error(`Failed to create ${lang} translation`);
        }
      }

      setter((prev) =>
        prev.map((r) =>
          r.entityId === entityId
            ? { ...r, saving: false, enDirty: false, ruDirty: false }
            : r
        )
      );
      setSuccessMessage(t("saved_successfully", "Translation saved successfully"));
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (saveError) {
      setError(extractErrorMessage(saveError));
      setter((prev) =>
        prev.map((r) => (r.entityId === entityId ? { ...r, saving: false } : r))
      );
    }
  };

  const currentRows = activeTab === "categories" ? categoryRows : promoRows;
  const hasDirtyRows = currentRows.some((r) => r.enDirty || r.ruDirty);

  return (
    <section className="module-page">
      <header className="module-header">
        <div>
          <h1>{t("title", "Content Translations")}</h1>
          <p>
            {t(
              "subtitle",
              "Manage localized names for categories and promotion packages across supported languages."
            )}
          </p>
        </div>
        <div className="users-actions-cell">
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => void loadData()}
            disabled={isLoading}
          >
            {isLoading ? t("refreshing", "Refreshing...") : t("refresh", "Refresh")}
          </button>
        </div>
      </header>

      {error ? <div className="dashboard-error">{error}</div> : null}
      {successMessage ? (
        <div className="l10n-success">{successMessage}</div>
      ) : null}

      {/* Tabs */}
      <div className="l10n-tabs">
        <button
          type="button"
          className={`l10n-tab ${activeTab === "categories" ? "l10n-tab-active" : ""}`}
          onClick={() => setActiveTab("categories")}
        >
          {t("tab_categories", "Category Names")}
          <span className="l10n-tab-count">{categoryRows.length}</span>
        </button>
        <button
          type="button"
          className={`l10n-tab ${activeTab === "promotions" ? "l10n-tab-active" : ""}`}
          onClick={() => setActiveTab("promotions")}
        >
          {t("tab_promotions", "Promotion Package Titles")}
          <span className="l10n-tab-count">{promoRows.length}</span>
        </button>
      </div>

      {/* Translation table */}
      <section className="table-card" aria-label={t("translations_table", "Translations table")}>
        <div className="table-head users-table-head">
          <strong>
            {activeTab === "categories"
              ? t("category_translations", "Category Translations")
              : t("promotion_translations", "Promotion Package Translations")}
          </strong>
          {hasDirtyRows ? (
            <span className="l10n-unsaved-hint">
              {t("unsaved_changes", "You have unsaved changes")}
            </span>
          ) : null}
        </div>

        <div className="users-table-wrap">
          <table className="users-table l10n-table">
            <thead>
              <tr>
                <th style={{ width: "30%" }}>
                  {activeTab === "categories"
                    ? t("col_category", "Category")
                    : t("col_package", "Package")}
                </th>
                <th style={{ width: "30%" }}>
                  {t("col_english", "English")}
                </th>
                <th style={{ width: "30%" }}>
                  {t("col_russian", "Русский")}
                </th>
                <th style={{ width: "10%" }}>{t("col_actions", "")}</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={4} className="users-empty-cell">
                    {t("loading", "Loading...")}
                  </td>
                </tr>
              ) : currentRows.length === 0 ? (
                <tr>
                  <td colSpan={4} className="users-empty-cell">
                    {activeTab === "categories"
                      ? t("no_categories", "No categories found. Create categories first.")
                      : t("no_packages", "No promotion packages found. Create packages first.")}
                  </td>
                </tr>
              ) : (
                currentRows.map((row) => (
                  <tr key={row.entityId}>
                    <td>
                      <div className="l10n-entity-label">{row.entityLabel}</div>
                    </td>
                    <td>
                      <input
                        className="l10n-input"
                        type="text"
                        value={row.en}
                        placeholder="English name..."
                        onChange={(e) =>
                          updateRow(activeTab, row.entityId, "en", e.target.value)
                        }
                      />
                    </td>
                    <td>
                      <input
                        className="l10n-input"
                        type="text"
                        value={row.ru}
                        placeholder="Русское название..."
                        onChange={(e) =>
                          updateRow(activeTab, row.entityId, "ru", e.target.value)
                        }
                      />
                    </td>
                    <td>
                      <button
                        type="button"
                        className={`btn ${row.enDirty || row.ruDirty ? "btn-primary" : "btn-ghost"}`}
                        disabled={row.saving || (!row.enDirty && !row.ruDirty)}
                        onClick={() => void saveRow(activeTab, row.entityId)}
                      >
                        {row.saving
                          ? t("saving", "Saving...")
                          : t("save", "Save")}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Help section */}
      <div className="l10n-help-card">
        <strong>{t("how_it_works", "How it works")}</strong>
        <p>
          {t(
            "help_text",
            "Enter translated names for each entity. English names are used as default. Russian translations will be shown to users who select Russian as their preferred language. Click Save to apply changes — they take effect immediately."
          )}
        </p>
      </div>
    </section>
  );
}
