import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useAuth } from "../../app/auth/AuthContext";
import { usePageI18n } from "../../app/i18n/I18nContext";
import { formatDateTime, formatInteger } from "../../shared/i18n/format";
import { Modal } from "../common/Modal";

type ReportStatus = "open" | "resolved" | "dismissed";
type ReportTargetType = "listing" | "user" | "message";
type ResolveAction = "resolve" | "dismiss";

type ReportAttachmentItem = {
  id: number;
  report_id: number;
  file_name: string;
  original_name: string;
  mime_type: string;
  file_size: number;
  file_path: string;
  created_at: string;
};

type ReportItem = {
  id: number;
  reporter_user_id: number;
  target_type: ReportTargetType;
  target_id: number;
  target_conversation_id: number | null;
  target_listing_id: number | null;
  reason_code: string;
  reason_text: string | null;
  attachments: ReportAttachmentItem[];
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

function targetTypeLabel(targetType: ReportTargetType, t: (key: string, fallback: string) => string): string {
  if (targetType === "listing") {
    return t("target_listing", "Listing");
  }
  if (targetType === "user") {
    return t("target_user", "User");
  }
  return t("target_message", "Message");
}

function formatFileSize(bytes: number, language: "en" | "ru"): string {
  if (!Number.isFinite(bytes) || bytes < 1024) {
    return `${Math.max(0, Math.floor(bytes || 0))} B`;
  }
  const kb = bytes / 1024;
  if (kb < 1024) {
    return `${new Intl.NumberFormat(language, { maximumFractionDigits: 1 }).format(kb)} KB`;
  }
  const mb = kb / 1024;
  return `${new Intl.NumberFormat(language, { maximumFractionDigits: 1 }).format(mb)} MB`;
}

function isImageAttachment(attachment: ReportAttachmentItem): boolean {
  return attachment.mime_type.toLowerCase().startsWith("image/");
}

function getReportListingId(report: ReportItem): number | null {
  if (report.target_listing_id !== null) {
    return report.target_listing_id;
  }
  if (report.target_type === "listing") {
    return report.target_id;
  }
  return null;
}

export function ReportsPage() {
  const { authFetch, canModerateContent } = useAuth();
  const { t, language } = usePageI18n("reports");
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

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
  const [downloadingAttachmentId, setDownloadingAttachmentId] = useState<number | null>(null);
  const [previewUrls, setPreviewUrls] = useState<Record<number, string>>({});
  const [previewLoadingIds, setPreviewLoadingIds] = useState<number[]>([]);
  const [previewFailedIds, setPreviewFailedIds] = useState<number[]>([]);
  const previewUrlsRef = useRef<Record<number, string>>({});

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

      const reportIdFromQuery = Number(searchParams.get("report_id"));
      const preferredReportId = Number.isInteger(reportIdFromQuery) && reportIdFromQuery > 0 ? reportIdFromQuery : null;

      if (payload.items.length > 0) {
        const selectedIsVisible = selectedReportId !== null && payload.items.some((item) => item.id === selectedReportId);
        const preferredVisible = preferredReportId !== null && payload.items.some((item) => item.id === preferredReportId);

        if (preferredVisible) {
          setSelectedReportId(preferredReportId);
        } else if (!selectedIsVisible) {
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
  }, [authFetch, page, searchParams, selectedReportId, statusFilter, t, targetTypeFilter]);

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

  useEffect(() => {
    previewUrlsRef.current = previewUrls;
  }, [previewUrls]);

  useEffect(() => {
    return () => {
      for (const previewUrl of Object.values(previewUrlsRef.current)) {
        window.URL.revokeObjectURL(previewUrl);
      }
    };
  }, []);

  useEffect(() => {
    setPreviewUrls((previous) => {
      for (const previewUrl of Object.values(previous)) {
        window.URL.revokeObjectURL(previewUrl);
      }
      return {};
    });
    setPreviewLoadingIds([]);
    setPreviewFailedIds([]);
  }, [selectedReport?.id]);

  const loadAttachmentPreview = useCallback(
    async (attachment: ReportAttachmentItem) => {
      if (!isImageAttachment(attachment)) {
        return;
      }

      if (previewUrls[attachment.id] || previewLoadingIds.includes(attachment.id)) {
        return;
      }

      setPreviewLoadingIds((previous) => (previous.includes(attachment.id) ? previous : [...previous, attachment.id]));

      try {
        const response = await authFetch(`/reports/attachments/${attachment.id}/preview`);
        if (!response.ok) {
          throw new Error("Failed to load preview");
        }

        const blob = await response.blob();
        const objectUrl = window.URL.createObjectURL(blob);
        setPreviewUrls((previous) => ({ ...previous, [attachment.id]: objectUrl }));
        setPreviewFailedIds((previous) => previous.filter((value) => value !== attachment.id));
      } catch {
        setPreviewFailedIds((previous) => (previous.includes(attachment.id) ? previous : [...previous, attachment.id]));
      } finally {
        setPreviewLoadingIds((previous) => previous.filter((value) => value !== attachment.id));
      }
    },
    [authFetch, previewLoadingIds, previewUrls],
  );

  useEffect(() => {
    if (!isReviewModalOpen || !selectedReport) {
      return;
    }

    const imageAttachments = selectedReport.attachments.filter((attachment) => isImageAttachment(attachment));
    for (const attachment of imageAttachments) {
      void loadAttachmentPreview(attachment);
    }
  }, [isReviewModalOpen, loadAttachmentPreview, selectedReport]);

  const onApplyFilters = () => {
    if (page !== 1) {
      setPage(1);
      return;
    }
    void loadReports();
  };

  const onResolveSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!canModerateContent) {
      setError(t("access_denied_moderation", "Access denied: moderator, admin or superadmin role required"));
      return;
    }

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

  const downloadAttachment = async (attachment: ReportAttachmentItem) => {
    setDownloadingAttachmentId(attachment.id);

    try {
      const response = await authFetch(`/reports/attachments/${attachment.id}/download`);
      if (!response.ok) {
        let message = t("error_download_attachment", "Failed to download attachment");
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = t("error_download_attachment", "Failed to download attachment");
        }
        throw new Error(message);
      }

      const blob = await response.blob();
      const objectUrl = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = attachment.original_name || attachment.file_name;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(objectUrl);
    } catch (downloadError) {
      setError(extractErrorMessage(downloadError));
    } finally {
      setDownloadingAttachmentId(null);
    }
  };

  const openReportMessageInMessages = (report: ReportItem) => {
    if (report.target_type !== "message" || report.target_conversation_id === null) {
      return;
    }

    const params = new URLSearchParams();
    params.set("conversation_id", String(report.target_conversation_id));
    params.set("message_id", String(report.target_id));
    navigate(`/messages?${params.toString()}`);
  };

  const openReportListingInModeration = (report: ReportItem) => {
    const listingId = getReportListingId(report);
    if (listingId === null) {
      return;
    }

    const params = new URLSearchParams();
    params.set("listing_id", String(listingId));
    navigate(`/listings?${params.toString()}`);
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

  const chatAbusePresets = useMemo(() => {
    if (!selectedReport || selectedReport.target_type !== "message") {
      return [] as Array<{ id: string; label: string; action: ResolveAction; moderationAction: string; note: string }>;
    }

    return [
      {
        id: "chat-warning",
        label: t("preset_chat_warning", "Warning note"),
        action: "resolve" as ResolveAction,
        moderationAction: "",
        note: t("preset_note_chat_warning", "Message violates chat policy. Warning issued."),
      },
      {
        id: "chat-block",
        label: t("preset_chat_block_sender", "Block sender"),
        action: "resolve" as ResolveAction,
        moderationAction: "block",
        note: t("preset_note_chat_block_sender", "Sender blocked due to abusive chat behavior."),
      },
      {
        id: "chat-deactivate",
        label: t("preset_chat_deactivate_sender", "Deactivate sender"),
        action: "resolve" as ResolveAction,
        moderationAction: "deactivate",
        note: t("preset_note_chat_deactivate_sender", "Sender account deactivated after severe abuse in chat."),
      },
      {
        id: "chat-dismiss",
        label: t("preset_chat_false_positive", "Dismiss as false positive"),
        action: "dismiss" as ResolveAction,
        moderationAction: "",
        note: t("preset_note_chat_false_positive", "No policy violation detected in the reported message."),
      },
    ];
  }, [selectedReport, t]);

  const applyChatPreset = (preset: {
    action: ResolveAction;
    moderationAction: string;
    note: string;
  }) => {
    setResolveAction(preset.action);
    setModerationAction(preset.moderationAction);
    setResolutionNote(preset.note);
  };

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
          <option value="message">{t("target_message", "Message")}</option>
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
                        <strong>{targetTypeLabel(report.target_type, t)}</strong>
                        <span>{t("reporter", "Reporter")} #{formatInteger(report.reporter_user_id, language)}</span>
                        <span>{t("target", "target")} #{formatInteger(report.target_id, language)}</span>
                        {getReportListingId(report) !== null ? (
                          <span>
                            {t("listing_context", "Listing")} #{formatInteger(getReportListingId(report) ?? 0, language)}
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td>
                      <div className="users-name-cell">
                        <strong>{report.reason_code}</strong>
                        <span>{report.reason_text ?? t("no_reason_text", "No text provided")}</span>
                        {report.attachments.length > 0 ? (
                          <div className="reports-attachments-list">
                            {report.attachments.map((attachment) => (
                              <button
                                key={attachment.id}
                                type="button"
                                className="btn btn-ghost messages-attachment-btn"
                                disabled={downloadingAttachmentId === attachment.id}
                                onClick={() => void downloadAttachment(attachment)}
                              >
                                {downloadingAttachmentId === attachment.id
                                  ? t("downloading", "Downloading...")
                                  : `${t("evidence", "Evidence")}: ${attachment.original_name}`}
                              </button>
                            ))}
                          </div>
                        ) : null}
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
                      <div className="users-actions-cell">
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
            <div className="reports-detail-stack">
              <div className="dashboard-stats-grid reports-details-grid">
                <article className="dashboard-stat-group">
                  <h3>{t("report_details", "Report details")}</h3>
                  <p>
                    {t("status", "Status")}: <strong>{statusLabel(selectedReport.status, t)}</strong>
                  </p>
                  <p>
                    {t("reporter", "Reporter")}: <strong>#{formatInteger(selectedReport.reporter_user_id, language)}</strong>
                  </p>
                  <p>
                    {t("target", "Target")}: <strong>{targetTypeLabel(selectedReport.target_type, t)} #{formatInteger(selectedReport.target_id, language)}</strong>
                  </p>
                  {selectedReport.target_conversation_id !== null ? (
                    <p>
                      {t("conversation", "Conversation")}: <strong>#{formatInteger(selectedReport.target_conversation_id, language)}</strong>
                    </p>
                  ) : null}
                  {getReportListingId(selectedReport) !== null ? (
                    <p>
                      {t("listing_context", "Listing")}: <strong>#{formatInteger(getReportListingId(selectedReport) ?? 0, language)}</strong>
                    </p>
                  ) : null}
                  <p>
                    {t("created", "Created")}: <strong>{formatDateTime(selectedReport.created_at, language)}</strong>
                  </p>
                </article>

                <article className="dashboard-stat-group">
                  <h3>{t("reason", "Reason")}</h3>
                  <p><strong>{selectedReport.reason_code}</strong></p>
                  <p>{selectedReport.reason_text ?? t("no_reason_text", "No text provided")}</p>
                </article>
              </div>

              {selectedReport.target_type === "message" && selectedReport.target_conversation_id !== null || getReportListingId(selectedReport) !== null ? (
                <article className="dashboard-stat-group reports-related-actions-card">
                  <h3>{t("related_sections", "Related sections")}</h3>
                  <div className="reports-related-actions">
                    {selectedReport.target_type === "message" && selectedReport.target_conversation_id !== null ? (
                      <div className="reports-related-action-item">
                        <p>{t("messages_history", "Messages history")}</p>
                        <button
                          type="button"
                          className="btn btn-ghost"
                          onClick={() => openReportMessageInMessages(selectedReport)}
                        >
                          {t("open_in_messages", "Open in messages")}
                        </button>
                      </div>
                    ) : null}

                    {getReportListingId(selectedReport) !== null ? (
                      <div className="reports-related-action-item">
                        <p>{t("listings_moderation", "Listings moderation")}</p>
                        <button
                          type="button"
                          className="btn btn-ghost"
                          onClick={() => openReportListingInModeration(selectedReport)}
                        >
                          {t("open_in_listings", "Open in listings")}
                        </button>
                      </div>
                    ) : null}
                  </div>
                </article>
              ) : null}

              <article className="dashboard-stat-group reports-evidence-card">
                <h3>{t("evidence_files", "Evidence files")}</h3>
                {selectedReport.attachments.length === 0 ? (
                  <p className="reports-no-evidence">{t("no_evidence", "No evidence files attached")}</p>
                ) : (
                  <div className="reports-evidence-grid">
                    {selectedReport.attachments.map((attachment) => {
                      const previewUrl = previewUrls[attachment.id];
                      const previewLoading = previewLoadingIds.includes(attachment.id);
                      const previewFailed = previewFailedIds.includes(attachment.id);

                      return (
                        <article key={attachment.id} className="reports-evidence-item">
                          <div className="reports-evidence-preview">
                            {isImageAttachment(attachment) ? (
                              previewUrl ? (
                                <img src={previewUrl} alt={attachment.original_name} loading="lazy" />
                              ) : previewLoading ? (
                                <span>{t("loading_preview", "Loading preview...")}</span>
                              ) : previewFailed ? (
                                <span>{t("preview_unavailable", "Preview unavailable")}</span>
                              ) : (
                                <button
                                  type="button"
                                  className="btn btn-ghost"
                                  onClick={() => void loadAttachmentPreview(attachment)}
                                >
                                  {t("load_preview", "Load preview")}
                                </button>
                              )
                            ) : (
                              <span>{attachment.mime_type}</span>
                            )}
                          </div>

                          <div className="reports-evidence-meta">
                            <strong>{attachment.original_name}</strong>
                            <span>{t("mime_type", "MIME")}: {attachment.mime_type}</span>
                            <span>{t("size", "Size")}: {formatFileSize(attachment.file_size, language)}</span>
                            <span>{t("uploaded", "Uploaded")}: {formatDateTime(attachment.created_at, language)}</span>
                          </div>

                          <button
                            type="button"
                            className="btn btn-ghost messages-attachment-btn"
                            disabled={downloadingAttachmentId === attachment.id}
                            onClick={() => void downloadAttachment(attachment)}
                          >
                            {downloadingAttachmentId === attachment.id ? t("downloading", "Downloading...") : t("download", "Download")}
                          </button>
                        </article>
                      );
                    })}
                  </div>
                )}
              </article>

              {chatAbusePresets.length > 0 ? (
                <article className="dashboard-stat-group reports-presets-card">
                  <h3>{t("quick_presets", "Quick presets")}</h3>
                  <div className="users-actions-cell reports-presets-row">
                    {chatAbusePresets.map((preset) => (
                      <button
                        key={preset.id}
                        type="button"
                        className="btn btn-ghost"
                        disabled={!canModerateContent}
                        onClick={() => applyChatPreset(preset)}
                      >
                        {preset.label}
                      </button>
                    ))}
                  </div>
                </article>
              ) : null}

              <form className="reports-form" onSubmit={onResolveSubmit}>
                {!canModerateContent ? (
                  <div className="dashboard-error">
                    {t("read_only_mode", "Read-only mode: moderation actions require moderator, admin or superadmin role")}
                  </div>
                ) : null}

                <div className="reports-form-grid">
                  <label>
                    {t("action", "Action")}
                    <select
                      className="users-filter-select"
                      value={resolveAction}
                      onChange={(event) => setResolveAction(event.target.value as ResolveAction)}
                      disabled={!canModerateContent}
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
                      disabled={!canModerateContent || moderationOptions.length === 0}
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
                    disabled={!canModerateContent}
                  />
                </label>

                <div className="users-actions-cell">
                  <button type="submit" className="btn btn-primary" disabled={!canModerateContent || isSubmitting}>
                    {isSubmitting ? t("applying", "Applying...") : t("apply_action", "Apply action")}
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={!canModerateContent}
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
            </div>
          ) : null}
        </div>
      </Modal>
    </section>
  );
}
