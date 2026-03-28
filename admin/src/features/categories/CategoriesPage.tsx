import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { useAuth } from "../../app/auth/AuthContext";
import { usePageI18n } from "../../app/i18n/I18nContext";
import { formatDateTime } from "../../shared/i18n/format";
import { Modal } from "../common/Modal";

type CategoryAttributeDefinition = {
  key: string;
  label: string;
  value_type: "string" | "integer" | "number" | "boolean";
  required: boolean;
  min_value?: number | null;
  max_value?: number | null;
  min_length?: number | null;
  max_length?: number | null;
  options?: string[] | null;
};

type CategoryItem = {
  id: number;
  name: string;
  is_active: boolean;
  attributes_schema: CategoryAttributeDefinition[] | null;
  created_at: string;
};

type CategoryListResponse = {
  items: CategoryItem[];
};

type CategoryAttributeDraft = {
  id: number;
  key: string;
  label: string;
  value_type: "string" | "integer" | "number" | "boolean";
  required: boolean;
  min_value: string;
  max_value: string;
  optionsValues: string[];
};

type CategoryFormState = {
  name: string;
  isActive: boolean;
  attributesSchema: CategoryAttributeDraft[];
};

function buildEmptyAttributeDraft(id: number, existingKey?: string): CategoryAttributeDraft {
  return {
    id,
    key: existingKey ?? `field_${id}`,
    label: "",
    value_type: "string",
    required: false,
    min_value: "",
    max_value: "",
    optionsValues: [""],
  };
}

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed";
}

function buildInitialFormState(): CategoryFormState {
  return {
    name: "",
    isActive: true,
    attributesSchema: [],
  };
}

function normalizeSlug(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-_]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-");
}

function toDraftAttributes(source: CategoryAttributeDefinition[] | null): CategoryAttributeDraft[] {
  return (source ?? []).map((item, index) => ({
    id: index + 1,
    key: item.key ?? `field_${index + 1}`,
    label: item.label ?? "",
    value_type: item.value_type ?? "string",
    required: Boolean(item.required),
    min_value: item.min_value != null ? String(item.min_value) : "",
    max_value: item.max_value != null ? String(item.max_value) : "",
    optionsValues: (() => {
      const base = Array.isArray(item.options) ? item.options.slice(0, 10) : [];
      return base.length < 10 ? [...base, ""] : base;
    })(),
  }));
}

function getNextFieldId(drafts: CategoryAttributeDraft[]): number {
  return drafts.reduce((max, item) => Math.max(max, item.id), 0) + 1;
}

function parseOptionalNumber(value: string, t: (key: string, fallback: string) => string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const numeric = Number(trimmed);
  if (!Number.isFinite(numeric)) {
    throw new Error(t("error_numeric_boundaries", "Numeric boundaries must be valid numbers"));
  }
  return numeric;
}

function normalizeAttributesSchema(
  drafts: CategoryAttributeDraft[],
  t: (key: string, fallback: string) => string,
): CategoryAttributeDefinition[] | null {
  const cleaned: CategoryAttributeDefinition[] = [];

  for (const draft of drafts) {
    const key = draft.key.trim() || `field_${draft.id}`;
    const label = draft.label.trim();
    const type = draft.value_type;

    if (!label) {
      continue;
    }

    const minValue = parseOptionalNumber(draft.min_value, t);
    const maxValue = parseOptionalNumber(draft.max_value, t);
    const options = type === "string"
      ? draft.optionsValues
          .map((part) => part.trim())
          .filter((part) => part.length > 0)
      : [];

    if (minValue !== null && maxValue !== null && minValue > maxValue) {
      throw new Error(`${t("error_min_greater_than_max", "Min value cannot be greater than max value")} (${label})`);
    }

    const normalized: CategoryAttributeDefinition = {
      key,
      label,
      value_type: type,
      required: Boolean(draft.required),
    };

    if (type === "number" || type === "integer") {
      normalized.min_value = minValue;
      normalized.max_value = maxValue;
    }
    if (type === "string") {
      normalized.min_length = 1;
      normalized.max_length = 35;
      normalized.options = options.length > 0 ? options : null;
    }

    cleaned.push(normalized);
  }

  const seen = new Set<string>();
  for (const item of cleaned) {
    if (seen.has(item.key)) {
      throw new Error(`${t("error_duplicate_field_key", "Duplicate field key")}: '${item.key}'`);
    }
    seen.add(item.key);
  }

  return cleaned.length > 0 ? cleaned : null;
}

