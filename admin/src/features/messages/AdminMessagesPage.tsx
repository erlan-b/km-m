import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "../../app/auth/AuthContext";
import { usePageI18n } from "../../app/i18n/I18nContext";
import { formatDateTime, formatInteger } from "../../shared/i18n/format";
import { Modal } from "../common/Modal";
import { ImagePreviewOverlay } from "../common/ImagePreviewOverlay";

type ConversationItem = {
  id: number;
  listing_id: number;
  created_by_user_id: number;
  participant_a_id: number;
  participant_b_id: number;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
  last_message_preview: string | null;
  unread_count: number;
};

type ConversationListResponse = {
  items: ConversationItem[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
};

type MessageAttachmentItem = {
  id: number;
  message_id: number;
  file_name: string;
  original_name: string;
  mime_type: string;
  file_size: number;
  file_path: string;
  created_at: string;
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
  attachments: MessageAttachmentItem[];
};

type MessageListResponse = {
  items: MessageItem[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
};

type ConversationFilters = {
  user_id: string;
  listing_id: string;
  conversation_id: string;
};

const initialFilters: ConversationFilters = {
  user_id: "",
  listing_id: "",
  conversation_id: "",
};

function extractErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

function parsePositiveInt(raw: string): number | null {
  const value = raw.trim();
  if (!value) {
    return null;
  }

  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }

  return parsed;
}

function readPageParam(value: string | null): number {
  if (value === null) {
    return 1;
  }

  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return 1;
  }

  return parsed;
}

function readConversationFiltersFromSearchParams(searchParams: URLSearchParams): ConversationFilters {
  return {
    user_id: searchParams.get("user_id") ?? "",
    listing_id: searchParams.get("listing_id") ?? "",
    conversation_id: searchParams.get("conversation_id") ?? "",
  };
}

function areConversationFiltersEqual(left: ConversationFilters, right: ConversationFilters): boolean {
  return (
    left.user_id === right.user_id &&
    left.listing_id === right.listing_id &&
    left.conversation_id === right.conversation_id
  );
}

function buildMessagesSearchParams(
  filters: ConversationFilters,
  conversationPage: number,
  messagesPage: number,
  selectedConversationId: number | null,
  messageId: number | null,
): URLSearchParams {
  const params = new URLSearchParams();

  const userId = parsePositiveInt(filters.user_id);
  if (userId !== null) {
    params.set("user_id", String(userId));
  }

  const listingId = parsePositiveInt(filters.listing_id);
  if (listingId !== null) {
    params.set("listing_id", String(listingId));
  }

  const conversationId = selectedConversationId ?? parsePositiveInt(filters.conversation_id);
  if (conversationId !== null) {
    params.set("conversation_id", String(conversationId));
  }

  if (messageId !== null) {
    params.set("message_id", String(messageId));
  }

  if (conversationPage > 1) {
    params.set("page", String(conversationPage));
  }

  if (messagesPage > 1) {
    params.set("messages_page", String(messagesPage));
  }

  return params;
}

function formatFileSize(bytes: number, language: "en" | "ru"): string {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return "-";
  }

  if (bytes < 1024) {
    return `${formatInteger(bytes, language)} B`;
  }

  const kb = bytes / 1024;
  if (kb < 1024) {
    return `${kb.toFixed(1)} KB`;
  }

  const mb = kb / 1024;
  return `${mb.toFixed(2)} MB`;
}

function isImageAttachment(attachment: MessageAttachmentItem): boolean {
  return attachment.mime_type.toLowerCase().startsWith("image/");
}

