import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { useAuth } from "../../app/auth/AuthContext";
import { usePageI18n } from "../../app/i18n/I18nContext";
import { formatDateTime, formatInteger } from "../../shared/i18n/format";
import { Modal } from "../common/Modal";

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

function statusLabel(status: ReportStatus, t: (key: string, fallback: string) => string): string {
  if (status === "open") {
    return t("status_open", "Open");
  }
  if (status === "resolved") {
    return t("status_resolved", "Resolved");
  }
  return t("status_dismissed", "Dismissed");
}

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed";
}

export function ReportsPage() {
  const { authFetch } = useAuth();
  const { t, language } = usePageI18n("reports");

  const [reports, setReports] = useState<ReportListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<ReportStatus | "">("open");
  const [targetTypeFilter, setTargetTypeFilter] = useState<ReportTargetType | "">("");
  const [page, setPage] = useState(1);

  const [selectedReportId, setSelectedReportId] = useState<number | null>(null);
  const [isReviewModalOpen, setIsReviewModalOpen] = useState(false);
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
        throw new Error(t("error_load_reports", "Failed to load reports"));
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
        let message = t("error_process_report", "Failed to process report");
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = t("error_process_report", "Failed to process report");
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
        { value: "approve", label: t("moderation_approve_listing", "Approve listing") },
        { value: "reject", label: t("moderation_reject_listing", "Reject listing") },
        { value: "archive", label: t("moderation_archive_listing", "Archive listing") },
        { value: "deactivate", label: t("moderation_deactivate_listing", "Deactivate listing") },
      ];
    }

    return [
      { value: "block", label: t("moderation_block_user", "Block user") },
      { value: "unblock", label: t("moderation_unblock_user", "Unblock user") },
      { value: "activate", label: t("moderation_activate_user", "Activate user") },
      { value: "deactivate", label: t("moderation_deactivate_user", "Deactivate user") },
    ];
  }, [selectedReport, t]);

  const totalPages = reports?.total_pages ?? 0;
  const canPrev = page > 1;
  const canNext = totalPages > 0 && page < totalPages;

  const summaryText = useMemo(() => {
    if (!reports) {
      return "-";
    }
    if (reports.total_items === 0) {
      return t("no_reports_found", "No reports found");
    }

    const from = (reports.page - 1) * reports.page_size + 1;
    const to = Math.min(reports.page * reports.page_size, reports.total_items);
    return `${formatInteger(from, language)}-${formatInteger(to, language)} ${t("of", "of")} ${formatInteger(reports.total_items, language)}`;
  }, [language, reports, t]);

  return (
    <section className="module-page">
      <header className="module-header">
        <div>
          <h1>{t("title", "Reports")}</h1>
          <p>{t("subtitle", "Review reports, apply moderation actions, and resolve or dismiss.")}</p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={() => void loadReports()} disabled={isLoading}>
          {isLoading ? t("refreshing", "Refreshing...") : t("refresh", "Refresh")}
        </button>
      </header>

      {error ? <div className="dashboard-error">{error}</div> : null}

      <div className="search-strip">
        <select
          className="users-filter-select"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as ReportStatus | "")}
        >
          <option value="">{t("all_statuses", "All statuses")}</option>
          <option value="open">{t("status_open", "Open")}</option>
          <option value="resolved">{t("status_resolved", "Resolved")}</option>
          <option value="dismissed">{t("status_dismissed", "Dismissed")}</option>
        </select>
        <select
          className="users-filter-select"
          value={targetTypeFilter}
          onChange={(event) => setTargetTypeFilter(event.target.value as ReportTargetType | "")}
        >
          <option value="">{t("all_target_types", "All target types")}</option>
          <option value="listing">{t("target_listing", "Listing")}</option>
          <option value="user">{t("target_user", "User")}</option>
        </select>
        <button type="button" className="btn btn-ghost" onClick={onApplyFilters}>
          {t("apply_filters", "Apply filters")}
        </button>
      </div>

      <section className="table-card" aria-label={t("reports_table", "Reports table")}>
        <div className="table-head users-table-head">
          <strong>{t("reports_queue", "Reports queue")}</strong>
          <span>{summaryText}</span>
        </div>

        <div className="reports-table-wrap">
          <table className="reports-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>{t("target", "Target")}</th>
                <th>{t("reason", "Reason")}</th>
                <th>{t("status", "Status")}</th>
                <th>{t("created", "Created")}</th>
                <th>{t("reviewed", "Reviewed")}</th>
                <th>{t("actions", "Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {(reports?.items ?? []).length === 0 ? (
                <tr>
                  <td colSpan={7} className="users-empty-cell">
                    {isLoading ? t("loading_reports", "Loading reports...") : t("no_reports_found", "No reports found")}
                  </td>
                </tr>
              ) : (
                reports?.items.map((report) => (
                  <tr key={report.id}>
                    <td>#{report.id}</td>
                    <td>
                      <div className="users-name-cell">
                        <strong>{report.target_type === "listing" ? t("target_listing", "Listing") : t("target_user", "User")}</strong>
                        <span>{t("target", "target")} #{formatInteger(report.target_id, language)}</span>
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
                        {statusLabel(report.status, t)}
                      </span>
                    </td>
                    <td>{formatDateTime(report.created_at, language)}</td>
                    <td>{formatDateTime(report.reviewed_at, language)}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-ghost"
                        onClick={() => {
                          setResolveAction("resolve");
                          setModerationAction("");
                          setResolutionNote(report.resolution_note ?? "");
                          setSelectedReportId(report.id);
                          setIsReviewModalOpen(true);
                        }}
                      >
                        {t("review", "Review")}
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
            {t("previous", "Previous")}
          </button>
          <span className="users-page-indicator">
            {t("page", "Page")} {formatInteger(reports?.page ?? page, language)}{totalPages ? ` / ${formatInteger(totalPages, language)}` : ""}
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
        open={isReviewModalOpen}
        onClose={() => setIsReviewModalOpen(false)}
        title={t("moderation_action", "Moderation action")}
        subtitle={selectedReport ? `${t("report", "Report")} #${formatInteger(selectedReport.id, language)}` : t("no_report_selected", "No report selected")}
      >
        <div className="users-detail-body">
          {!selectedReport ? <p>{t("select_report", "Select a report and click Review.")}</p> : null}

          {selectedReport ? (
            <form className="reports-form" onSubmit={onResolveSubmit}>
              <div className="reports-form-grid">
                <label>
                  {t("action", "Action")}
                  <select
                    className="users-filter-select"
                    value={resolveAction}
                    onChange={(event) => setResolveAction(event.target.value as ResolveAction)}
                  >
                    <option value="resolve">{t("resolve", "Resolve")}</option>
                    <option value="dismiss">{t("dismiss", "Dismiss")}</option>
                  </select>
                </label>

                <label>
                  {t("moderation_action_optional", "Moderation action (optional)")}
                  <select
                    className="users-filter-select"
                    value={moderationAction}
                    onChange={(event) => setModerationAction(event.target.value)}
                  >
                    <option value="">{t("no_moderation_action", "No moderation action")}</option>
                    {moderationOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <label className="reports-note-label">
                {t("resolution_note_optional", "Resolution note (optional)")}
                <textarea
                  className="reports-note-input"
                  value={resolutionNote}
                  onChange={(event) => setResolutionNote(event.target.value)}
                  placeholder={t("resolution_note_placeholder", "Provide moderation context for audit and reporter notifications")}
                  maxLength={2000}
                />
              </label>

              <div className="users-actions-cell">
                <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                  {isSubmitting ? t("applying", "Applying...") : t("apply_action", "Apply action")}
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
                  {t("reset_form", "Reset form")}
                </button>
              </div>
            </form>
          ) : null}
        </div>
      </Modal>
    </section>
  );
}
