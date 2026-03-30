import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useAuth } from "../../app/auth/AuthContext";
import { usePageI18n } from "../../app/i18n/I18nContext";
import { formatDateTime, formatInteger } from "../../shared/i18n/format";
import { ImagePreviewOverlay } from "../common/ImagePreviewOverlay";
import { Modal } from "../common/Modal";

type ReportStatus = "open" | "resolved" | "dismissed";
type ReportTargetType = "listing" | "message";
type ResolveAction = "resolve" | "dismiss";
type ListingStatus = "draft" | "pending_review" | "published" | "rejected" | "archived" | "inactive" | "sold";
type TransactionType = "sale" | "rent_long" | "rent_daily";

type ReportItem = {
  id: number;
  reporter_user_id: number;
  target_type: ReportTargetType;
  target_id: number;
  target_conversation_id: number | null;
  target_listing_id: number | null;
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

type ListingItem = {
  id: number;
  owner_id: number;
  category_id: number;
  transaction_type: TransactionType;
  title: string;
  description: string;
  price: string | number;
  currency: string;
  city: string;
  address_line: string | null;
  status: ListingStatus;
  view_count: number;
  favorite_count: number;
  created_at: string;
  updated_at: string;
};

type ListingListResponse = {
  items: ListingItem[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
};

type ListingMediaItem = {
  id: number;
  listing_id: number;
  original_name: string;
  mime_type: string;
  file_size: number;
  sort_order: number;
  is_primary: boolean;
  created_at: string;
  file_url: string;
  thumbnail_url: string | null;
};

type ListingMediaListResponse = {
  items: ListingMediaItem[];
};

type MessageItem = {
  id: number;
  conversation_id: number;
  sender_id: number;
  message_type: string;
  text_body: string | null;
  is_read: boolean;
  sent_at: string;
  edited_at: string | null;
  deleted_at: string | null;
  attachments: unknown[];
};

type MessageListResponse = {
  items: MessageItem[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
};

type AdminUserDetailResponse = {
  id: number;
  full_name: string;
  email: string;
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

function listingStatusLabel(status: ListingStatus, t: (key: string, fallback: string) => string): string {
  if (status === "pending_review") {
    return t("status_pending_review", "Pending review");
  }
  if (status === "published") {
    return t("status_published", "Published");
  }
  if (status === "rejected") {
    return t("status_rejected", "Rejected");
  }
  if (status === "inactive") {
    return t("status_inactive", "Inactive");
  }
  if (status === "sold") {
    return t("status_sold", "Sold");
  }
  if (status === "archived") {
    return t("status_archived", "Archived");
  }
  return t("status_draft", "Draft");
}

function transactionLabel(value: TransactionType, t: (key: string, fallback: string) => string): string {
  if (value === "sale") {
    return t("transaction_sale", "Sale");
  }
  if (value === "rent_long") {
    return t("transaction_rent_long", "Long rent");
  }
  return t("transaction_rent_daily", "Daily rent");
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
  return t("target_message", "Message");
}

function formatPrice(value: string | number, currency: string, language: "en" | "ru"): string {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return `${value} ${currency}`;
  }
  return `${formatInteger(numeric, language)} ${currency}`;
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

function getReportListingId(report: ReportItem): number | null {
  if (report.target_listing_id !== null) {
    return report.target_listing_id;
  }
  if (report.target_type === "listing") {
    return report.target_id;
  }
  return null;
}

function isImageMedia(item: ListingMediaItem): boolean {
  return item.mime_type.toLowerCase().startsWith("image/");
}

async function getApiErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
    if (typeof payload?.error?.message === "string") {
      return payload.error.message;
    }
    if (typeof payload?.detail === "string") {
      return payload.detail;
    }
  } catch {
    return fallback;
  }
  return fallback;
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

  const [listingContext, setListingContext] = useState<ListingItem | null>(null);
  const [isListingContextLoading, setIsListingContextLoading] = useState(false);
  const [listingContextError, setListingContextError] = useState<string | null>(null);
  const [listingMedia, setListingMedia] = useState<ListingMediaItem[]>([]);
  const [isListingMediaLoading, setIsListingMediaLoading] = useState(false);
  const [listingMediaError, setListingMediaError] = useState<string | null>(null);
  const [listingMediaPreviewUrls, setListingMediaPreviewUrls] = useState<Record<number, string>>({});
  const [listingMediaPreviewLoadingIds, setListingMediaPreviewLoadingIds] = useState<number[]>([]);
  const [listingMediaPreviewFailedIds, setListingMediaPreviewFailedIds] = useState<number[]>([]);
  const [openingListingImageId, setOpeningListingImageId] = useState<number | null>(null);
  const [listingImagePreviewItem, setListingImagePreviewItem] = useState<ListingMediaItem | null>(null);
  const [listingImagePreviewUrl, setListingImagePreviewUrl] = useState<string | null>(null);
  const [downloadingListingMediaId, setDownloadingListingMediaId] = useState<number | null>(null);

  const [messageContext, setMessageContext] = useState<MessageItem | null>(null);
  const [isMessageContextLoading, setIsMessageContextLoading] = useState(false);
  const [messageContextError, setMessageContextError] = useState<string | null>(null);
  const [messageSender, setMessageSender] = useState<AdminUserDetailResponse | null>(null);
  const [isMessageSenderLoading, setIsMessageSenderLoading] = useState(false);
  const [messageSenderError, setMessageSenderError] = useState<string | null>(null);

  const closeListingImagePreview = useCallback(() => {
    setListingImagePreviewItem(null);
    setListingImagePreviewUrl((previousUrl) => {
      if (previousUrl) {
        window.URL.revokeObjectURL(previousUrl);
      }
      return null;
    });
  }, []);

  const closeReviewModal = () => {
    setIsReviewModalOpen(false);
    closeListingImagePreview();
  };

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

  const loadListingMediaThumbnail = useCallback(
    async (mediaItem: ListingMediaItem) => {
      if (!isImageMedia(mediaItem)) {
        return;
      }

      if (listingMediaPreviewUrls[mediaItem.id] || listingMediaPreviewLoadingIds.includes(mediaItem.id)) {
        return;
      }

      setListingMediaPreviewLoadingIds((previous) => (
        previous.includes(mediaItem.id) ? previous : [...previous, mediaItem.id]
      ));

      try {
        const response = await authFetch(`/listing-media/${mediaItem.id}/thumbnail/my`);
        if (!response.ok) {
          throw new Error("Failed to load thumbnail");
        }

        const blob = await response.blob();
        const objectUrl = window.URL.createObjectURL(blob);
        setListingMediaPreviewUrls((previous) => {
          const previousUrl = previous[mediaItem.id];
          if (previousUrl) {
            window.URL.revokeObjectURL(previousUrl);
          }
          return { ...previous, [mediaItem.id]: objectUrl };
        });
        setListingMediaPreviewFailedIds((previous) => previous.filter((value) => value !== mediaItem.id));
      } catch {
        setListingMediaPreviewFailedIds((previous) => (
          previous.includes(mediaItem.id) ? previous : [...previous, mediaItem.id]
        ));
      } finally {
        setListingMediaPreviewLoadingIds((previous) => previous.filter((value) => value !== mediaItem.id));
      }
    },
    [authFetch, listingMediaPreviewLoadingIds, listingMediaPreviewUrls],
  );

  const downloadListingMedia = useCallback(async (mediaItem: ListingMediaItem) => {
    setDownloadingListingMediaId(mediaItem.id);
    setListingMediaError(null);

    try {
      const response = await authFetch(`/listing-media/${mediaItem.id}/download/my`);
      if (!response.ok) {
        const message = await getApiErrorMessage(response, "Failed to download listing media");
        throw new Error(message);
      }

      const blob = await response.blob();
      const objectUrl = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = mediaItem.original_name;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(objectUrl);
    } catch (downloadError) {
      setListingMediaError(extractErrorMessage(downloadError));
    } finally {
      setDownloadingListingMediaId(null);
    }
  }, [authFetch]);

  const openListingImagePreview = useCallback(async (mediaItem: ListingMediaItem) => {
    if (!isImageMedia(mediaItem)) {
      void downloadListingMedia(mediaItem);
      return;
    }

    setOpeningListingImageId(mediaItem.id);
    setListingMediaError(null);

    try {
      const response = await authFetch(`/listing-media/${mediaItem.id}/download/my`);
      if (!response.ok) {
        const message = await getApiErrorMessage(response, "Failed to load listing image");
        throw new Error(message);
      }

      const blob = await response.blob();
      const objectUrl = window.URL.createObjectURL(blob);

      setListingImagePreviewUrl((previousUrl) => {
        if (previousUrl) {
          window.URL.revokeObjectURL(previousUrl);
        }
        return objectUrl;
      });
      setListingImagePreviewItem(mediaItem);
    } catch (previewError) {
      setListingMediaError(extractErrorMessage(previewError));
    } finally {
      setOpeningListingImageId(null);
    }
  }, [authFetch, downloadListingMedia]);

  useEffect(() => {
    setResolveAction("resolve");
    setModerationAction("");
    setResolutionNote(selectedReport?.resolution_note ?? "");
  }, [selectedReport?.id, selectedReport?.resolution_note]);

  useEffect(() => {
    if (!isReviewModalOpen || !selectedReport || selectedReport.target_type !== "listing") {
      setListingContext(null);
      setIsListingContextLoading(false);
      setListingContextError(null);
      setListingMedia([]);
      setIsListingMediaLoading(false);
      setListingMediaError(null);
      setListingMediaPreviewLoadingIds([]);
      setListingMediaPreviewFailedIds([]);
      setListingMediaPreviewUrls((previous) => {
        for (const previewUrl of Object.values(previous)) {
          window.URL.revokeObjectURL(previewUrl);
        }
        return {};
      });
      setOpeningListingImageId(null);
      setDownloadingListingMediaId(null);
      closeListingImagePreview();
      return;
    }

    const listingId = getReportListingId(selectedReport);
    if (listingId === null) {
      setListingContextError(t("error_listing_context_missing", "Listing context is missing for this report"));
      return;
    }

    let cancelled = false;

    const load = async () => {
      setListingContext(null);
      setIsListingContextLoading(true);
      setListingContextError(null);
      setListingMedia([]);
      setIsListingMediaLoading(true);
      setListingMediaError(null);
      setListingMediaPreviewLoadingIds([]);
      setListingMediaPreviewFailedIds([]);
      setListingMediaPreviewUrls((previous) => {
        for (const previewUrl of Object.values(previous)) {
          window.URL.revokeObjectURL(previewUrl);
        }
        return {};
      });
      setOpeningListingImageId(null);
      setDownloadingListingMediaId(null);
      closeListingImagePreview();

      try {
        const listingParams = new URLSearchParams();
        listingParams.set("listing_id", String(listingId));
        listingParams.set("page", "1");
        listingParams.set("page_size", "1");

        const listingResponse = await authFetch(`/listings/admin/moderation?${listingParams.toString()}`);
        if (!listingResponse.ok) {
          const message = await getApiErrorMessage(listingResponse, "Failed to load listing context");
          throw new Error(message);
        }

        const listingPayload = (await listingResponse.json()) as ListingListResponse;
        const listingItem = listingPayload.items[0] ?? null;
        if (listingItem === null) {
          throw new Error(t("error_listing_not_found", "Listing not found"));
        }

        if (!cancelled) {
          setListingContext(listingItem);
        }
      } catch (contextError) {
        if (!cancelled) {
          setListingContextError(extractErrorMessage(contextError));
        }
      } finally {
        if (!cancelled) {
          setIsListingContextLoading(false);
        }
      }

      try {
        const mediaResponse = await authFetch(`/listing-media/listings/${listingId}/my`);
        if (!mediaResponse.ok) {
          const message = await getApiErrorMessage(mediaResponse, "Failed to load listing photos");
          throw new Error(message);
        }

        const mediaPayload = (await mediaResponse.json()) as ListingMediaListResponse;
        if (!cancelled) {
          setListingMedia(mediaPayload.items);
        }
      } catch (mediaError) {
        if (!cancelled) {
          setListingMediaError(extractErrorMessage(mediaError));
        }
      } finally {
        if (!cancelled) {
          setIsListingMediaLoading(false);
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [authFetch, closeListingImagePreview, isReviewModalOpen, selectedReport, t]);

  useEffect(() => {
    if (!isReviewModalOpen || selectedReport?.target_type !== "listing" || listingMedia.length === 0) {
      return;
    }

    for (const mediaItem of listingMedia) {
      if (isImageMedia(mediaItem)) {
        void loadListingMediaThumbnail(mediaItem);
      }
    }
  }, [isReviewModalOpen, listingMedia, loadListingMediaThumbnail, selectedReport?.target_type]);

  useEffect(() => {
    return () => {
      for (const previewUrl of Object.values(listingMediaPreviewUrls)) {
        window.URL.revokeObjectURL(previewUrl);
      }
    };
  }, [listingMediaPreviewUrls]);

  useEffect(() => {
    return () => {
      if (listingImagePreviewUrl) {
        window.URL.revokeObjectURL(listingImagePreviewUrl);
      }
    };
  }, [listingImagePreviewUrl]);

  useEffect(() => {
    if (!isReviewModalOpen || !selectedReport || selectedReport.target_type !== "message") {
      setMessageContext(null);
      setIsMessageContextLoading(false);
      setMessageContextError(null);
      setMessageSender(null);
      setIsMessageSenderLoading(false);
      setMessageSenderError(null);
      return;
    }

    if (selectedReport.target_conversation_id === null) {
      setMessageContext(null);
      setMessageContextError(t("error_conversation_missing", "Conversation context is missing for this message report"));
      setMessageSender(null);
      setMessageSenderError(null);
      return;
    }

    let cancelled = false;

    const load = async () => {
      setMessageContext(null);
      setIsMessageContextLoading(true);
      setMessageContextError(null);
      setMessageSender(null);
      setIsMessageSenderLoading(false);
      setMessageSenderError(null);

      try {
        const params = new URLSearchParams();
        params.set("conversation_id", String(selectedReport.target_conversation_id));
        params.set("page", "1");
        params.set("page_size", "30");
        params.set("message_id", String(selectedReport.target_id));

        const messageResponse = await authFetch(`/admin/messages?${params.toString()}`);
        if (!messageResponse.ok) {
          const message = await getApiErrorMessage(messageResponse, "Failed to load message context");
          throw new Error(message);
        }

        const messagePayload = (await messageResponse.json()) as MessageListResponse;
        const targetMessage = messagePayload.items.find((item) => item.id === selectedReport.target_id) ?? null;
        if (targetMessage === null) {
          throw new Error(t("error_message_not_found", "Reported message not found in conversation"));
        }

        if (cancelled) {
          return;
        }

        setMessageContext(targetMessage);
        setIsMessageSenderLoading(true);

        try {
          const senderResponse = await authFetch(`/admin/users/${targetMessage.sender_id}`);
          if (!senderResponse.ok) {
            const message = await getApiErrorMessage(senderResponse, "Failed to load sender info");
            throw new Error(message);
          }

          const senderPayload = (await senderResponse.json()) as AdminUserDetailResponse;
          if (!cancelled) {
            setMessageSender(senderPayload);
          }
        } catch (senderError) {
          if (!cancelled) {
            setMessageSenderError(extractErrorMessage(senderError));
          }
        } finally {
          if (!cancelled) {
            setIsMessageSenderLoading(false);
          }
        }
      } catch (contextError) {
        if (!cancelled) {
          setMessageContextError(extractErrorMessage(contextError));
        }
      } finally {
        if (!cancelled) {
          setIsMessageContextLoading(false);
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [authFetch, isReviewModalOpen, selectedReport, t]);

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
        const message = await getApiErrorMessage(response, t("error_process_report", "Failed to process report"));
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
                        <span>{t("target", "Target")} #{formatInteger(report.target_id, language)}</span>
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
        onClose={closeReviewModal}
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

              {selectedReport.target_type === "listing" ? (
                <article className="dashboard-stat-group reports-context-card">
                  <div className="reports-context-head">
                    <h3>{t("listing_context_details", "Listing context")}</h3>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      disabled={getReportListingId(selectedReport) === null}
                      onClick={() => openReportListingInModeration(selectedReport)}
                    >
                      {t("open_listing", "Open listing")}
                    </button>
                  </div>

                  {listingContextError ? <p className="reports-no-evidence">{listingContextError}</p> : null}

                  {isListingContextLoading ? (
                    <p className="reports-no-evidence">{t("loading_listing_context", "Loading listing context...")}</p>
                  ) : null}

                  {listingContext ? (
                    <>
                      <div className="reports-context-meta">
                        <p>{t("title_label", "Title")}: <strong>{listingContext.title}</strong></p>
                        <p>{t("status", "Status")}: <strong>{listingStatusLabel(listingContext.status, t)}</strong></p>
                        <p>{t("transaction", "Transaction")}: <strong>{transactionLabel(listingContext.transaction_type, t)}</strong></p>
                        <p>{t("price", "Price")}: <strong>{formatPrice(listingContext.price, listingContext.currency, language)}</strong></p>
                        <p>{t("owner", "Owner")}: <strong>#{formatInteger(listingContext.owner_id, language)}</strong></p>
                        <p>{t("category", "Category")}: <strong>#{formatInteger(listingContext.category_id, language)}</strong></p>
                        <p>{t("location", "Location")}: <strong>{listingContext.city}{listingContext.address_line ? `, ${listingContext.address_line}` : ""}</strong></p>
                        <p>{t("views", "Views")}: <strong>{formatInteger(listingContext.view_count, language)}</strong></p>
                        <p>{t("favorites", "Favorites")}: <strong>{formatInteger(listingContext.favorite_count, language)}</strong></p>
                      </div>

                      <p className="reports-context-description">{listingContext.description}</p>
                    </>
                  ) : null}

                  <div className="listings-media-block">
                    <h4>{t("photos", "Photos")}</h4>

                    {listingMediaError ? <p className="reports-no-evidence">{listingMediaError}</p> : null}

                    {isListingMediaLoading ? (
                      <p className="reports-no-evidence">{t("loading_photos", "Loading photos...")}</p>
                    ) : listingMedia.length === 0 ? (
                      <p className="reports-no-evidence">{t("no_photos", "No photos attached")}</p>
                    ) : (
                      <div className="listings-media-grid">
                        {listingMedia.map((mediaItem) => {
                          const previewUrl = listingMediaPreviewUrls[mediaItem.id];
                          const previewLoading = listingMediaPreviewLoadingIds.includes(mediaItem.id);
                          const previewFailed = listingMediaPreviewFailedIds.includes(mediaItem.id);

                          return (
                            <article key={mediaItem.id} className="listings-media-item">
                              <div className="listings-media-thumb">
                                {isImageMedia(mediaItem) ? (
                                  previewUrl ? (
                                    <button
                                      type="button"
                                      className="listings-media-thumb-btn"
                                      onClick={() => void openListingImagePreview(mediaItem)}
                                    >
                                      <img src={previewUrl} alt={mediaItem.original_name} loading="lazy" />
                                    </button>
                                  ) : previewLoading ? (
                                    <span>{t("loading_preview", "Loading preview...")}</span>
                                  ) : previewFailed ? (
                                    <button
                                      type="button"
                                      className="btn btn-ghost"
                                      onClick={() => void loadListingMediaThumbnail(mediaItem)}
                                    >
                                      {t("retry_preview", "Retry preview")}
                                    </button>
                                  ) : (
                                    <button
                                      type="button"
                                      className="btn btn-ghost"
                                      onClick={() => void loadListingMediaThumbnail(mediaItem)}
                                    >
                                      {t("load_preview", "Load preview")}
                                    </button>
                                  )
                                ) : (
                                  <span>{mediaItem.mime_type}</span>
                                )}
                              </div>

                              <div className="listings-media-meta">
                                <strong>{mediaItem.original_name}</strong>
                                <span>{t("size", "Size")}: {formatFileSize(mediaItem.file_size, language)}</span>
                                <span>{t("uploaded", "Uploaded")}: {formatDateTime(mediaItem.created_at, language)}</span>
                              </div>

                              <div className="users-actions-cell">
                                <button
                                  type="button"
                                  className="btn btn-ghost"
                                  disabled={openingListingImageId === mediaItem.id || downloadingListingMediaId === mediaItem.id}
                                  onClick={() => {
                                    if (isImageMedia(mediaItem)) {
                                      void openListingImagePreview(mediaItem);
                                      return;
                                    }
                                    void downloadListingMedia(mediaItem);
                                  }}
                                >
                                  {openingListingImageId === mediaItem.id
                                    ? t("loading_photo", "Loading photo...")
                                    : downloadingListingMediaId === mediaItem.id
                                      ? t("downloading", "Downloading...")
                                      : isImageMedia(mediaItem)
                                        ? t("open_image", "Open image")
                                        : t("download", "Download")}
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-ghost"
                                  disabled={downloadingListingMediaId === mediaItem.id}
                                  onClick={() => void downloadListingMedia(mediaItem)}
                                >
                                  {downloadingListingMediaId === mediaItem.id ? t("downloading", "Downloading...") : t("download", "Download")}
                                </button>
                              </div>
                            </article>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </article>
              ) : null}

              {selectedReport.target_type === "message" ? (
                <article className="dashboard-stat-group reports-context-card">
                  <div className="reports-context-head">
                    <h3>{t("message_context", "Message context")}</h3>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      disabled={selectedReport.target_conversation_id === null}
                      onClick={() => openReportMessageInMessages(selectedReport)}
                    >
                      {t("open_in_messages", "Open in messages")}
                    </button>
                  </div>

                  {messageContextError ? <p className="reports-no-evidence">{messageContextError}</p> : null}

                  {isMessageContextLoading ? (
                    <p className="reports-no-evidence">{t("loading_message_context", "Loading message context...")}</p>
                  ) : null}

                  {messageContext ? (
                    <>
                      <div className="reports-context-meta">
                        <p>
                          {t("sender", "Sender")}: <strong>{messageSender ? `${messageSender.full_name} (#${formatInteger(messageContext.sender_id, language)})` : `#${formatInteger(messageContext.sender_id, language)}`}</strong>
                        </p>
                        {messageSender?.email ? (
                          <p>{t("email", "Email")}: <strong>{messageSender.email}</strong></p>
                        ) : null}
                        {isMessageSenderLoading ? <p>{t("loading_sender", "Loading sender...")}</p> : null}
                        {messageSenderError ? <p>{messageSenderError}</p> : null}
                        <p>{t("sent_at", "Sent at")}: <strong>{formatDateTime(messageContext.sent_at, language)}</strong></p>
                      </div>
                      <p className="reports-message-body">{messageContext.text_body ?? t("no_message_text", "Message has no text")}</p>
                    </>
                  ) : null}
                </article>
              ) : null}

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

      <ImagePreviewOverlay
        open={listingImagePreviewItem !== null && listingImagePreviewUrl !== null}
        imageSrc={listingImagePreviewUrl}
        imageAlt={listingImagePreviewItem?.original_name ?? t("image_preview", "Image preview")}
        onClose={closeListingImagePreview}
        onDownload={() => {
          if (!listingImagePreviewItem) {
            return;
          }
          void downloadListingMedia(listingImagePreviewItem);
        }}
        downloadLabel={t("download", "Download")}
        downloadingLabel={t("downloading", "Downloading...")}
        closeLabel={t("close", "Close")}
        isDownloading={
          listingImagePreviewItem !== null &&
          downloadingListingMediaId === listingImagePreviewItem.id
        }
      />
    </section>
  );
}
