import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { useAuth } from "../../app/auth/AuthContext";
import { usePageI18n } from "../../app/i18n/I18nContext";
import { formatDateTime, formatInteger } from "../../shared/i18n/format";
import { Modal } from "../common/Modal";

type I18nEntryItem = {
  id: number;
  page_key: string;
  text_key: string;
  language: string;
  text_value: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

type I18nEntryListResponse = {
  items: I18nEntryItem[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
};

type EntryFormState = {
  page_key: string;
  text_key: string;
  language: string;
  text_value: string;
  is_active: boolean;
};

const initialFormState: EntryFormState = {
  page_key: "",
  text_key: "",
  language: "en",
  text_value: "",
  is_active: true,
};

function normalizePageKey(value: string): string {
  return value.trim().toLowerCase().replace(/-/g, "_");
}

function normalizeLanguage(value: string): string {
  return value.trim().toLowerCase().replace(/_/g, "-").split("-", 1)[0] ?? "";
}

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed";
}

function truncateText(value: string, maxLength: number): string {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 1)}...`;
}

export function LocalizationPage() {
  const { authFetch } = useAuth();
  const { t, language } = usePageI18n("localization_admin");

  const [entries, setEntries] = useState<I18nEntryListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [page, setPage] = useState(1);
  const [queryInput, setQueryInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [pageKeyFilter, setPageKeyFilter] = useState("");
  const [languageFilter, setLanguageFilter] = useState("");
  const [includeInactive, setIncludeInactive] = useState(true);

  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [editingEntry, setEditingEntry] = useState<I18nEntryItem | null>(null);
  const [formState, setFormState] = useState<EntryFormState>(initialFormState);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [busyDeleteId, setBusyDeleteId] = useState<number | null>(null);

  const loadEntries = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", "20");
      params.set("include_inactive", includeInactive ? "true" : "false");

      const normalizedPageKeyFilter = normalizePageKey(pageKeyFilter);
      if (normalizedPageKeyFilter.length >= 2) {
        params.set("page_key", normalizedPageKeyFilter);
      }

      const normalizedLanguageFilter = normalizeLanguage(languageFilter);
      if (normalizedLanguageFilter.length >= 2) {
        params.set("language", normalizedLanguageFilter);
      }

      if (searchTerm.trim().length >= 1) {
        params.set("q", searchTerm.trim());
      }

      const response = await authFetch(`/i18n/admin/entries?${params.toString()}`);
      if (!response.ok) {
        let message = t("error_load_entries", "Failed to load localization entries");
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = t("error_load_entries", "Failed to load localization entries");
        }
        throw new Error(message);
      }

      const payload = (await response.json()) as I18nEntryListResponse;
      setEntries(payload);
    } catch (loadError) {
      setError(extractErrorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, [authFetch, includeInactive, languageFilter, page, pageKeyFilter, searchTerm, t]);

  useEffect(() => {
    void loadEntries();
  }, [loadEntries]);

  const onSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPage(1);
    setSearchTerm(queryInput);
  };

  const onApplyFilters = () => {
    if (page !== 1) {
      setPage(1);
      return;
    }
    void loadEntries();
  };

  const onResetFilters = () => {
    setQueryInput("");
    setSearchTerm("");
    setPageKeyFilter("");
    setLanguageFilter("");
    setIncludeInactive(true);
    if (page !== 1) {
      setPage(1);
      return;
    }
    void loadEntries();
  };

  const openCreateModal = () => {
    setEditingEntry(null);
    setFormState(initialFormState);
    setFormError(null);
    setIsFormModalOpen(true);
  };

  const openEditModal = (entry: I18nEntryItem) => {
    setEditingEntry(entry);
    setFormState({
      page_key: entry.page_key,
      text_key: entry.text_key,
      language: entry.language,
      text_value: entry.text_value,
      is_active: entry.is_active,
    });
    setFormError(null);
    setIsFormModalOpen(true);
  };

  const saveEntry = async () => {
    const pageKey = normalizePageKey(formState.page_key);
    const textKey = formState.text_key.trim();
    const lang = normalizeLanguage(formState.language);
    const textValue = formState.text_value.trim();

    if (pageKey.length < 2) {
      setFormError(t("error_page_key", "Page key must contain at least 2 characters"));
      return;
    }
    if (textKey.length < 1) {
      setFormError(t("error_text_key", "Text key is required"));
      return;
    }
    if (lang.length < 2) {
      setFormError(t("error_language", "Language is required"));
      return;
    }
    if (textValue.length < 1) {
      setFormError(t("error_text_value", "Text value is required"));
      return;
    }

    setIsSaving(true);
    setFormError(null);

    try {
      const payload = {
        page_key: pageKey,
        text_key: textKey,
        language: lang,
        text_value: textValue,
        is_active: formState.is_active,
      };

      const isEdit = editingEntry !== null;
      const path = isEdit ? `/i18n/admin/entries/${editingEntry.id}` : "/i18n/admin/entries";
      const method = isEdit ? "PATCH" : "POST";

      const response = await authFetch(path, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        let message = t("error_save_entry", "Failed to save localization entry");
        try {
          const errorPayload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof errorPayload?.error?.message === "string") {
            message = errorPayload.error.message;
          } else if (typeof errorPayload?.detail === "string") {
            message = errorPayload.detail;
          }
        } catch {
          message = t("error_save_entry", "Failed to save localization entry");
        }
        throw new Error(message);
      }

      setIsFormModalOpen(false);
      setEditingEntry(null);
      await loadEntries();
    } catch (saveError) {
      setFormError(extractErrorMessage(saveError));
    } finally {
      setIsSaving(false);
    }
  };

  const deleteEntry = async (entry: I18nEntryItem) => {
    const confirmed = window.confirm(
      `${t("confirm_delete", "Delete localization entry")} ${entry.page_key}.${entry.text_key} (${entry.language})?`,
    );
    if (!confirmed) {
      return;
    }

    setBusyDeleteId(entry.id);
    setError(null);

    try {
      const response = await authFetch(`/i18n/admin/entries/${entry.id}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        let message = t("error_delete_entry", "Failed to delete localization entry");
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = t("error_delete_entry", "Failed to delete localization entry");
        }
        throw new Error(message);
      }

      await loadEntries();
    } catch (deleteError) {
      setError(extractErrorMessage(deleteError));
    } finally {
      setBusyDeleteId(null);
    }
  };

  const rows = entries?.items ?? [];
  const totalPages = entries?.total_pages ?? 0;
  const canPrev = page > 1;
  const canNext = totalPages > 0 && page < totalPages;

  const summaryText = useMemo(() => {
    if (!entries) {
      return "-";
    }
    if (entries.total_items === 0) {
      return t("no_entries_found", "No localization entries found");
    }

    const from = (entries.page - 1) * entries.page_size + 1;
    const to = Math.min(entries.page * entries.page_size, entries.total_items);
    return `${formatInteger(from, language)}-${formatInteger(to, language)} ${t("of", "of")} ${formatInteger(entries.total_items, language)}`;
  }, [entries, language, t]);

  return (
    <section className="module-page">
      <header className="module-header">
        <div>
          <h1>{t("title", "Localization")}</h1>
          <p>{t("subtitle", "Manage translation entries used by admin pages and runtime dictionaries.")}</p>
        </div>
        <div className="users-actions-cell">
          <button type="button" className="btn btn-ghost" onClick={() => void loadEntries()} disabled={isLoading}>
            {isLoading ? t("refreshing", "Refreshing...") : t("refresh", "Refresh")}
          </button>
          <button type="button" className="btn btn-primary" onClick={openCreateModal}>
            {t("new_entry", "New entry")}
          </button>
        </div>
      </header>

      {error ? <div className="dashboard-error">{error}</div> : null}

      <form className="search-strip localization-search-strip" onSubmit={onSearchSubmit}>
        <input
          placeholder={t("search_placeholder", "Search by page/key/text")}
          value={queryInput}
          onChange={(event) => setQueryInput(event.target.value)}
        />
        <input
          placeholder={t("page_key", "Page key")}
          value={pageKeyFilter}
          onChange={(event) => setPageKeyFilter(event.target.value)}
        />
        <input
          placeholder={t("language", "Language")}
          value={languageFilter}
          onChange={(event) => setLanguageFilter(event.target.value)}
        />
        <label className="categories-checkbox-label">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(event) => setIncludeInactive(event.target.checked)}
          />
          {t("include_inactive", "Include inactive")}
        </label>
        <button type="button" className="btn btn-ghost" onClick={onResetFilters}>
          {t("reset", "Reset")}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onApplyFilters}>
          {t("apply_filters", "Apply filters")}
        </button>
        <button type="submit" className="btn btn-primary">
          {t("search", "Search")}
        </button>
      </form>

      <section className="table-card" aria-label={t("entries_table", "Localization entries table")}>
        <div className="table-head users-table-head">
          <strong>{t("entries", "Entries")}</strong>
          <span>{summaryText}</span>
        </div>

        <div className="localization-table-wrap">
          <table className="localization-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>{t("page_key", "Page key")}</th>
                <th>{t("text_key", "Text key")}</th>
                <th>{t("language", "Language")}</th>
                <th>{t("text_value", "Text value")}</th>
                <th>{t("status", "Status")}</th>
                <th>{t("updated", "Updated")}</th>
                <th>{t("actions", "Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="users-empty-cell">
                    {isLoading ? t("loading_entries", "Loading entries...") : t("no_entries_found", "No localization entries found")}
                  </td>
                </tr>
              ) : (
                rows.map((item) => (
                  <tr key={item.id}>
                    <td>#{formatInteger(item.id, language)}</td>
                    <td>{item.page_key}</td>
                    <td>{item.text_key}</td>
                    <td>{item.language}</td>
                    <td title={item.text_value}>{truncateText(item.text_value, 90)}</td>
                    <td>
                      <span className={`users-status-badge ${item.is_active ? "users-status-active" : "users-status-deactivated"}`}>
                        {item.is_active ? t("active", "Active") : t("inactive", "Inactive")}
                      </span>
                    </td>
                    <td>{formatDateTime(item.updated_at, language)}</td>
                    <td>
                      <div className="users-actions-cell">
                        <button type="button" className="btn btn-ghost" onClick={() => openEditModal(item)}>
                          {t("edit", "Edit")}
                        </button>
                        <button
                          type="button"
                          className="btn btn-primary"
                          disabled={busyDeleteId === item.id}
                          onClick={() => void deleteEntry(item)}
                        >
                          {busyDeleteId === item.id ? t("processing", "Processing...") : t("delete", "Delete")}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="table-footer">
          <button
            type="button"
            className="btn btn-ghost"
            disabled={!canPrev}
            onClick={() => setPage((prev) => Math.max(1, prev - 1))}
          >
            {t("previous", "Previous")}
          </button>
          <span className="users-page-indicator">
            {t("page", "Page")} {formatInteger(entries?.page ?? page, language)}{totalPages ? ` / ${formatInteger(totalPages, language)}` : ""}
          </span>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={!canNext}
            onClick={() => setPage((prev) => prev + 1)}
          >
            {t("next", "Next")}
          </button>
        </div>
      </section>

      <Modal
        open={isFormModalOpen}
        onClose={() => setIsFormModalOpen(false)}
        title={editingEntry ? t("edit_entry", "Edit localization entry") : t("create_entry", "Create localization entry")}
        subtitle={editingEntry ? `${editingEntry.page_key}.${editingEntry.text_key}` : t("new_entry", "New entry")}
      >
        <div className="users-detail-body">
          {formError ? <div className="dashboard-error">{formError}</div> : null}

          <form
            className="reports-form"
            onSubmit={(event) => {
              event.preventDefault();
              void saveEntry();
            }}
          >
            <div className="reports-form-grid">
              <label>
                {t("page_key", "Page key")}
                <input
                  value={formState.page_key}
                  onChange={(event) => setFormState((prev) => ({ ...prev, page_key: event.target.value }))}
                  required
                />
              </label>

              <label>
                {t("text_key", "Text key")}
                <input
                  value={formState.text_key}
                  onChange={(event) => setFormState((prev) => ({ ...prev, text_key: event.target.value }))}
                  required
                />
              </label>
            </div>

            <div className="reports-form-grid">
              <label>
                {t("language", "Language")}
                <input
                  value={formState.language}
                  onChange={(event) => setFormState((prev) => ({ ...prev, language: event.target.value }))}
                  required
                />
              </label>

              <label className="categories-checkbox-label categories-form-checkbox">
                <input
                  type="checkbox"
                  checked={formState.is_active}
                  onChange={(event) => setFormState((prev) => ({ ...prev, is_active: event.target.checked }))}
                />
                {t("active", "Active")}
              </label>
            </div>

            <label className="reports-note-label">
              {t("text_value", "Text value")}
              <textarea
                className="reports-note-input"
                value={formState.text_value}
                onChange={(event) => setFormState((prev) => ({ ...prev, text_value: event.target.value }))}
                required
                maxLength={10000}
              />
            </label>

            <div className="users-actions-cell">
              <button type="submit" className="btn btn-primary" disabled={isSaving}>
                {isSaving ? t("saving", "Saving...") : editingEntry ? t("save_changes", "Save changes") : t("create", "Create")}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => {
                  if (editingEntry) {
                    openEditModal(editingEntry);
                    return;
                  }
                  setFormState(initialFormState);
                }}
              >
                {t("reset", "Reset")}
              </button>
            </div>
          </form>
        </div>
      </Modal>
    </section>
  );
}