export function CategoriesPage() {
  const { authFetch } = useAuth();
  const { t, language } = usePageI18n("categories");

  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showInactive, setShowInactive] = useState(true);
  const [query, setQuery] = useState("");

  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [formState, setFormState] = useState<CategoryFormState>(buildInitialFormState());
  const [nextFieldId, setNextFieldId] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [isActionBusyCategoryId, setIsActionBusyCategoryId] = useState<number | null>(null);

  const selectedCategory = useMemo(
    () => categories.find((item) => item.id === selectedCategoryId) ?? null,
    [categories, selectedCategoryId],
  );

  const loadCategories = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set("include_inactive", showInactive ? "true" : "false");

      const response = await authFetch(`/categories/admin?${params.toString()}`);
      if (!response.ok) {
        throw new Error(t("error_load_categories", "Failed to load categories"));
      }

      const payload = (await response.json()) as CategoryListResponse;
      setCategories(payload.items);

      setSelectedCategoryId((previous) => {
        if (payload.items.length === 0) {
          return null;
        }

        const previousVisible = previous !== null && payload.items.some((item) => item.id === previous);
        return previousVisible ? previous : payload.items[0].id;
      });
    } catch (loadError) {
      setError(extractErrorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, [authFetch, showInactive, t]);

  useEffect(() => {
    void loadCategories();
  }, [loadCategories]);

  useEffect(() => {
    if (!selectedCategory) {
      setFormState(buildInitialFormState());
      setNextFieldId(1);
      return;
    }

    const draftAttributes = toDraftAttributes(selectedCategory.attributes_schema);

    setFormState({
      name: selectedCategory.name,
      isActive: selectedCategory.is_active,
      attributesSchema: draftAttributes,
    });
    setNextFieldId(getNextFieldId(draftAttributes));
  }, [selectedCategory]);

  const filteredRows = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) {
      return categories;
    }

    return categories.filter((item) => {
      const source = item.name.toLowerCase();
      return source.includes(term);
    });
  }, [categories, query]);

  const resetCreateForm = () => {
    setSelectedCategoryId(null);
    setFormState(buildInitialFormState());
    setNextFieldId(1);
    setIsFormModalOpen(true);
  };

  const applyActivationToggle = async (category: CategoryItem) => {
    const actionPath = category.is_active ? "deactivate" : "activate";
    const actionLabel = category.is_active ? t("deactivate", "Deactivate") : t("activate", "Activate");

    const confirmed = window.confirm(`${actionLabel} ${t("category", "category")} '${category.name}'?`);
    if (!confirmed) {
      return;
    }

    setIsActionBusyCategoryId(category.id);
    setError(null);

    try {
      const response = await authFetch(`/categories/${category.id}/${actionPath}`, {
        method: "POST",
      });

      if (!response.ok) {
        let message = t("error_action_category", "Failed to change category status");
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = t("error_action_category", "Failed to change category status");
        }
        throw new Error(message);
      }

      const updated = (await response.json()) as CategoryItem;

      setCategories((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      if (selectedCategoryId === updated.id) {
        setFormState((prev) => ({ ...prev, isActive: updated.is_active }));
      }
    } catch (actionError) {
      setError(extractErrorMessage(actionError));
    } finally {
      setIsActionBusyCategoryId(null);
    }
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setIsSubmitting(true);
    setError(null);

    try {
      const attributesSchema = normalizeAttributesSchema(formState.attributesSchema, t);

      const isEditMode = selectedCategory !== null;
      const slug = normalizeSlug(formState.name);

      const basePayload = {
        name: formState.name.trim(),
        slug,
        is_active: formState.isActive,
        attributes_schema: attributesSchema,
      };
      const payload = basePayload;

      if (!payload.name || payload.name.length < 2) {
        throw new Error(t("error_name_min_length", "Name must be at least 2 characters"));
      }
      if (!payload.slug || payload.slug.length < 2) {
        throw new Error(t("error_name_slug", "Name should contain at least 2 latin letters or digits"));
      }

      const path = isEditMode ? `/categories/${selectedCategory.id}` : "/categories";
      const method = isEditMode ? "PATCH" : "POST";

      const response = await authFetch(path, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        let message = t("error_save_category", "Failed to save category");
        try {
          const body = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof body?.error?.message === "string") {
            message = body.error.message;
          } else if (typeof body?.detail === "string") {
            message = body.detail;
          }
        } catch {
          message = t("error_save_category", "Failed to save category");
        }
        throw new Error(message);
      }

      const saved = (await response.json()) as CategoryItem;

      setCategories((prev) => {
        if (isEditMode) {
          return prev.map((item) => (item.id === saved.id ? saved : item));
        }
        return [...prev, saved];
      });
      setSelectedCategoryId(saved.id);
      setIsFormModalOpen(false);
    } catch (submitError) {
      setError(extractErrorMessage(submitError));
    } finally {
      setIsSubmitting(false);
    }
  };

  const addField = () => {
    setFormState((prev) => ({
      ...prev,
      attributesSchema: [...prev.attributesSchema, buildEmptyAttributeDraft(nextFieldId)],
    }));
    setNextFieldId((prev) => prev + 1);
  };

  const updateField = (index: number, patch: Partial<CategoryAttributeDraft>) => {
    setFormState((prev) => ({
      ...prev,
      attributesSchema: prev.attributesSchema.map((item, currentIndex) =>
        currentIndex === index ? { ...item, ...patch } : item,
      ),
    }));
  };

  const updateOptionValue = (fieldIndex: number, optionIndex: number, value: string) => {
    setFormState((prev) => {
      const attributesSchema = prev.attributesSchema.map((item, currentIndex) => {
        if (currentIndex !== fieldIndex) {
          return item;
        }

        const optionsValues = [...item.optionsValues];
        optionsValues[optionIndex] = value;

        if (
          optionIndex === optionsValues.length - 1
          && value.trim().length > 0
          && optionsValues.length < 10
        ) {
          optionsValues.push("");
        }

        return {
          ...item,
          optionsValues,
        };
      });

      return {
        ...prev,
        attributesSchema,
      };
    });
  };

  const removeOptionValue = (fieldIndex: number, optionIndex: number) => {
    setFormState((prev) => {
      const attributesSchema = prev.attributesSchema.map((item, currentIndex) => {
        if (currentIndex !== fieldIndex) {
          return item;
        }

        const filtered = item.optionsValues.filter((_, index) => index !== optionIndex);
        if (filtered.length === 0) {
          filtered.push("");
        }

        return {
          ...item,
          optionsValues: filtered,
        };
      });

      return {
        ...prev,
        attributesSchema,
      };
    });
  };

  const removeField = (index: number) => {
    setFormState((prev) => ({
      ...prev,
      attributesSchema: prev.attributesSchema.filter((_, currentIndex) => currentIndex !== index),
    }));
  };

  const moveField = (index: number, direction: -1 | 1) => {
    setFormState((prev) => {
      const target = index + direction;
      if (target < 0 || target >= prev.attributesSchema.length) {
        return prev;
      }

      const clone = [...prev.attributesSchema];
      const temp = clone[index];
      clone[index] = clone[target];
      clone[target] = temp;

      return {
        ...prev,
        attributesSchema: clone,
      };
    });
  };

  return (
    <section className="module-page">
      <header className="module-header">
        <div>
          <h1>{t("title", "Categories")}</h1>
          <p>{t("subtitle", "Manage category metadata, active state, and dynamic listing fields with a visual builder.")}</p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={() => void loadCategories()} disabled={isLoading}>
          {isLoading ? t("refreshing", "Refreshing...") : t("refresh", "Refresh")}
        </button>
      </header>

      {error ? <div className="dashboard-error">{error}</div> : null}

      <div className="search-strip categories-search-strip">
        <input
          placeholder={t("search_placeholder", "Search by category name")}
          aria-label={t("search_categories", "Search categories")}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <label className="categories-checkbox-label">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(event) => setShowInactive(event.target.checked)}
          />
          {t("include_inactive", "Include inactive")}
        </label>
        <button type="button" className="btn btn-ghost" onClick={resetCreateForm}>
          {t("new_category", "New category")}
        </button>
      </div>

      <section className="table-card" aria-label={t("table_categories", "Categories")}> 
        <div className="table-head users-table-head">
          <strong>{t("table_categories", "Categories")}</strong>
          <span>{filteredRows.length} {t("total", "total")}</span>
        </div>

        <div className="categories-table-wrap">
          <table className="categories-table">
            <thead>
              <tr>
                <th>{t("name", "Name")}</th>
                <th>{t("attributes", "Attributes")}</th>
                <th>{t("status", "Status")}</th>
                <th>{t("created", "Created")}</th>
                <th>{t("actions", "Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="users-empty-cell">
                    {isLoading ? t("loading_categories", "Loading categories...") : t("no_categories_found", "No categories found")}
                  </td>
                </tr>
              ) : (
                filteredRows.map((category) => (
                  <tr key={category.id}>
                    <td>{category.name}</td>
                    <td>{category.attributes_schema?.length ?? 0}</td>
                    <td>
                      <span className={`users-status-badge ${category.is_active ? "users-status-active" : "users-status-deactivated"}`}>
                        {category.is_active ? t("active", "Active") : t("inactive", "Inactive")}
                      </span>
                    </td>
                    <td>{formatDateTime(category.created_at, language)}</td>
                    <td>
                      <div className="users-actions-cell">
                        <button
                          type="button"
                          className="btn btn-ghost"
                          onClick={() => {
                            const draftAttributes = toDraftAttributes(category.attributes_schema);
                            setFormState({
                              name: category.name,
                              isActive: category.is_active,
                              attributesSchema: draftAttributes,
                            });
                            setNextFieldId(getNextFieldId(draftAttributes));
                            setSelectedCategoryId(category.id);
                            setIsFormModalOpen(true);
                          }}
                        >
                          {t("edit", "Edit")}
                        </button>
                        <button
                          type="button"
                          className="btn btn-primary"
                          disabled={isActionBusyCategoryId === category.id}
                          onClick={() => void applyActivationToggle(category)}
                        >
                          {isActionBusyCategoryId === category.id
                            ? t("processing", "Processing...")
                            : category.is_active
                              ? t("deactivate", "Deactivate")
                              : t("activate", "Activate")}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <Modal
        open={isFormModalOpen}
        onClose={() => setIsFormModalOpen(false)}
        title={selectedCategory ? t("edit_category", "Edit category") : t("create_category", "Create category")}
        subtitle={selectedCategory ? `${t("category", "Category")} #${selectedCategory.id}` : t("new", "New")}
      >
        <div className="users-detail-body">
          <form className="reports-form" onSubmit={onSubmit}>
            <div className="reports-form-grid">
              <label>
                {t("name", "Name")}
                <input
                  value={formState.name}
                  onChange={(event) => setFormState((prev) => ({ ...prev, name: event.target.value }))}
                  required
                  minLength={2}
                />
              </label>
            </div>

            <div className="reports-form-grid">
              <label className="categories-checkbox-label categories-form-checkbox">
                <input
                  type="checkbox"
                  checked={formState.isActive}
                  onChange={(event) => setFormState((prev) => ({ ...prev, isActive: event.target.checked }))}
                />
                {t("active", "Active")}
              </label>
            </div>

            <section className="categories-builder" aria-label={t("dynamic_fields_builder", "Dynamic fields builder")}> 
              <div className="table-head categories-builder-head">
                <strong>{t("dynamic_fields_builder", "Dynamic fields builder")}</strong>
                <button type="button" className="btn btn-ghost" onClick={addField}>{t("add_field", "Add field")}</button>
              </div>

              <div className="categories-builder-list">
                {formState.attributesSchema.length === 0 ? (
                  <p className="categories-empty-builder">
                    {t("no_dynamic_fields", "No dynamic fields yet. Click Add field to configure attributes for listings in this category.")}
                  </p>
                ) : (
                  formState.attributesSchema.map((attribute, index) => (
                    <article key={attribute.id} className="categories-attr-row">
                      <div className="categories-attr-row-head">
                        <strong>{t("field", "Field")} {index + 1}</strong>
                        <div className="users-actions-cell">
                          <button
                            type="button"
                            className="btn btn-ghost"
                            disabled={index === 0}
                            onClick={() => moveField(index, -1)}
                          >
                            {t("up", "Up")}
                          </button>
                          <button
                            type="button"
                            className="btn btn-ghost"
                            disabled={index === formState.attributesSchema.length - 1}
                            onClick={() => moveField(index, 1)}
                          >
                            {t("down", "Down")}
                          </button>
                          <button type="button" className="btn btn-primary" onClick={() => removeField(index)}>
                            {t("remove", "Remove")}
                          </button>
                        </div>
                      </div>

                      <div className="categories-attr-grid">
                        <label>
                          {t("label", "Label")}
                          <input
                            value={attribute.label}
                            placeholder={t("label_placeholder", "Rooms count")}
                            onChange={(event) => updateField(index, { label: event.target.value })}
                          />
                        </label>

                        <label>
                          {t("type", "Type")}
                          <select
                            className="users-filter-select"
                            value={attribute.value_type}
                            onChange={(event) => updateField(index, { value_type: event.target.value as CategoryAttributeDraft["value_type"] })}
                          >
                            <option value="string">{t("type_text", "Text")}</option>
                            <option value="integer">{t("type_integer", "Integer")}</option>
                            <option value="number">{t("type_decimal", "Decimal")}</option>
                            <option value="boolean">{t("type_yes_no", "Yes / No")}</option>
                          </select>
                        </label>

                        <label className="categories-checkbox-label categories-field-required">
                          <input
                            type="checkbox"
                            checked={attribute.required}
                            onChange={(event) => updateField(index, { required: event.target.checked })}
                          />
                          {t("required", "Required")}
                        </label>

                        {attribute.value_type === "string" ? (
                          <>
                            <label className="categories-options-field">
                              {t("options_help", "Options (optional, type one option per field, max 10)")}
                              <div className="categories-options-list">
                                {attribute.optionsValues.map((optionValue, optionIndex) => {
                                  const isLast = optionIndex === attribute.optionsValues.length - 1;
                                  const canRemove = attribute.optionsValues.length > 1 || optionValue.trim().length > 0;

                                  return (
                                    <div key={`${attribute.id}-option-${optionIndex}`} className="categories-option-row">
                                      <input
                                        className="categories-options-input"
                                        value={optionValue}
                                        placeholder={`${t("option", "Option")} ${optionIndex + 1}`}
                                        onChange={(event) => updateOptionValue(index, optionIndex, event.target.value)}
                                      />
                                      <button
                                        type="button"
                                        className="btn btn-ghost categories-option-remove"
                                        onClick={() => removeOptionValue(index, optionIndex)}
                                        disabled={!canRemove || (isLast && optionValue.trim().length === 0 && attribute.optionsValues.length === 1)}
                                      >
                                        {t("remove", "Remove")}
                                      </button>
                                    </div>
                                  );
                                })}
                              </div>
                            </label>
                          </>
                        ) : null}

                        {attribute.value_type === "integer" || attribute.value_type === "number" ? (
                          <>
                            <label>
                              {t("min_value", "Min value")}
                              <input
                                type="number"
                                value={attribute.min_value}
                                onChange={(event) => updateField(index, { min_value: event.target.value })}
                              />
                            </label>

                            <label>
                              {t("max_value", "Max value")}
                              <input
                                type="number"
                                value={attribute.max_value}
                                onChange={(event) => updateField(index, { max_value: event.target.value })}
                              />
                            </label>
                          </>
                        ) : null}
                      </div>
                    </article>
                  ))
                )}
              </div>
            </section>

            <div className="users-actions-cell">
              <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                {isSubmitting ? t("saving", "Saving...") : selectedCategory ? t("save", "Save changes") : t("create", "Create category")}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => {
                  if (selectedCategory) {
                    const draftAttributes = toDraftAttributes(selectedCategory.attributes_schema);
                    setFormState({
                      name: selectedCategory.name,
                      isActive: selectedCategory.is_active,
                      attributesSchema: draftAttributes,
                    });
                    setNextFieldId(getNextFieldId(draftAttributes));
                    return;
                  }
                  setFormState(buildInitialFormState());
                  setNextFieldId(1);
                }}
              >
                {t("reset_form", "Reset form")}
              </button>
            </div>
          </form>
        </div>
      </Modal>
    </section>
  );
}
