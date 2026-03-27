import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { useAuth } from "../../app/auth/AuthContext";

type ReportStatus = "open" | "resolved" | "dismissed";
type ReportTargetType = "listing" | "user";
type ResolveAction = "resolve" | "dismiss";

type ReportItem = {
  id: number;
  reporter_user_id: number;
  target_type: ReportTargetType;
  target_id: number;
  reason_code: string;
  reason_text: string | null;
  status: ReportStatus;
  resolution_note: string | null;
  reviewed_by_admin_id: number | null;
  created_at: string;
  reviewed_at: string | null;
};

type ReportListResponse = {
  items: ReportItem[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
};

type ReportResolveRequest = {
  action: ResolveAction;
  resolution_note: string | null;
  moderation_action: string | null;
};

function formatDate(value: string | null): string {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function statusLabel(status: ReportStatus): string {
  if (status === "open") {
    return "Open";
  }
  if (status === "resolved") {
    return "Resolved";
  }
  return "Dismissed";
}

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed";
}

export function ReportsPage() {
  const { authFetch } = useAuth();

  const [reports, setReports] = useState<ReportListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<ReportStatus | "">("open");
  const [targetTypeFilter, setTargetTypeFilter] = useState<ReportTargetType | "">("");
  const [page, setPage] = useState(1);

  const [selectedReportId, setSelectedReportId] = useState<number | null>(null);
  const [resolveAction, setResolveAction] = useState<ResolveAction>("resolve");
  const [moderationAction, setModerationAction] = useState("");
  const [resolutionNote, setResolutionNote] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadReports = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", "20");

      if (statusFilter) {
        params.set("status_filter", statusFilter);
      }
      if (targetTypeFilter) {
        params.set("target_type_filter", targetTypeFilter);
      }

      const response = await authFetch(`/reports/admin?${params.toString()}`);
      if (!response.ok) {
        throw new Error("Failed to load reports");
      }

      const payload = (await response.json()) as ReportListResponse;
      setReports(payload);

      if (payload.items.length > 0) {
        const selectedIsVisible = selectedReportId !== null && payload.items.some((item) => item.id === selectedReportId);
        if (!selectedIsVisible) {
          setSelectedReportId(payload.items[0].id);
        }
      }

      if (payload.items.length === 0) {
        setSelectedReportId(null);
      }
    } catch (loadError) {
      setError(extractErrorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, [authFetch, page, selectedReportId, statusFilter, targetTypeFilter]);

  useEffect(() => {
    void loadReports();
  }, [loadReports]);

  const selectedReport = useMemo(() => {
    if (!reports || selectedReportId === null) {
      return null;
    }
    return reports.items.find((item) => item.id === selectedReportId) ?? null;
  }, [reports, selectedReportId]);

  useEffect(() => {
    setResolveAction("resolve");
    setModerationAction("");
    setResolutionNote(selectedReport?.resolution_note ?? "");
  }, [selectedReport?.id, selectedReport?.resolution_note]);

  const onApplyFilters = () => {
    if (page !== 1) {
      setPage(1);
      return;
    }
    void loadReports();
  };

  const onResolveSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!selectedReport) {
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const body: ReportResolveRequest = {
        action: resolveAction,
        resolution_note: resolutionNote.trim() ? resolutionNote.trim() : null,
        moderation_action: moderationAction.trim() ? moderationAction.trim() : null,
      };

      const response = await authFetch(`/reports/${selectedReport.id}/resolve`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        let message = "Failed to process report";
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = "Failed to process report";
        }
        throw new Error(message);
      }

      const updated = (await response.json()) as ReportItem;

      setReports((prev) => {
        if (!prev) {
          return prev;
        }

        return {
          ...prev,
          items: prev.items.map((item) => (item.id === updated.id ? updated : item)),
        };
      });
      setResolutionNote(updated.resolution_note ?? "");
    } catch (submitError) {
      setError(extractErrorMessage(submitError));
    } finally {
      setIsSubmitting(false);
    }
  };

  const moderationOptions = useMemo(() => {
    if (!selectedReport) {
      return [] as Array<{ value: string; label: string }>;
    }

    if (selectedReport.target_type === "listing") {
      return [
        { value: "approve", label: "Approve listing" },
        { value: "reject", label: "Reject listing" },
        { value: "archive", label: "Archive listing" },
        { value: "deactivate", label: "Deactivate listing" },
      ];
    }

    return [
      { value: "block", label: "Block user" },
      { value: "unblock", label: "Unblock user" },
      { value: "activate", label: "Activate user" },
      { value: "deactivate", label: "Deactivate user" },
    ];
  }, [selectedReport]);

  const totalPages = reports?.total_pages ?? 0;
  const canPrev = page > 1;
  const canNext = totalPages > 0 && page < totalPages;

  const summaryText = useMemo(() => {
    if (!reports) {
      return "-";
    }
    if (reports.total_items === 0) {
      return "No reports found";
    }

    const from = (reports.page - 1) * reports.page_size + 1;
    const to = Math.min(reports.page * reports.page_size, reports.total_items);
    return `${from}-${to} of ${reports.total_items}`;
  }, [reports]);

  return (
    <section className="module-page">
      <header className="module-header">
        <div>
          <h1>Reports</h1>
          <p>Review reports, apply moderation actions, and resolve or dismiss.</p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={() => void loadReports()} disabled={isLoading}>
          {isLoading ? "Refreshing..." : "Refresh"}
        </button>
      </header>

      {error ? <div className="dashboard-error">{error}</div> : null}

      <div className="search-strip">
        <select
          className="users-filter-select"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as ReportStatus | "")}
        >
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="resolved">Resolved</option>
          <option value="dismissed">Dismissed</option>
        </select>
        <select
          className="users-filter-select"
          value={targetTypeFilter}
          onChange={(event) => setTargetTypeFilter(event.target.value as ReportTargetType | "")}
        >
          <option value="">All target types</option>
          <option value="listing">Listing</option>
          <option value="user">User</option>
        </select>
        <button type="button" className="btn btn-ghost" onClick={onApplyFilters}>
          Apply filters
        </button>
      </div>

      <section className="table-card" aria-label="Reports table">
        <div className="table-head users-table-head">
          <strong>Reports queue</strong>
          <span>{summaryText}</span>
        </div>

        <div className="reports-table-wrap">
          <table className="reports-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Target</th>
                <th>Reason</th>
                <th>Status</th>
                <th>Created</th>
                <th>Reviewed</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {(reports?.items ?? []).length === 0 ? (
                <tr>
                  <td colSpan={7} className="users-empty-cell">
                    {isLoading ? "Loading reports..." : "No reports found"}
                  </td>
                </tr>
              ) : (
                reports?.items.map((report) => (
                  <tr key={report.id}>
                    <td>#{report.id}</td>
                    <td>
                      <div className="users-name-cell">
                        <strong>{report.target_type}</strong>
                        <span>target #{report.target_id}</span>
                      </div>
                    </td>
                    <td>
                      <div className="users-name-cell">
                        <strong>{report.reason_code}</strong>
                        <span>{report.reason_text ?? "-"}</span>
                      </div>
                    </td>
                    <td>
                      <span className={`users-status-badge users-status-${report.status === "open" ? "pending_verification" : report.status === "resolved" ? "active" : "deactivated"}`}>
                        {statusLabel(report.status)}
                      </span>
                    </td>
                    <td>{formatDate(report.created_at)}</td>
                    <td>{formatDate(report.reviewed_at)}</td>
                    <td>
                      <button type="button" className="btn btn-ghost" onClick={() => setSelectedReportId(report.id)}>
                        Review
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
            Page {reports?.page ?? page}{totalPages ? ` / ${totalPages}` : ""}
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

      <section className="table-card" aria-label="Report moderation panel">
        <div className="table-head">
          <strong>Moderation action</strong>
          <span>{selectedReport ? `Report #${selectedReport.id}` : "No report selected"}</span>
        </div>

        <div className="users-detail-body">
          {!selectedReport ? <p>Select a report and click Review.</p> : null}

          {selectedReport ? (
            <form className="reports-form" onSubmit={onResolveSubmit}>
              <div className="reports-form-grid">
                <label>
                  Action
                  <select
                    className="users-filter-select"
                    value={resolveAction}
                    onChange={(event) => setResolveAction(event.target.value as ResolveAction)}
                  >
                    <option value="resolve">Resolve</option>
                    <option value="dismiss">Dismiss</option>
                  </select>
                </label>

                <label>
                  Moderation action (optional)
                  <select
                    className="users-filter-select"
                    value={moderationAction}
                    onChange={(event) => setModerationAction(event.target.value)}
                  >
                    <option value="">No moderation action</option>
                    {moderationOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <label className="reports-note-label">
                Resolution note (optional)
                <textarea
                  className="reports-note-input"
                  value={resolutionNote}
                  onChange={(event) => setResolutionNote(event.target.value)}
                  placeholder="Provide moderation context for audit and reporter notifications"
                  maxLength={2000}
                />
              </label>

              <div className="users-actions-cell">
                <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                  {isSubmitting ? "Applying..." : "Apply action"}
                </button>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => {
                    setResolveAction("resolve");
                    setModerationAction("");
                    setResolutionNote(selectedReport.resolution_note ?? "");
                  }}
                >
                  Reset form
                </button>
              </div>
            </form>
          ) : null}
        </div>
      </section>
    </section>
  );
}
