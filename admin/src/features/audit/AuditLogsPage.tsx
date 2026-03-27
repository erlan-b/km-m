import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "../../app/auth/AuthContext";
import { usePageI18n } from "../../app/i18n/I18nContext";
import { Modal } from "../common/Modal";

type AdminAuditLogItem = {
  id: number;
  admin_user_id: number | null;
  action: string;
  target_type: string;
  target_id: number;
  details: string | null;
  created_at: string;
};

type AdminAuditLogListResponse = {
  items: AdminAuditLogItem[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
};

type AuditFilters = {
  action: string;
  target_type: string;
  admin_user_id: string;
};

const initialFilters: AuditFilters = {
  action: "",
  target_type: "",
  admin_user_id: "",
};

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
  return "Failed to load audit logs";
}

function parsePositiveInt(value: string): number | null {
  const normalized = value.trim();
  if (!normalized) {
    return null;
  }

  const parsed = Number.parseInt(normalized, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }

  return parsed;
}

function truncateText(value: string, maxLength: number): string {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 1)}...`;
}

export function AuditLogsPage() {
  const { authFetch } = useAuth();
  const { t } = usePageI18n("audit_logs");

  const [logs, setLogs] = useState<AdminAuditLogListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [page, setPage] = useState(1);
  const [draftFilters, setDraftFilters] = useState<AuditFilters>(initialFilters);
  const [appliedFilters, setAppliedFilters] = useState<AuditFilters>(initialFilters);

  const [selectedLog, setSelectedLog] = useState<AdminAuditLogItem | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);

  const loadLogs = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", "20");

      const action = appliedFilters.action.trim();
      if (action.length >= 2) {
        params.set("action", action);
      }

      const targetType = appliedFilters.target_type.trim();
      if (targetType.length >= 2) {
        params.set("target_type", targetType);
      }

      const adminUserId = parsePositiveInt(appliedFilters.admin_user_id);
      if (adminUserId !== null) {
        params.set("admin_user_id", String(adminUserId));
      }

      const response = await authFetch(`/admin/audit-logs?${params.toString()}`);
      if (!response.ok) {
        let message = "Failed to load audit logs";
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = "Failed to load audit logs";
        }
        throw new Error(message);
      }

      const payload = (await response.json()) as AdminAuditLogListResponse;
      setLogs(payload);

      if (payload.items.length === 0) {
        setSelectedLog(null);
        setIsDetailModalOpen(false);
      } else if (selectedLog) {
        const refreshed = payload.items.find((item) => item.id === selectedLog.id) ?? null;
        setSelectedLog(refreshed);
      }
    } catch (loadError) {
      setError(extractErrorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, [appliedFilters, authFetch, page, selectedLog]);

  useEffect(() => {
    void loadLogs();
  }, [loadLogs]);

  const onApplyFilters = () => {
    if (page !== 1) {
      setPage(1);
    }
    setAppliedFilters({
      action: draftFilters.action.trim(),
      target_type: draftFilters.target_type.trim(),
      admin_user_id: draftFilters.admin_user_id,
    });
  };

  const onResetFilters = () => {
    setDraftFilters(initialFilters);
    setAppliedFilters(initialFilters);
    if (page !== 1) {
      setPage(1);
    }
  };

  const rows = logs?.items ?? [];
  const totalPages = logs?.total_pages ?? 0;
  const canPrev = page > 1;
  const canNext = totalPages > 0 && page < totalPages;

  const summaryText = useMemo(() => {
    if (!logs) {
      return "-";
    }
    if (logs.total_items === 0) {
      return "No audit logs found";
    }

    const from = (logs.page - 1) * logs.page_size + 1;
    const to = Math.min(logs.page * logs.page_size, logs.total_items);
    return `${from}-${to} of ${logs.total_items}`;
  }, [logs]);

  return (
    <section className="module-page">
      <header className="module-header">
        <div>
          <h1>{t("title", "Audit Logs")}</h1>
          <p>{t("subtitle", "Trace moderation actions, actors, targets and details.")}</p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={() => void loadLogs()} disabled={isLoading}>
          {isLoading ? t("refreshing", "Refreshing...") : t("refresh", "Refresh")}
        </button>
      </header>

      {error ? <div className="dashboard-error">{error}</div> : null}

      <section className="search-strip audit-search-strip" aria-label="Audit logs filters">
        <input
          placeholder="Action"
          value={draftFilters.action}
          onChange={(event) => setDraftFilters((prev) => ({ ...prev, action: event.target.value }))}
        />

        <input
          placeholder="Target type"
          value={draftFilters.target_type}
          onChange={(event) => setDraftFilters((prev) => ({ ...prev, target_type: event.target.value }))}
        />

        <input
          placeholder="Admin user ID"
          inputMode="numeric"
          value={draftFilters.admin_user_id}
          onChange={(event) => setDraftFilters((prev) => ({ ...prev, admin_user_id: event.target.value }))}
        />

        <button type="button" className="btn btn-ghost" onClick={onResetFilters}>
          {t("reset", "Reset")}
        </button>
        <button type="button" className="btn btn-primary" onClick={onApplyFilters}>
          {t("apply_filters", "Apply filters")}
        </button>
      </section>

      <section className="table-card" aria-label="Audit logs table">
        <div className="table-head users-table-head">
          <strong>Audit logs</strong>
          <span>{summaryText}</span>
        </div>

        <div className="audit-table-wrap">
          <table className="audit-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Admin</th>
                <th>Action</th>
                <th>Target</th>
                <th>Details</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="users-empty-cell">
                    {isLoading ? "Loading audit logs..." : "No audit logs found"}
                  </td>
                </tr>
              ) : (
                rows.map((item) => (
                  <tr key={item.id}>
                    <td>#{item.id}</td>
                    <td>{item.admin_user_id ?? "-"}</td>
                    <td>{item.action}</td>
                    <td>
                      <div className="users-name-cell">
                        <strong>{item.target_type}</strong>
                        <span>target #{item.target_id}</span>
                      </div>
                    </td>
                    <td>{item.details ? truncateText(item.details, 80) : "-"}</td>
                    <td>{formatDate(item.created_at)}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-ghost"
                        onClick={() => {
                          setSelectedLog(item);
                          setIsDetailModalOpen(true);
                        }}
                      >
                        Details
                      </button>
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
            Previous
          </button>
          <span className="users-page-indicator">
            Page {logs?.page ?? page}{totalPages ? ` / ${totalPages}` : ""}
          </span>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={!canNext}
            onClick={() => setPage((prev) => prev + 1)}
          >
            Next
          </button>
        </div>
      </section>

      <Modal
        open={isDetailModalOpen}
        onClose={() => setIsDetailModalOpen(false)}
        title="Audit log detail"
        subtitle={selectedLog ? `Log #${selectedLog.id}` : "No log selected"}
      >
        <div className="users-detail-body">
          {!selectedLog ? <p>Select a log entry and click Details.</p> : null}

          {selectedLog ? (
            <div className="dashboard-stats-grid">
              <article className="dashboard-stat-group">
                <h3>Actor</h3>
                <p>Admin user ID: <strong>{selectedLog.admin_user_id ?? "-"}</strong></p>
                <p>Action: <strong>{selectedLog.action}</strong></p>
              </article>

              <article className="dashboard-stat-group">
                <h3>Target</h3>
                <p>Type: <strong>{selectedLog.target_type}</strong></p>
                <p>ID: <strong>{selectedLog.target_id}</strong></p>
              </article>

              <article className="dashboard-stat-group">
                <h3>Timestamp</h3>
                <p>Created: <strong>{formatDate(selectedLog.created_at)}</strong></p>
              </article>

              <article className="dashboard-stat-group">
                <h3>Details</h3>
                <p className="audit-log-details">{selectedLog.details ?? "No details"}</p>
              </article>
            </div>
          ) : null}
        </div>
      </Modal>
    </section>
  );
}
