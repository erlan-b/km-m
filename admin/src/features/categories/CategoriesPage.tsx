import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { useAuth } from "../../app/auth/AuthContext";

type CategoryAttributeDefinition = {
  key: string;
  label: string;
  value_type: "string" | "integer" | "number" | "boolean";
  required: boolean;
  min_value?: number | null;
  max_value?: number | null;
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

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
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

function parseOptionalNumber(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const numeric = Number(trimmed);
  if (!Number.isFinite(numeric)) {
    throw new Error("Numeric boundaries must be valid numbers");
  }
  return numeric;
}

function normalizeAttributesSchema(drafts: CategoryAttributeDraft[]): CategoryAttributeDefinition[] | null {
  const cleaned: CategoryAttributeDefinition[] = [];

  for (const draft of drafts) {
    const key = draft.key.trim() || `field_${draft.id}`;
    const label = draft.label.trim();
    const type = draft.value_type;

    if (!label) {
      continue;
    }

    const minValue = parseOptionalNumber(draft.min_value);
    const maxValue = parseOptionalNumber(draft.max_value);
    const options = type === "string"
      ? draft.optionsValues
          .map((part) => part.trim())
          .filter((part) => part.length > 0)
      : [];

    if (minValue !== null && maxValue !== null && minValue > maxValue) {
      throw new Error(`Field '${label}': min value cannot be greater than max value`);
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
      normalized.max_length = 300;
      normalized.options = options.length > 0 ? options : null;
    }

    cleaned.push(normalized);
  }

  const seen = new Set<string>();
  for (const item of cleaned) {
    if (seen.has(item.key)) {
      throw new Error(`Duplicate field key '${item.key}'`);
    }
    seen.add(item.key);
  }

  return cleaned.length > 0 ? cleaned : null;
}

export function CategoriesPage() {
  const { authFetch } = useAuth();

  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showInactive, setShowInactive] = useState(true);
  const [query, setQuery] = useState("");

  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [formState, setFormState] = useState<CategoryFormState>(buildInitialFormState());
  const [nextFieldId, setNextFieldId] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
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
        throw new Error("Failed to load categories");
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
  }, [authFetch, showInactive]);

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
  };

  const applyActivationToggle = async (category: CategoryItem) => {
    const actionPath = category.is_active ? "deactivate" : "activate";
    const actionLabel = category.is_active ? "Deactivate" : "Activate";

    const confirmed = window.confirm(`${actionLabel} category '${category.name}'?`);
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
        let message = `Failed to ${actionPath} category`;
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = `Failed to ${actionPath} category`;
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
      const attributesSchema = normalizeAttributesSchema(formState.attributesSchema);

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
        throw new Error("Name must be at least 2 characters");
      }
      if (!payload.slug || payload.slug.length < 2) {
        throw new Error("Name should contain at least 2 latin letters or digits");
      }

      const path = isEditMode ? `/categories/${selectedCategory.id}` : "/categories";
      const method = isEditMode ? "PATCH" : "POST";

      const response = await authFetch(path, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        let message = `Failed to ${isEditMode ? "update" : "create"} category`;
        try {
          const body = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof body?.error?.message === "string") {
            message = body.error.message;
          } else if (typeof body?.detail === "string") {
            message = body.detail;
          }
        } catch {
          message = `Failed to ${isEditMode ? "update" : "create"} category`;
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
          <h1>Categories</h1>
          <p>Manage category metadata, active state, and dynamic listing fields with a visual builder.</p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={() => void loadCategories()} disabled={isLoading}>
          {isLoading ? "Refreshing..." : "Refresh"}
        </button>
      </header>

      {error ? <div className="dashboard-error">{error}</div> : null}

      <div className="search-strip categories-search-strip">
        <input
          placeholder="Search by category name"
          aria-label="Search categories"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <label className="categories-checkbox-label">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(event) => setShowInactive(event.target.checked)}
          />
          Include inactive
        </label>
        <button type="button" className="btn btn-ghost" onClick={resetCreateForm}>
          New category
        </button>
      </div>

      <section className="table-card" aria-label="Categories table">
        <div className="table-head users-table-head">
          <strong>Categories</strong>
          <span>{filteredRows.length} total</span>
        </div>

        <div className="categories-table-wrap">
          <table className="categories-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Attributes</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="users-empty-cell">
                    {isLoading ? "Loading categories..." : "No categories found"}
                  </td>
                </tr>
              ) : (
                filteredRows.map((category) => (
                  <tr key={category.id}>
                    <td>{category.name}</td>
                    <td>{category.attributes_schema?.length ?? 0}</td>
                    <td>
                      <span className={`users-status-badge ${category.is_active ? "users-status-active" : "users-status-deactivated"}`}>
                        {category.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td>{formatDate(category.created_at)}</td>
                    <td>
                      <div className="users-actions-cell">
                        <button type="button" className="btn btn-ghost" onClick={() => setSelectedCategoryId(category.id)}>
                          Edit
                        </button>
                        <button
                          type="button"
                          className="btn btn-primary"
                          disabled={isActionBusyCategoryId === category.id}
                          onClick={() => void applyActivationToggle(category)}
                        >
                          {isActionBusyCategoryId === category.id
                            ? "Processing..."
                            : category.is_active
                              ? "Deactivate"
                              : "Activate"}
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

      <section className="table-card" aria-label="Category form">
        <div className="table-head">
          <strong>{selectedCategory ? "Edit category" : "Create category"}</strong>
          <span>{selectedCategory ? `Category #${selectedCategory.id}` : "New"}</span>
        </div>

        <div className="users-detail-body">
          <form className="reports-form" onSubmit={onSubmit}>
            <div className="reports-form-grid">
              <label>
                Name
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
                Active
              </label>
            </div>

            <section className="categories-builder" aria-label="Dynamic fields builder">
              <div className="table-head categories-builder-head">
                <strong>Dynamic fields builder</strong>
                <button type="button" className="btn btn-ghost" onClick={addField}>Add field</button>
              </div>

              <div className="categories-builder-list">
                {formState.attributesSchema.length === 0 ? (
                  <p className="categories-empty-builder">
                    No dynamic fields yet. Click Add field to configure attributes for listings in this category.
                  </p>
                ) : (
                  formState.attributesSchema.map((attribute, index) => (
                    <article key={attribute.id} className="categories-attr-row">
                      <div className="categories-attr-row-head">
                        <strong>Field {index + 1}</strong>
                        <div className="users-actions-cell">
                          <button
                            type="button"
                            className="btn btn-ghost"
                            disabled={index === 0}
                            onClick={() => moveField(index, -1)}
                          >
                            Up
                          </button>
                          <button
                            type="button"
                            className="btn btn-ghost"
                            disabled={index === formState.attributesSchema.length - 1}
                            onClick={() => moveField(index, 1)}
                          >
                            Down
                          </button>
                          <button type="button" className="btn btn-primary" onClick={() => removeField(index)}>
                            Remove
                          </button>
                        </div>
                      </div>

                      <div className="categories-attr-grid">
                        <label>
                          Label
                          <input
                            value={attribute.label}
                            placeholder="Rooms count"
                            onChange={(event) => updateField(index, { label: event.target.value })}
                          />
                        </label>

                        <label>
                          Type
                          <select
                            className="users-filter-select"
                            value={attribute.value_type}
                            onChange={(event) => updateField(index, { value_type: event.target.value as CategoryAttributeDraft["value_type"] })}
                          >
                            <option value="string">Text</option>
                            <option value="integer">Integer</option>
                            <option value="number">Decimal</option>
                            <option value="boolean">Yes / No</option>
                          </select>
                        </label>

                        <label className="categories-checkbox-label categories-field-required">
                          <input
                            type="checkbox"
                            checked={attribute.required}
                            onChange={(event) => updateField(index, { required: event.target.checked })}
                          />
                          Required
                        </label>

                        {attribute.value_type === "string" ? (
                          <>
                            <label className="categories-options-field">
                              Options (optional, type one option per field, max 10)
                              <div className="categories-options-list">
                                {attribute.optionsValues.map((optionValue, optionIndex) => {
                                  const isLast = optionIndex === attribute.optionsValues.length - 1;
                                  const canRemove = attribute.optionsValues.length > 1 || optionValue.trim().length > 0;

                                  return (
                                    <div key={`${attribute.id}-option-${optionIndex}`} className="categories-option-row">
                                      <input
                                        className="categories-options-input"
                                        value={optionValue}
                                        placeholder={`Option ${optionIndex + 1}`}
                                        onChange={(event) => updateOptionValue(index, optionIndex, event.target.value)}
                                      />
                                      <button
                                        type="button"
                                        className="btn btn-ghost categories-option-remove"
                                        onClick={() => removeOptionValue(index, optionIndex)}
                                        disabled={!canRemove || (isLast && optionValue.trim().length === 0 && attribute.optionsValues.length === 1)}
                                      >
                                        Remove
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
                              Min value
                              <input
                                type="number"
                                value={attribute.min_value}
                                onChange={(event) => updateField(index, { min_value: event.target.value })}
                              />
                            </label>

                            <label>
                              Max value
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
                {isSubmitting ? "Saving..." : selectedCategory ? "Save changes" : "Create category"}
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
                Reset form
              </button>
            </div>
          </form>
        </div>
      </section>
    </section>
  );
}
