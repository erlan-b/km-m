import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "../../app/auth/AuthContext";
import { usePageI18n } from "../../app/i18n/I18nContext";

type CategoryItem = {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  attributes_schema: CategoryAttributeDefinition[] | null;
};

type CategoryAttributeDefinition = {
  key: string;
  label: string;
  value_type: "string" | "integer" | "number" | "boolean";
  required: boolean;
  options?: string[] | null;
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
  rowId: string;
  pageKey: "categories" | "promotions";
  textKey: string;
  entityLabel: string;
  fieldLabel: string;
  en: string;
  ru: string;
  enDirty: boolean;
  ruDirty: boolean;
  saving: boolean;
};

type SupportedLanguage = "en" | "ru";
type TranslationDirection = "en_to_ru" | "ru_to_en";
type LocalizationTab = "categories" | "promotions";

type I18nEntryItem = {
  id: number;
  page_key: string;
  text_key: string;
  language: string;
  text_value: string;
  is_active: boolean;
};

type I18nEntryListResponse = {
  items: I18nEntryItem[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
};

type EntryIndex = Record<string, number>;

const DIRTY_KEY_BY_LANGUAGE: Record<SupportedLanguage, "enDirty" | "ruDirty"> = {
  en: "enDirty",
  ru: "ruDirty",
};

function buildEntryIndexKey(pageKey: string, textKey: string, language: SupportedLanguage): string {
  return `${pageKey}::${textKey}::${language}`;
}

function normalizeTextKeyPart(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "")
    || "field";
}

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "Request failed";
}

