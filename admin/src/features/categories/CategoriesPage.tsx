import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { useAuth } from "../../app/auth/AuthContext";

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
  slug: string;
  is_active: boolean;
  display_order: number;
  attributes_schema: CategoryAttributeDefinition[] | null;
  created_at: string;
};

type CategoryListResponse = {
  items: CategoryItem[];
};

type CategoryFormState = {
  name: string;
  slug: string;
  displayOrder: string;
  isActive: boolean;
  attributesSchemaText: string;
};

const DEFAULT_SCHEMA_TEXT = "[]";

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
    slug: "",
    displayOrder: "0",
    isActive: true,
    attributesSchemaText: DEFAULT_SCHEMA_TEXT,
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

function parseAttributesSchema(source: string): CategoryAttributeDefinition[] | null {
  const trimmed = source.trim();
  if (!trimmed || trimmed === "null") {
    return null;
  }

  const parsed = JSON.parse(trimmed) as unknown;
  if (!Array.isArray(parsed)) {
    throw new Error("attributes_schema must be a JSON array");
  }
  return parsed as CategoryAttributeDefinition[];
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

      if (payload.items.length > 0) {
        const selectedVisible = selectedCategoryId !== null && payload.items.some((item) => item.id === selectedCategoryId);
        if (!selectedVisible) {
          setSelectedCategoryId(payload.items[0].id);
        }
      } else {
        setSelectedCategoryId(null);
      }
    } catch (loadError) {
      setError(extractErrorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, [authFetch, selectedCategoryId, showInactive]);

  useEffect(() => {
    void loadCategories();
  }, [loadCategories]);

  useEffect(() => {
    if (!selectedCategory) {
      setFormState(buildInitialFormState());
      return;
    }

    setFormState({
      name: selectedCategory.name,
      slug: selectedCategory.slug,
      displayOrder: String(selectedCategory.display_order),
      isActive: selectedCategory.is_active,
      attributesSchemaText: JSON.stringify(selectedCategory.attributes_schema ?? [], null, 2),
    });
  }, [selectedCategory]);

  const filteredRows = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) {
      return categories;
    }

    return categories.filter((item) => {
      const source = `${item.name} ${item.slug}`.toLowerCase();
      return source.includes(term);
    });
  }, [categories, query]);

  const resetCreateForm = () => {
    setSelectedCategoryId(null);
    setFormState(buildInitialFormState());
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
      const parsedDisplayOrder = Number(formState.displayOrder);
      if (!Number.isInteger(parsedDisplayOrder) || parsedDisplayOrder < 0) {
        throw new Error("Display order must be an integer >= 0");
      }

      const attributesSchema = parseAttributesSchema(formState.attributesSchemaText);

      const payload = {
        name: formState.name.trim(),
        slug: normalizeSlug(formState.slug),
        is_active: formState.isActive,
        display_order: parsedDisplayOrder,
        attributes_schema: attributesSchema,
      };

      if (!payload.name || payload.name.length < 2) {
        throw new Error("Name must be at least 2 characters");
      }
      if (!payload.slug || payload.slug.length < 2) {
        throw new Error("Slug must be at least 2 characters");
      }

      const isEditMode = selectedCategory !== null;
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
        return [...prev, saved].sort((a, b) => a.display_order - b.display_order || a.id - b.id);
      });
      setSelectedCategoryId(saved.id);
    } catch (submitError) {
      setError(extractErrorMessage(submitError));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="module-page">
      <header className="module-header">
        <div>
          <h1>Categories</h1>
          <p>Manage category metadata, ordering, active state, and dynamic attributes schema.</p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={() => void loadCategories()} disabled={isLoading}>
          {isLoading ? "Refreshing..." : "Refresh"}
        </button>
      </header>

      {error ? <div className="dashboard-error">{error}</div> : null}

      <div className="search-strip categories-search-strip">
        <input
          placeholder="Search by name or slug"
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
                <th>Slug</th>
                <th>Order</th>
                <th>Attributes</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="users-empty-cell">
                    {isLoading ? "Loading categories..." : "No categories found"}
                  </td>
                </tr>
              ) : (
                filteredRows.map((category) => (
                  <tr key={category.id}>
                    <td>{category.name}</td>
                    <td>{category.slug}</td>
                    <td>{category.display_order}</td>
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
                  onChange={(event) => {
                    const name = event.target.value;
                    setFormState((prev) => ({
                      ...prev,
                      name,
                      slug: selectedCategory ? prev.slug : normalizeSlug(name),
                    }));
                  }}
                  required
                  minLength={2}
                />
              </label>

              <label>
                Slug
                <input
                  value={formState.slug}
                  onChange={(event) => setFormState((prev) => ({ ...prev, slug: normalizeSlug(event.target.value) }))}
                  required
                  minLength={2}
                />
              </label>
            </div>

            <div className="reports-form-grid">
              <label>
                Display order
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={formState.displayOrder}
                  onChange={(event) => setFormState((prev) => ({ ...prev, displayOrder: event.target.value }))}
                />
              </label>

              <label className="categories-checkbox-label categories-form-checkbox">
                <input
                  type="checkbox"
                  checked={formState.isActive}
                  onChange={(event) => setFormState((prev) => ({ ...prev, isActive: event.target.checked }))}
                />
                Active
              </label>
            </div>

            <label className="reports-note-label">
              attributes_schema (JSON array)
              <textarea
                className="reports-note-input categories-schema-input"
                value={formState.attributesSchemaText}
                onChange={(event) => setFormState((prev) => ({ ...prev, attributesSchemaText: event.target.value }))}
                spellCheck={false}
              />
            </label>

            <div className="users-actions-cell">
              <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                {isSubmitting ? "Saving..." : selectedCategory ? "Save changes" : "Create category"}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => {
                  if (selectedCategory) {
                    setFormState({
                      name: selectedCategory.name,
                      slug: selectedCategory.slug,
                      displayOrder: String(selectedCategory.display_order),
                      isActive: selectedCategory.is_active,
                      attributesSchemaText: JSON.stringify(selectedCategory.attributes_schema ?? [], null, 2),
                    });
                    return;
                  }
                  setFormState(buildInitialFormState());
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