export function AdminMessagesPage() {
  const { authFetch } = useAuth();
  const { t, language } = usePageI18n("messages");
  const [searchParams, setSearchParams] = useSearchParams();

  const [draftFilters, setDraftFilters] = useState<ConversationFilters>(() => readConversationFiltersFromSearchParams(searchParams));
  const [appliedFilters, setAppliedFilters] = useState<ConversationFilters>(() => readConversationFiltersFromSearchParams(searchParams));
  const [hasSubmittedFilters, setHasSubmittedFilters] = useState(
    () => (
      parsePositiveInt(searchParams.get("user_id") ?? "") !== null ||
      parsePositiveInt(searchParams.get("conversation_id") ?? "") !== null
    ),
  );

  const [conversationPage, setConversationPage] = useState(() => readPageParam(searchParams.get("page")));
  const [conversations, setConversations] = useState<ConversationListResponse | null>(null);
  const [isConversationsLoading, setIsConversationsLoading] = useState(false);
  const [conversationsError, setConversationsError] = useState<string | null>(null);

  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(null);

  const [messagesPage, setMessagesPage] = useState(() => readPageParam(searchParams.get("messages_page")));
  const [messages, setMessages] = useState<MessageListResponse | null>(null);
  const [isMessagesLoading, setIsMessagesLoading] = useState(false);
  const [messagesError, setMessagesError] = useState<string | null>(null);
  const [isTranscriptModalOpen, setIsTranscriptModalOpen] = useState(false);
  const [openTranscriptWhenConversationReady, setOpenTranscriptWhenConversationReady] = useState(
    () => (
      parsePositiveInt(searchParams.get("conversation_id") ?? "") !== null ||
      parsePositiveInt(searchParams.get("message_id") ?? "") !== null
    ),
  );

  const [downloadingAttachmentId, setDownloadingAttachmentId] = useState<number | null>(null);
  const [openingImagePreviewId, setOpeningImagePreviewId] = useState<number | null>(null);
  const [messageImagePreviewAttachment, setMessageImagePreviewAttachment] = useState<MessageAttachmentItem | null>(null);
  const [messageImagePreviewUrl, setMessageImagePreviewUrl] = useState<string | null>(null);
  const [pendingMessageId, setPendingMessageId] = useState<number | null>(() => parsePositiveInt(searchParams.get("message_id") ?? ""));
  const [highlightedMessageId, setHighlightedMessageId] = useState<number | null>(() => parsePositiveInt(searchParams.get("message_id") ?? ""));

  const [inlineImageUrls, setInlineImageUrls] = useState<Record<number, string>>({});
  const [inlineImageLoadingIds, setInlineImageLoadingIds] = useState<number[]>([]);
  const [inlineImageFailedIds, setInlineImageFailedIds] = useState<number[]>([]);

  const messageNodeRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const lastQueryFilterKey = useRef("");
  const inlineImageUrlsRef = useRef<Record<number, string>>({});

  const appliedUserId = useMemo(() => parsePositiveInt(appliedFilters.user_id), [appliedFilters.user_id]);
  const appliedListingId = useMemo(() => parsePositiveInt(appliedFilters.listing_id), [appliedFilters.listing_id]);
  const appliedConversationId = useMemo(() => parsePositiveInt(appliedFilters.conversation_id), [appliedFilters.conversation_id]);

  const selectedConversation = useMemo(() => {
    if (!conversations || selectedConversationId === null) {
      return null;
    }
    return conversations.items.find((item) => item.id === selectedConversationId) ?? null;
  }, [conversations, selectedConversationId]);

  const conversationRows = useMemo(() => conversations?.items ?? [], [conversations]);
  const messageRows = useMemo(() => messages?.items ?? [], [messages]);

  useEffect(() => {
    inlineImageUrlsRef.current = inlineImageUrls;
  }, [inlineImageUrls]);

  useEffect(() => {
    const queryFilters = readConversationFiltersFromSearchParams(searchParams);
    const shouldSubmitFilters = (
      parsePositiveInt(queryFilters.user_id) !== null ||
      parsePositiveInt(queryFilters.conversation_id) !== null
    );
    const queryConversationPage = readPageParam(searchParams.get("page"));
    const queryMessagesPage = readPageParam(searchParams.get("messages_page"));
    const queryMessageId = parsePositiveInt(searchParams.get("message_id") ?? "");
    const queryConversationId = parsePositiveInt(queryFilters.conversation_id);
    const queryWantsTranscript = queryConversationId !== null || queryMessageId !== null;
    const filterKey = `${queryFilters.user_id}|${queryFilters.listing_id}|${queryFilters.conversation_id}`;
    const filtersChanged = lastQueryFilterKey.current !== filterKey;

    lastQueryFilterKey.current = filterKey;

    setDraftFilters((previous) => (areConversationFiltersEqual(previous, queryFilters) ? previous : queryFilters));
    setAppliedFilters((previous) => (areConversationFiltersEqual(previous, queryFilters) ? previous : queryFilters));
    setHasSubmittedFilters((previous) => (previous === shouldSubmitFilters ? previous : shouldSubmitFilters));
    setConversationPage((previous) => (previous === queryConversationPage ? previous : queryConversationPage));
    setMessagesPage((previous) => (previous === queryMessagesPage ? previous : queryMessagesPage));
    setPendingMessageId((previous) => (previous === queryMessageId ? previous : queryMessageId));
    setHighlightedMessageId((previous) => (previous === queryMessageId ? previous : queryMessageId));
    setOpenTranscriptWhenConversationReady((previous) => (previous === queryWantsTranscript ? previous : queryWantsTranscript));

    if (filtersChanged) {
      setSelectedConversationId(null);
      setConversations(null);
      setMessages(null);
      setConversationsError(null);
      setMessagesError(null);
      setIsTranscriptModalOpen(false);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!openTranscriptWhenConversationReady || selectedConversationId === null) {
      return;
    }

    setIsTranscriptModalOpen(true);
    setOpenTranscriptWhenConversationReady(false);
  }, [openTranscriptWhenConversationReady, selectedConversationId]);

  const loadConversations = useCallback(async () => {
    if (!hasSubmittedFilters) {
      return;
    }

    if (appliedConversationId !== null) {
      setIsConversationsLoading(true);
      setConversationsError(null);

      try {
        const response = await authFetch(`/admin/messages/conversations/${appliedConversationId}`);
        if (!response.ok) {
          let message = t("error_load_conversations", "Failed to load conversations");
          try {
            const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
            if (typeof payload?.error?.message === "string") {
              message = payload.error.message;
            } else if (typeof payload?.detail === "string") {
              message = payload.detail;
            }
          } catch {
            message = t("error_load_conversations", "Failed to load conversations");
          }
          throw new Error(message);
        }

        const conversation = (await response.json()) as ConversationItem;
        setConversations({
          items: [conversation],
          page: 1,
          page_size: 1,
          total_items: 1,
          total_pages: 1,
        });
        setSelectedConversationId(conversation.id);
        setConversationPage(1);
      } catch (error) {
        setConversationsError(extractErrorMessage(error, t("error_load_conversations", "Failed to load conversations")));
      } finally {
        setIsConversationsLoading(false);
      }
      return;
    }

    if (appliedUserId === null) {
      setConversations(null);
      setSelectedConversationId(null);
      setConversationsError(t("user_or_conversation_required", "User ID or conversation ID is required for conversation oversight"));
      return;
    }

    setIsConversationsLoading(true);
    setConversationsError(null);

    try {
      const params = new URLSearchParams();
      params.set("page", String(conversationPage));
      params.set("page_size", "20");
      params.set("user_id", String(appliedUserId));

      if (appliedListingId !== null) {
        params.set("listing_id", String(appliedListingId));
      }

      const response = await authFetch(`/admin/messages/conversations?${params.toString()}`);
      if (!response.ok) {
        let message = t("error_load_conversations", "Failed to load conversations");
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = t("error_load_conversations", "Failed to load conversations");
        }
        throw new Error(message);
      }

      const payload = (await response.json()) as ConversationListResponse;
      setConversations(payload);

      setSelectedConversationId((current) => {
        if (payload.items.length === 0) {
          return null;
        }
        if (current !== null && payload.items.some((item) => item.id === current)) {
          return current;
        }
        return payload.items[0].id;
      });
    } catch (error) {
      setConversationsError(extractErrorMessage(error, t("error_load_conversations", "Failed to load conversations")));
    } finally {
      setIsConversationsLoading(false);
    }
  }, [appliedConversationId, appliedListingId, appliedUserId, authFetch, conversationPage, hasSubmittedFilters, t]);

  useEffect(() => {
    void loadConversations();
  }, [loadConversations]);

  const loadMessages = useCallback(async () => {
    if (selectedConversationId === null) {
      setMessages(null);
      setMessagesError(null);
      return;
    }

    if (!isTranscriptModalOpen) {
      return;
    }

    setIsMessagesLoading(true);
    setMessagesError(null);

    try {
      const params = new URLSearchParams();
      params.set("conversation_id", String(selectedConversationId));
      params.set("page", String(messagesPage));
      params.set("page_size", "30");
      if (pendingMessageId !== null) {
        params.set("message_id", String(pendingMessageId));
      }

      const response = await authFetch(`/admin/messages?${params.toString()}`);
      if (!response.ok) {
        let message = t("error_load_messages", "Failed to load messages");
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = t("error_load_messages", "Failed to load messages");
        }
        throw new Error(message);
      }

      const payload = (await response.json()) as MessageListResponse;
      setMessages(payload);
      if (payload.page !== messagesPage) {
        setMessagesPage(payload.page);
      }

      if (pendingMessageId !== null) {
        setHighlightedMessageId(pendingMessageId);
        setPendingMessageId(null);
      }
    } catch (error) {
      setMessagesError(extractErrorMessage(error, t("error_load_messages", "Failed to load messages")));
    } finally {
      setIsMessagesLoading(false);
    }
  }, [authFetch, isTranscriptModalOpen, messagesPage, pendingMessageId, selectedConversationId, t]);

  useEffect(() => {
    void loadMessages();
  }, [loadMessages]);

  const setMessageNodeRef = useCallback((messageId: number, node: HTMLDivElement | null) => {
    messageNodeRefs.current[messageId] = node;
  }, []);

  useEffect(() => {
    if (!isTranscriptModalOpen || highlightedMessageId === null || isMessagesLoading) {
      return;
    }

    const node = messageNodeRefs.current[highlightedMessageId];
    if (!node) {
      return;
    }

    const timer = window.setTimeout(() => {
      node.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 60);

    return () => {
      window.clearTimeout(timer);
    };
  }, [highlightedMessageId, isMessagesLoading, isTranscriptModalOpen, messageRows]);

  const onApplyFilters = () => {
    const nextFilters: ConversationFilters = {
      user_id: draftFilters.user_id.trim(),
      listing_id: draftFilters.listing_id.trim(),
      conversation_id: draftFilters.conversation_id.trim(),
    };

    const parsedConversationId = parsePositiveInt(nextFilters.conversation_id);

    setHasSubmittedFilters(true);
    setConversationPage(1);
    setMessagesPage(1);
    setSelectedConversationId(parsedConversationId);
    setIsTranscriptModalOpen(false);
    setOpenTranscriptWhenConversationReady(parsedConversationId !== null);
    setAppliedFilters(nextFilters);
    setPendingMessageId(null);
    setHighlightedMessageId(null);
    setSearchParams(buildMessagesSearchParams(nextFilters, 1, 1, parsedConversationId, null), { replace: true });
  };

  const onResetFilters = () => {
    setDraftFilters(initialFilters);
    setAppliedFilters(initialFilters);
    setHasSubmittedFilters(false);
    setConversationPage(1);
    setMessagesPage(1);
    setSelectedConversationId(null);
    setConversations(null);
    setMessages(null);
    setConversationsError(null);
    setMessagesError(null);
    setIsTranscriptModalOpen(false);
    setOpenTranscriptWhenConversationReady(false);
    setPendingMessageId(null);
    setHighlightedMessageId(null);
    setSearchParams(new URLSearchParams(), { replace: true });
  };

  const closeTranscriptModal = () => {
    setIsTranscriptModalOpen(false);
  };

  const openTranscriptForConversation = (conversationId: number) => {
    setSelectedConversationId(conversationId);
    setMessagesPage(1);
    setMessages(null);
    setMessagesError(null);
    setPendingMessageId(null);
    setHighlightedMessageId(null);
    setIsTranscriptModalOpen(true);
    setOpenTranscriptWhenConversationReady(false);
    setSearchParams(
      buildMessagesSearchParams(appliedFilters, conversationPage, 1, conversationId, null),
      { replace: true },
    );
  };

  const downloadAttachment = async (attachment: MessageAttachmentItem) => {
    setDownloadingAttachmentId(attachment.id);

    try {
      const response = await authFetch(`/admin/messages/attachments/${attachment.id}/download`);
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
    } catch (error) {
      setMessagesError(extractErrorMessage(error, t("error_download_attachment", "Failed to download attachment")));
    } finally {
      setDownloadingAttachmentId(null);
    }
  };

  const openImageAttachmentPreview = async (attachment: MessageAttachmentItem) => {
    if (!isImageAttachment(attachment)) {
      void downloadAttachment(attachment);
      return;
    }

    setOpeningImagePreviewId(attachment.id);

    try {
      const response = await authFetch(`/admin/messages/attachments/${attachment.id}/download`);
      if (!response.ok) {
        let message = t("error_load_preview", "Failed to load preview");
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = t("error_load_preview", "Failed to load preview");
        }
        throw new Error(message);
      }

      const blob = await response.blob();
      const objectUrl = window.URL.createObjectURL(blob);
      setMessageImagePreviewUrl((previousUrl) => {
        if (previousUrl) {
          window.URL.revokeObjectURL(previousUrl);
        }
        return objectUrl;
      });
      setMessageImagePreviewAttachment(attachment);
    } catch (error) {
      setMessagesError(extractErrorMessage(error, t("error_load_preview", "Failed to load preview")));
    } finally {
      setOpeningImagePreviewId(null);
    }
  };

  const closeImageAttachmentPreview = () => {
    setMessageImagePreviewAttachment(null);
    setMessageImagePreviewUrl((previousUrl) => {
      if (previousUrl) {
        window.URL.revokeObjectURL(previousUrl);
      }
      return null;
    });
  };

  const loadInlineAttachmentPreview = useCallback(async (attachment: MessageAttachmentItem) => {
    if (!isImageAttachment(attachment)) {
      return;
    }

    if (inlineImageUrls[attachment.id] || inlineImageLoadingIds.includes(attachment.id)) {
      return;
    }

    setInlineImageLoadingIds((previous) => (previous.includes(attachment.id) ? previous : [...previous, attachment.id]));

    try {
      const response = await authFetch(`/admin/messages/attachments/${attachment.id}/download`);
      if (!response.ok) {
        throw new Error("Failed to load image preview");
      }

      const blob = await response.blob();
      const objectUrl = window.URL.createObjectURL(blob);

      setInlineImageUrls((previous) => {
        const previousUrl = previous[attachment.id];
        if (previousUrl) {
          window.URL.revokeObjectURL(previousUrl);
        }
        return { ...previous, [attachment.id]: objectUrl };
      });
      setInlineImageFailedIds((previous) => previous.filter((id) => id !== attachment.id));
    } catch {
      setInlineImageFailedIds((previous) => (previous.includes(attachment.id) ? previous : [...previous, attachment.id]));
    } finally {
      setInlineImageLoadingIds((previous) => previous.filter((id) => id !== attachment.id));
    }
  }, [authFetch, inlineImageLoadingIds, inlineImageUrls]);

  useEffect(() => {
    if (!isTranscriptModalOpen) {
      return;
    }

    for (const message of messageRows) {
      for (const attachment of message.attachments) {
        if (isImageAttachment(attachment)) {
          void loadInlineAttachmentPreview(attachment);
        }
      }
    }
  }, [isTranscriptModalOpen, loadInlineAttachmentPreview, messageRows]);

  useEffect(() => {
    const activeImageIds = new Set<number>();
    for (const message of messageRows) {
      for (const attachment of message.attachments) {
        if (isImageAttachment(attachment)) {
          activeImageIds.add(attachment.id);
        }
      }
    }

    setInlineImageUrls((previous) => {
      let changed = false;
      const next: Record<number, string> = {};

      for (const [rawId, url] of Object.entries(previous)) {
        const id = Number(rawId);
        if (activeImageIds.has(id)) {
          next[id] = url;
          continue;
        }

        window.URL.revokeObjectURL(url);
        changed = true;
      }

      return changed ? next : previous;
    });

    setInlineImageLoadingIds((previous) => previous.filter((id) => activeImageIds.has(id)));
    setInlineImageFailedIds((previous) => previous.filter((id) => activeImageIds.has(id)));
  }, [messageRows]);

  useEffect(() => {
    return () => {
      for (const url of Object.values(inlineImageUrlsRef.current)) {
        window.URL.revokeObjectURL(url);
      }
    };
  }, []);

  useEffect(() => {
    return () => {
      if (messageImagePreviewUrl) {
        window.URL.revokeObjectURL(messageImagePreviewUrl);
      }
    };
  }, [messageImagePreviewUrl]);

  const conversationTotalPages = conversations?.total_pages ?? 0;
  const canConversationPrev = conversationPage > 1;
  const canConversationNext = conversationTotalPages > 0 && conversationPage < conversationTotalPages;

  const messageTotalPages = messages?.total_pages ?? 0;
  const canMessagePrev = messagesPage > 1;
  const canMessageNext = messageTotalPages > 0 && messagesPage < messageTotalPages;

  const conversationSummary = useMemo(() => {
    if (!hasSubmittedFilters) {
      return t("set_filters_prompt", "Set filters and click Apply filters");
    }

    if (!conversations) {
      return "-";
    }

    if (conversations.total_items === 0) {
      return t("no_conversations_found", "No conversations found");
    }

    const from = (conversations.page - 1) * conversations.page_size + 1;
    const to = Math.min(conversations.page * conversations.page_size, conversations.total_items);
    return `${formatInteger(from, language)}-${formatInteger(to, language)} ${t("of", "of")} ${formatInteger(conversations.total_items, language)}`;
  }, [conversations, hasSubmittedFilters, language, t]);

  const messageSummary = useMemo(() => {
    if (!selectedConversation) {
      return t("select_conversation", "Select a conversation to inspect messages");
    }

    if (!messages) {
      return "-";
    }

    if (messages.total_items === 0) {
      return t("no_messages_found", "No messages found");
    }

    const from = (messages.page - 1) * messages.page_size + 1;
    const to = Math.min(messages.page * messages.page_size, messages.total_items);
    return `${formatInteger(from, language)}-${formatInteger(to, language)} ${t("of", "of")} ${formatInteger(messages.total_items, language)}`;
  }, [language, messages, selectedConversation, t]);

  return (
    <section className="module-page">
      <header className="module-header">
        <div>
          <h1>{t("title", "Messaging oversight")}</h1>
          <p>{t("subtitle", "Inspect conversations for abuse review with auditable access.")}</p>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => {
            void loadConversations();
            void loadMessages();
          }}
          disabled={isConversationsLoading || isMessagesLoading}
        >
          {isConversationsLoading || isMessagesLoading ? t("refreshing", "Refreshing...") : t("refresh", "Refresh")}
        </button>
      </header>

      {conversationsError ? <div className="dashboard-error">{conversationsError}</div> : null}

      <section className="search-strip messages-search-strip" aria-label={t("filters", "Filters") }>
        <input
          placeholder={t("user_id", "User ID")}
          value={draftFilters.user_id}
          onChange={(event) => setDraftFilters((prev) => ({ ...prev, user_id: event.target.value }))}
          inputMode="numeric"
        />
        <input
          placeholder={t("listing_id", "Listing ID (optional)")}
          value={draftFilters.listing_id}
          onChange={(event) => setDraftFilters((prev) => ({ ...prev, listing_id: event.target.value }))}
          inputMode="numeric"
        />
        <input
          placeholder={t("conversation_id", "Conversation ID (optional)")}
          value={draftFilters.conversation_id}
          onChange={(event) => setDraftFilters((prev) => ({ ...prev, conversation_id: event.target.value }))}
          inputMode="numeric"
        />
        <button type="button" className="btn btn-ghost" onClick={onResetFilters}>
          {t("reset", "Reset")}
        </button>
        <button type="button" className="btn btn-primary" onClick={onApplyFilters}>
          {t("apply_filters", "Apply filters")}
        </button>
      </section>

      <section className="table-card" aria-label={t("conversations_table", "Conversations table") }>
        <div className="table-head users-table-head">
          <strong>{t("conversations", "Conversations")}</strong>
          <span>{conversationSummary}</span>
        </div>

        <div className="messages-table-wrap">
          <table className="messages-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>{t("listing", "Listing")}</th>
                <th>{t("participants", "Participants")}</th>
                <th>{t("last_message", "Last message")}</th>
                <th>{t("last_activity", "Last activity")}</th>
                <th>{t("created", "Created")}</th>
                <th>{t("actions", "Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {conversationRows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="users-empty-cell">
                    {isConversationsLoading
                      ? t("loading_conversations", "Loading conversations...")
                      : t("no_conversations_found", "No conversations found")}
                  </td>
                </tr>
              ) : (
                conversationRows.map((conversation) => (
                  <tr key={conversation.id}>
                    <td>#{formatInteger(conversation.id, language)}</td>
                    <td>{formatInteger(conversation.listing_id, language)}</td>
                    <td>
                      <div className="users-name-cell">
                        <strong>A: {formatInteger(conversation.participant_a_id, language)}</strong>
                        <span>B: {formatInteger(conversation.participant_b_id, language)}</span>
                      </div>
                    </td>
                    <td>{conversation.last_message_preview ?? "-"}</td>
                    <td>{formatDateTime(conversation.last_message_at, language)}</td>
                    <td>{formatDateTime(conversation.created_at, language)}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-ghost"
                        onClick={() => openTranscriptForConversation(conversation.id)}
                      >
                        {selectedConversationId === conversation.id && isTranscriptModalOpen
                          ? t("transcript_opened", "Transcript opened")
                          : t("open_transcript", "Open transcript")}
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
            disabled={!canConversationPrev}
            onClick={() => {
              const nextPage = Math.max(1, conversationPage - 1);
              setConversationPage(nextPage);
              setSearchParams(
                buildMessagesSearchParams(
                  appliedFilters,
                  nextPage,
                  messagesPage,
                  isTranscriptModalOpen ? selectedConversationId : appliedConversationId,
                  null,
                ),
                { replace: true },
              );
            }}
          >
            {t("previous", "Previous")}
          </button>
          <span className="users-page-indicator">
            {t("page", "Page")} {formatInteger(conversations?.page ?? conversationPage, language)}{conversationTotalPages ? ` / ${formatInteger(conversationTotalPages, language)}` : ""}
          </span>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={!canConversationNext}
            onClick={() => {
              const nextPage = conversationPage + 1;
              setConversationPage(nextPage);
              setSearchParams(
                buildMessagesSearchParams(
                  appliedFilters,
                  nextPage,
                  messagesPage,
                  isTranscriptModalOpen ? selectedConversationId : appliedConversationId,
                  null,
                ),
                { replace: true },
              );
            }}
          >
            {t("next", "Next")}
          </button>
        </div>
      </section>

      <Modal
        open={isTranscriptModalOpen}
        onClose={closeTranscriptModal}
        title={t("transcript_title", "Conversation transcript")}
        subtitle={selectedConversation
          ? `${t("conversation", "Conversation")} #${formatInteger(selectedConversation.id, language)} - ${messageSummary}`
          : t("select_conversation", "Select a conversation to inspect messages")}
      >
        <div className="users-detail-body messages-transcript-modal-body">
          {messagesError ? <div className="dashboard-error">{messagesError}</div> : null}

          {selectedConversation ? (
            <div className="messages-transcript-meta">
              <p>
                {t("listing", "Listing")}: <strong>#{formatInteger(selectedConversation.listing_id, language)}</strong>
              </p>
              <p>
                {t("participants", "Participants")}: <strong>A #{formatInteger(selectedConversation.participant_a_id, language)}</strong>, <strong>B #{formatInteger(selectedConversation.participant_b_id, language)}</strong>
              </p>
              <p>
                {t("last_activity", "Last activity")}: <strong>{formatDateTime(selectedConversation.last_message_at, language)}</strong>
              </p>
            </div>
          ) : null}

          <div className="messages-transcript-feed" aria-live="polite">
            {selectedConversation === null ? (
              <p className="messages-transcript-empty">{t("select_conversation", "Select a conversation to inspect messages")}</p>
            ) : isMessagesLoading ? (
              <p className="messages-transcript-empty">{t("loading_messages", "Loading messages...")}</p>
            ) : messageRows.length === 0 ? (
              <p className="messages-transcript-empty">{t("no_messages_found", "No messages found")}</p>
            ) : (
              messageRows.map((message) => {
                const senderRole = selectedConversation && message.sender_id === selectedConversation.participant_a_id
                  ? "participant-a"
                  : selectedConversation && message.sender_id === selectedConversation.participant_b_id
                    ? "participant-b"
                    : "other";

                return (
                  <article
                    key={message.id}
                    className={`messages-bubble-row messages-bubble-row-${senderRole}${highlightedMessageId === message.id ? " messages-bubble-row-highlight" : ""}`}
                  >
                    <div
                      className="messages-bubble-card"
                      ref={(node) => setMessageNodeRef(message.id, node)}
                    >
                      <header className="messages-bubble-head">
                        <strong>
                          {t("sender", "Sender")} #{formatInteger(message.sender_id, language)}
                        </strong>
                        <span>{formatDateTime(message.sent_at, language)}</span>
                      </header>

                      <p className="messages-bubble-text">{message.text_body?.trim() || t("no_message_text", "Message has no text")}</p>

                      {message.attachments.length > 0 ? (
                        <div className="messages-attachments-list">
                          {message.attachments.map((attachment) => {
                            const isImage = isImageAttachment(attachment);
                            const inlineUrl = inlineImageUrls[attachment.id];
                            const isInlineLoading = inlineImageLoadingIds.includes(attachment.id);
                            const isInlineFailed = inlineImageFailedIds.includes(attachment.id);

                            if (!isImage) {
                              return (
                                <button
                                  key={attachment.id}
                                  type="button"
                                  className="btn btn-ghost messages-attachment-btn"
                                  disabled={downloadingAttachmentId === attachment.id}
                                  onClick={() => {
                                    void downloadAttachment(attachment);
                                  }}
                                >
                                  {downloadingAttachmentId === attachment.id
                                    ? t("downloading", "Downloading...")
                                    : `${attachment.original_name} (${formatFileSize(attachment.file_size, language)})`}
                                </button>
                              );
                            }

                            return (
                              <div key={attachment.id} className="messages-inline-image-card">
                                {inlineUrl ? (
                                  <button
                                    type="button"
                                    className="messages-inline-image-btn"
                                    disabled={openingImagePreviewId === attachment.id}
                                    onClick={() => {
                                      void openImageAttachmentPreview(attachment);
                                    }}
                                  >
                                    <img src={inlineUrl} alt={attachment.original_name} loading="lazy" />
                                  </button>
                                ) : isInlineLoading ? (
                                  <div className="messages-inline-image-loading">{t("loading_preview", "Loading preview...")}</div>
                                ) : isInlineFailed ? (
                                  <button
                                    type="button"
                                    className="btn btn-ghost"
                                    onClick={() => {
                                      void loadInlineAttachmentPreview(attachment);
                                    }}
                                  >
                                    {t("retry_preview", "Retry preview")}
                                  </button>
                                ) : (
                                  <button
                                    type="button"
                                    className="btn btn-ghost"
                                    onClick={() => {
                                      void loadInlineAttachmentPreview(attachment);
                                    }}
                                  >
                                    {t("load_preview", "Load preview")}
                                  </button>
                                )}

                                <div className="messages-inline-image-meta">
                                  <span>{attachment.original_name}</span>
                                  <span>{formatFileSize(attachment.file_size, language)}</span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      ) : null}
                    </div>
                  </article>
                );
              })
            )}
          </div>

          <div className="table-footer messages-transcript-footer">
            <button
              type="button"
              className="btn btn-ghost"
              disabled={!canMessagePrev || selectedConversation === null}
              onClick={() => {
                const nextPage = Math.max(1, messagesPage - 1);
                setMessagesPage(nextPage);
                setSearchParams(
                  buildMessagesSearchParams(appliedFilters, conversationPage, nextPage, selectedConversationId, null),
                  { replace: true },
                );
              }}
            >
              {t("previous", "Previous")}
            </button>
            <span className="users-page-indicator">
              {t("page", "Page")} {formatInteger(messages?.page ?? messagesPage, language)}{messageTotalPages ? ` / ${formatInteger(messageTotalPages, language)}` : ""}
            </span>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={!canMessageNext || selectedConversation === null}
              onClick={() => {
                const nextPage = messagesPage + 1;
                setMessagesPage(nextPage);
                setSearchParams(
                  buildMessagesSearchParams(appliedFilters, conversationPage, nextPage, selectedConversationId, null),
                  { replace: true },
                );
              }}
            >
              {t("next", "Next")}
            </button>
          </div>
        </div>
      </Modal>

      <ImagePreviewOverlay
        open={messageImagePreviewAttachment !== null && messageImagePreviewUrl !== null}
        imageSrc={messageImagePreviewUrl}
        imageAlt={messageImagePreviewAttachment?.original_name ?? t("image_preview", "Image preview")}
        onClose={closeImageAttachmentPreview}
        onDownload={() => {
          if (!messageImagePreviewAttachment) {
            return;
          }
          void downloadAttachment(messageImagePreviewAttachment);
        }}
        downloadLabel={t("download", "Download")}
        downloadingLabel={t("downloading", "Downloading...")}
        closeLabel={t("close", "Close")}
        isDownloading={
          messageImagePreviewAttachment !== null &&
          downloadingAttachmentId === messageImagePreviewAttachment.id
        }
      />
    </section>
  );
}