export function LocalizationPage() {
  const { authFetch } = useAuth();
  const { t } = usePageI18n("localization_admin");

  const [activeTab, setActiveTab] = useState<LocalizationTab>("categories");
  const [translationDirection, setTranslationDirection] = useState<TranslationDirection>("en_to_ru");
  const [categoryRows, setCategoryRows] = useState<TranslationRow[]>([]);
  const [promoRows, setPromoRows] = useState<TranslationRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const entryIndexRef = useRef<EntryIndex>({});

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const [catRes, promoRes] = await Promise.all([
        authFetch("/categories/admin?include_inactive=true"),
        authFetch("/promotions/packages/admin"),
      ]);

      if (!catRes.ok || !promoRes.ok) {
        throw new Error("Failed to load data");
      }

      const categories = ((await catRes.json()) as { items: CategoryItem[] }).items;
      const promoPackages = ((await promoRes.json()) as { items: PromotionPackageItem[] }).items;
      const i18nEntries: I18nEntryItem[] = [];
      let page = 1;

      while (true) {
        const i18nRes = await authFetch(`/i18n/admin/entries?page=${page}&page_size=100&include_inactive=true`);
        if (!i18nRes.ok) {
          throw new Error("Failed to load localization entries");
        }

        const payload = (await i18nRes.json()) as I18nEntryListResponse;
        i18nEntries.push(...payload.items);

        if (payload.total_pages === 0 || page >= payload.total_pages) {
          break;
        }
        page += 1;
      }

      // Build lookup: page_key -> text_key -> language -> value
      const lookup = new Map<string, Map<string, Map<SupportedLanguage, string>>>();
      const entryIndex: EntryIndex = {};

      for (const entry of i18nEntries) {
        const lang = entry.language === "ru" ? "ru" : "en";
        if (!lookup.has(entry.page_key)) lookup.set(entry.page_key, new Map());
        const pageMap = lookup.get(entry.page_key)!;
        if (!pageMap.has(entry.text_key)) pageMap.set(entry.text_key, new Map());
        pageMap.get(entry.text_key)!.set(lang, entry.text_value);
        entryIndex[buildEntryIndexKey(entry.page_key, entry.text_key, lang)] = entry.id;
      }
      entryIndexRef.current = entryIndex;

      const getTranslation = (pageKey: string, textKey: string, lang: SupportedLanguage): string => {
        return lookup.get(pageKey)?.get(textKey)?.get(lang) ?? "";
      };

      const categoryTranslationRows: TranslationRow[] = [];
      for (const cat of categories) {
        const entityLabel = `${cat.name} (${cat.slug})`;
        const categoryNameTextKey = `category_${cat.id}_name`;

        categoryTranslationRows.push({
          rowId: `category-${cat.id}-name`,
          pageKey: "categories",
          textKey: categoryNameTextKey,
          entityLabel,
          fieldLabel: t("field_category_name", "Category name"),
          en: getTranslation("categories", categoryNameTextKey, "en") || cat.name,
          ru: getTranslation("categories", categoryNameTextKey, "ru"),
          enDirty: false,
          ruDirty: false,
          saving: false,
        });

        for (const [attributeIndex, attribute] of (cat.attributes_schema ?? []).entries()) {
          const rawAttributeKey = attribute.key?.trim() || `field_${attributeIndex + 1}`;
          const normalizedAttributeKey = normalizeTextKeyPart(rawAttributeKey);
          const attributeLabelTextKey = `category_${cat.id}_attr_${normalizedAttributeKey}_label`;
          const fallbackAttributeLabel = attribute.label?.trim() ?? "";
          const enAttributeLabel = getTranslation("categories", attributeLabelTextKey, "en") || fallbackAttributeLabel;
          const ruAttributeLabel = getTranslation("categories", attributeLabelTextKey, "ru");

          if (enAttributeLabel || ruAttributeLabel) {
            categoryTranslationRows.push({
              rowId: `category-${cat.id}-attr-${normalizedAttributeKey}-label`,
              pageKey: "categories",
              textKey: attributeLabelTextKey,
              entityLabel,
              fieldLabel: `${t("field_attribute_label", "Attribute label")} (${rawAttributeKey})`,
              en: enAttributeLabel,
              ru: ruAttributeLabel,
              enDirty: false,
              ruDirty: false,
              saving: false,
            });
          }

          const options = Array.isArray(attribute.options) ? attribute.options : [];
          options.forEach((optionValue, optionIndex) => {
            const optionTextKey = `category_${cat.id}_attr_${normalizedAttributeKey}_option_${optionIndex + 1}`;
            const fallbackOptionText = optionValue.trim();
            const enOption = getTranslation("categories", optionTextKey, "en") || fallbackOptionText;
            const ruOption = getTranslation("categories", optionTextKey, "ru");

            if (!enOption && !ruOption) {
              return;
            }

            categoryTranslationRows.push({
              rowId: `category-${cat.id}-attr-${normalizedAttributeKey}-option-${optionIndex + 1}`,
              pageKey: "categories",
              textKey: optionTextKey,
              entityLabel,
              fieldLabel: `${t("field_attribute_option", "Attribute option")} ${optionIndex + 1} (${rawAttributeKey})`,
              en: enOption,
              ru: ruOption,
              enDirty: false,
              ruDirty: false,
              saving: false,
            });
          });
        }
      }
      setCategoryRows(categoryTranslationRows);

      const promotionTranslationRows: TranslationRow[] = [];
      for (const pkg of promoPackages) {
        const entityLabel = `${pkg.title} (#${pkg.id})`;

        const titleTextKey = `package_${pkg.id}_title`;
        promotionTranslationRows.push({
          rowId: `package-${pkg.id}-title`,
          pageKey: "promotions",
          textKey: titleTextKey,
          entityLabel,
          fieldLabel: t("field_package_title", "Package title"),
          en: getTranslation("promotions", titleTextKey, "en") || pkg.title,
          ru: getTranslation("promotions", titleTextKey, "ru"),
          enDirty: false,
          ruDirty: false,
          saving: false,
        });

        const descriptionTextKey = `package_${pkg.id}_description`;
        const fallbackDescription = (pkg.description ?? "").trim();
        const enDescription = getTranslation("promotions", descriptionTextKey, "en") || fallbackDescription;
        const ruDescription = getTranslation("promotions", descriptionTextKey, "ru");
        if (enDescription || ruDescription) {
          promotionTranslationRows.push({
            rowId: `package-${pkg.id}-description`,
            pageKey: "promotions",
            textKey: descriptionTextKey,
            entityLabel,
            fieldLabel: t("field_package_description", "Package description"),
            en: enDescription,
            ru: ruDescription,
            enDirty: false,
            ruDirty: false,
            saving: false,
          });
        }
      }
      setPromoRows(promotionTranslationRows);
    } catch (loadError) {
      setError(extractErrorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, [authFetch, t]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const sourceLanguage: SupportedLanguage = translationDirection === "en_to_ru" ? "en" : "ru";
  const targetLanguage: SupportedLanguage = sourceLanguage === "en" ? "ru" : "en";
  const targetDirtyKey = DIRTY_KEY_BY_LANGUAGE[targetLanguage];

  const updateRow = (
    tab: LocalizationTab,
    rowId: string,
    lang: SupportedLanguage,
    value: string,
  ) => {
    const setter = tab === "categories" ? setCategoryRows : setPromoRows;
    const dirtyKey = DIRTY_KEY_BY_LANGUAGE[lang];

    setter((prev) =>
      prev.map((row) =>
        row.rowId === rowId
          ? { ...row, [lang]: value, [dirtyKey]: true }
          : row
      )
    );
  };

  const upsertEntry = useCallback(
    async (
      pageKey: "categories" | "promotions",
      textKey: string,
      language: SupportedLanguage,
      textValue: string,
    ) => {
      const entryKey = buildEntryIndexKey(pageKey, textKey, language);
      const existingId = entryIndexRef.current[entryKey];

      if (existingId) {
        const response = await authFetch(`/i18n/admin/entries/${existingId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text_value: textValue, is_active: true }),
        });
        if (!response.ok) {
          throw new Error("Failed to update translation");
        }
        return;
      }

      const response = await authFetch("/i18n/admin/entries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          page_key: pageKey,
          text_key: textKey,
          language,
          text_value: textValue,
          is_active: true,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to create translation");
      }

      const created = (await response.json()) as I18nEntryItem;
      entryIndexRef.current[entryKey] = created.id;
    },
    [authFetch],
  );

  const saveRow = async (tab: LocalizationTab, rowId: string) => {
    const rows = tab === "categories" ? categoryRows : promoRows;
    const row = rows.find((item) => item.rowId === rowId);
    if (!row) return;

    const setter = tab === "categories" ? setCategoryRows : setPromoRows;
    setter((prev) =>
      prev.map((item) => (item.rowId === rowId ? { ...item, saving: true } : item))
    );
    setError(null);
    setSuccessMessage(null);

    try {
      const value = row[targetLanguage].trim();
      if (!value) {
        throw new Error(t("target_translation_required", "Target translation cannot be empty"));
      }

      await upsertEntry(row.pageKey, row.textKey, targetLanguage, value);

      setter((prev) =>
        prev.map((item) =>
          item.rowId === rowId
            ? { ...item, saving: false, [targetDirtyKey]: false }
            : item
        )
      );
      setSuccessMessage(t("saved_successfully", "Translation saved successfully"));
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (saveError) {
      setError(extractErrorMessage(saveError));
      setter((prev) =>
        prev.map((item) => (item.rowId === rowId ? { ...item, saving: false } : item))
      );
    }
  };

  const currentRows = activeTab === "categories" ? categoryRows : promoRows;
  const hasDirtyRows = currentRows.some((row) => row.enDirty || row.ruDirty);

  const sourceColumnTitle = useMemo(
    () => (
      sourceLanguage === "en"
        ? t("source_language_en", "Source (English)")
        : t("source_language_ru", "Source (Русский)")
    ),
    [sourceLanguage, t],
  );

  const targetColumnTitle = useMemo(
    () => (
      targetLanguage === "en"
        ? t("target_language_en", "Target (English)")
        : t("target_language_ru", "Target (Русский)")
    ),
    [targetLanguage, t],
  );

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

      <div className="l10n-controls">
        <label className="l10n-direction-control">
          {t("translation_direction", "Translation direction")}
          <select
            className="users-filter-select"
            value={translationDirection}
            onChange={(event) => setTranslationDirection(event.target.value as TranslationDirection)}
          >
            <option value="en_to_ru">EN -&gt; RU</option>
            <option value="ru_to_en">RU -&gt; EN</option>
          </select>
        </label>
      </div>

      {/* Tabs */}
      <div className="l10n-tabs">
        <button
          type="button"
          className={`l10n-tab ${activeTab === "categories" ? "l10n-tab-active" : ""}`}
          onClick={() => setActiveTab("categories")}
        >
          {t("tab_categories", "Category Fields")}
          <span className="l10n-tab-count">{categoryRows.length}</span>
        </button>
        <button
          type="button"
          className={`l10n-tab ${activeTab === "promotions" ? "l10n-tab-active" : ""}`}
          onClick={() => setActiveTab("promotions")}
        >
          {t("tab_promotions", "Promotion Package Fields")}
          <span className="l10n-tab-count">{promoRows.length}</span>
        </button>
      </div>

      {/* Translation table */}
      <section className="table-card" aria-label={t("translations_table", "Translations table")}>
        <div className="table-head users-table-head">
          <strong>
            {activeTab === "categories"
              ? t("category_translations", "Category Field Translations")
              : t("promotion_translations", "Promotion Package Field Translations")}
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
                <th style={{ width: "24%" }}>
                  {activeTab === "categories"
                    ? t("col_category", "Category")
                    : t("col_package", "Package")}
                </th>
                <th style={{ width: "26%" }}>
                  {t("col_field", "Field")}
                </th>
                <th style={{ width: "20%" }}>
                  {sourceColumnTitle}
                </th>
                <th style={{ width: "20%" }}>
                  {targetColumnTitle}
                </th>
                <th style={{ width: "10%" }}>{t("col_actions", "")}</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="users-empty-cell">
                    {t("loading", "Loading...")}
                  </td>
                </tr>
              ) : currentRows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="users-empty-cell">
                    {activeTab === "categories"
                      ? t("no_categories", "No categories found. Create categories first.")
                      : t("no_packages", "No promotion packages found. Create packages first.")}
                  </td>
                </tr>
              ) : (
                currentRows.map((row) => (
                  <tr key={row.rowId}>
                    <td>
                      <div className="l10n-entity-label">{row.entityLabel}</div>
                    </td>
                    <td>
                      <div className="l10n-field-label">{row.fieldLabel}</div>
                    </td>
                    <td>
                      <input
                        className="l10n-input"
                        type="text"
                        value={row[sourceLanguage]}
                        placeholder={sourceLanguage === "en" ? "English source..." : "Русский источник..."}
                        readOnly
                        disabled
                      />
                    </td>
                    <td>
                      <input
                        className="l10n-input"
                        type="text"
                        value={row[targetLanguage]}
                        placeholder={targetLanguage === "en" ? "English translation..." : "Русский перевод..."}
                        onChange={(e) =>
                          updateRow(activeTab, row.rowId, targetLanguage, e.target.value)
                        }
                      />
                    </td>
                    <td>
                      <button
                        type="button"
                        className={`btn ${row[targetDirtyKey] ? "btn-primary" : "btn-ghost"}`}
                        disabled={row.saving || !row[targetDirtyKey]}
                        onClick={() => void saveRow(activeTab, row.rowId)}
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
    </section>
  );
}
