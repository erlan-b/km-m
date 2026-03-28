import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "../../app/auth/AuthContext";
import { usePageI18n } from "../../app/i18n/I18nContext";
import { formatDateTime, formatInteger } from "../../shared/i18n/format";
import { Modal } from "../common/Modal";

type ListingStatus = "draft" | "pending_review" | "published" | "rejected" | "archived" | "inactive" | "sold";
type TransactionType = "sale" | "rent_long" | "rent_daily";

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
  map_address_label: string | null;
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

type ListingStatusUpdateResponse = {
  listing_id: number;
  status: ListingStatus;
  note: string | null;
};

const ACTIONS_BY_STATUS: Record<ListingStatus, string[]> = {
  draft: ["approve", "reject", "archive"],
  pending_review: ["approve", "reject", "archive"],
  rejected: ["approve", "archive"],
  published: ["deactivate", "archive"],
  inactive: ["approve", "archive"],
  sold: ["archive"],
  archived: [],
};

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed";
}

function formatPrice(value: string | number, currency: string, language: "en" | "ru"): string {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return `${value} ${currency}`;
  }
  return `${formatInteger(numeric, language)} ${currency}`;
}

function statusLabel(status: ListingStatus, t: (key: string, fallback: string) => string): string {
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

function moderationActionLabel(action: string, t: (key: string, fallback: string) => string): string {
  if (action === "approve") {
    return t("action_approve", "Approve");
  }
  if (action === "reject") {
    return t("action_reject", "Reject");
  }
  if (action === "archive") {
    return t("action_archive", "Archive");
  }
  if (action === "deactivate") {
    return t("action_deactivate", "Deactivate");
  }
  return action;
}

function statusBadgeClass(status: ListingStatus): string {
  if (status === "published") {
    return "users-status-active";
  }
  if (status === "rejected" || status === "archived") {
    return "users-status-deactivated";
  }
  if (status === "inactive") {
    return "users-status-blocked";
  }
  if (status === "sold") {
    return "users-status-deactivated";
  }
  return "users-status-pending_verification";
}

export function ListingsModerationPage() {
  const { authFetch, canModerateContent } = useAuth();
  const { t, language } = usePageI18n("listings");
  const [searchParams] = useSearchParams();

  const initialListingIdFilter = useMemo(() => {
    const raw = searchParams.get("listing_id");
    if (!raw) {
      return "";
    }
    const parsed = Number(raw);
    if (!Number.isInteger(parsed) || parsed <= 0) {
      return "";
    }
    return String(parsed);
  }, [searchParams]);

  const [listings, setListings] = useState<ListingListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [queryInput, setQueryInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [listingIdFilter, setListingIdFilter] = useState(initialListingIdFilter);
  const [statusFilter, setStatusFilter] = useState<ListingStatus | "">(initialListingIdFilter ? "" : "pending_review");
  const [transactionTypeFilter, setTransactionTypeFilter] = useState<TransactionType | "">("");
  const [cityFilter, setCityFilter] = useState("");
  const [sortBy, setSortBy] = useState<"newest" | "oldest" | "price_asc" | "price_desc">("newest");
  const [page, setPage] = useState(1);

  const [selectedListingId, setSelectedListingId] = useState<number | null>(null);
  const [isReviewModalOpen, setIsReviewModalOpen] = useState(false);
  const [action, setAction] = useState("");
  const [note, setNote] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadListings = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", "20");
      params.set("sort_by", sortBy);

      if (searchTerm.trim()) {
        params.set("q", searchTerm.trim());
      }
      if (listingIdFilter.trim()) {
        params.set("listing_id", listingIdFilter.trim());
      }
      if (statusFilter) {
        params.set("status_filter", statusFilter);
      }
      if (transactionTypeFilter) {
        params.set("transaction_type", transactionTypeFilter);
      }
      if (cityFilter.trim()) {
        params.set("city", cityFilter.trim());
      }

      const response = await authFetch(`/listings/admin/moderation?${params.toString()}`);
      if (!response.ok) {
        throw new Error(t("error_load_queue", "Failed to load listings moderation queue"));
      }

      const payload = (await response.json()) as ListingListResponse;
      setListings(payload);

      if (payload.items.length > 0) {
        const selectedVisible = selectedListingId !== null && payload.items.some((item) => item.id === selectedListingId);
        if (!selectedVisible) {
          setSelectedListingId(payload.items[0].id);
        }
      } else {
        setSelectedListingId(null);
      }
    } catch (loadError) {
      setError(extractErrorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, [authFetch, cityFilter, listingIdFilter, page, searchTerm, selectedListingId, sortBy, statusFilter, t, transactionTypeFilter]);

  useEffect(() => {
    void loadListings();
  }, [loadListings]);

  const selectedListing = useMemo(() => {
    if (!listings || selectedListingId === null) {
      return null;
    }
    return listings.items.find((item) => item.id === selectedListingId) ?? null;
  }, [listings, selectedListingId]);

  const availableActions = useMemo(() => {
    if (!selectedListing) {
      return [] as string[];
    }
    return ACTIONS_BY_STATUS[selectedListing.status] ?? [];
  }, [selectedListing]);

  useEffect(() => {
    if (availableActions.length === 0) {
      setAction("");
    } else {
      setAction(availableActions[0]);
    }
    setNote("");
  }, [selectedListing?.id, availableActions]);

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
    void loadListings();
  };

  const onModerateSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!canModerateContent) {
      setError(t("access_denied_moderation", "Access denied: moderator, admin or superadmin role required"));
      return;
    }

    if (!selectedListing || !action) {
      return;
    }

    const confirmed = window.confirm(`${t("confirm_apply_action", "Apply action")} '${moderationActionLabel(action, t)}' ${t("to_listing", "to listing")} #${selectedListing.id}?`);
    if (!confirmed) {
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await authFetch(`/listings/${selectedListing.id}/moderation`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          note: note.trim() ? note.trim() : null,
        }),
      });

      if (!response.ok) {
        let message = t("error_apply_action", "Failed to apply moderation action");
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = t("error_apply_action", "Failed to apply moderation action");
        }
        throw new Error(message);
      }

      const payload = (await response.json()) as ListingStatusUpdateResponse;

      setListings((prev) => {
        if (!prev) {
          return prev;
        }
        return {
          ...prev,
          items: prev.items.map((item) =>
            item.id === payload.listing_id
              ? {
                  ...item,
                  status: payload.status,
                }
              : item,
          ),
        };
      });
    } catch (submitError) {
      setError(extractErrorMessage(submitError));
    } finally {
      setIsSubmitting(false);
    }
  };

  const rows = listings?.items ?? [];
  const totalPages = listings?.total_pages ?? 0;
  const canPrev = page > 1;
  const canNext = totalPages > 0 && page < totalPages;

  const summaryText = useMemo(() => {
    if (!listings) {
      return "-";
    }
    if (listings.total_items === 0) {
      return t("no_listings_found", "No listings found");
    }

    const from = (listings.page - 1) * listings.page_size + 1;
    const to = Math.min(listings.page * listings.page_size, listings.total_items);
    return `${formatInteger(from, language)}-${formatInteger(to, language)} ${t("of", "of")} ${formatInteger(listings.total_items, language)}`;
  }, [language, listings, t]);

  return (
    <section className="module-page">
      <header className="module-header">
        <div>
          <h1>{t("title", "Listings Moderation")}</h1>
          <p>{t("subtitle", "Review queue, apply status transitions, and keep moderation notes.")}</p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={() => void loadListings()} disabled={isLoading}>
          {isLoading ? t("refreshing", "Refreshing...") : t("refresh", "Refresh")}
        </button>
      </header>

      {error ? <div className="dashboard-error">{error}</div> : null}

      <form className="search-strip listings-search-strip" onSubmit={onSearchSubmit}>
        <input
          placeholder={t("search_placeholder", "Search by title or description")}
          aria-label={t("search_listings", "Search listings")}
          value={queryInput}
          onChange={(event) => setQueryInput(event.target.value)}
        />
        <input
          placeholder={t("listing_id", "Listing ID")}
          aria-label={t("listing_id", "Listing ID")}
          value={listingIdFilter}
          inputMode="numeric"
          pattern="[0-9]*"
          onChange={(event) => setListingIdFilter(event.target.value.replace(/[^0-9]/g, ""))}
        />
        <select
          className="users-filter-select"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as ListingStatus | "")}
        >
          <option value="">{t("all_statuses", "All statuses")}</option>
          <option value="draft">{t("status_draft", "Draft")}</option>
          <option value="pending_review">{t("status_pending_review", "Pending review")}</option>
          <option value="published">{t("status_published", "Published")}</option>
          <option value="rejected">{t("status_rejected", "Rejected")}</option>
          <option value="inactive">{t("status_inactive", "Inactive")}</option>
          <option value="sold">{t("status_sold", "Sold")}</option>
          <option value="archived">{t("status_archived", "Archived")}</option>
        </select>
        <select
          className="users-filter-select"
          value={transactionTypeFilter}
          onChange={(event) => setTransactionTypeFilter(event.target.value as TransactionType | "")}
        >
          <option value="">{t("all_transaction_types", "All transaction types")}</option>
          <option value="sale">{t("transaction_sale", "Sale")}</option>
          <option value="rent_long">{t("transaction_rent_long", "Long rent")}</option>
          <option value="rent_daily">{t("transaction_rent_daily", "Daily rent")}</option>
        </select>
        <input
          placeholder={t("city", "City")}
          aria-label={t("filter_by_city", "Filter by city")}
          value={cityFilter}
          onChange={(event) => setCityFilter(event.target.value)}
        />
        <select
          className="users-filter-select"
          value={sortBy}
          onChange={(event) => setSortBy(event.target.value as "newest" | "oldest" | "price_asc" | "price_desc")}
        >
          <option value="newest">{t("sort_newest", "Newest")}</option>
          <option value="oldest">{t("sort_oldest", "Oldest")}</option>
          <option value="price_asc">{t("sort_price_asc", "Price asc")}</option>
          <option value="price_desc">{t("sort_price_desc", "Price desc")}</option>
        </select>
        <button type="button" className="btn btn-ghost" onClick={onApplyFilters}>
          {t("apply_filters", "Apply filters")}
        </button>
        <button type="submit" className="btn btn-primary">{t("search", "Search")}</button>
      </form>

      <section className="table-card" aria-label={t("table_listings_queue", "Listings moderation queue")}>
        <div className="table-head users-table-head">
          <strong>{t("queue", "Queue")}</strong>
          <span>{summaryText}</span>
        </div>

        <div className="listings-table-wrap">
          <table className="listings-table">
            <thead>
              <tr>
                <th>{t("listing", "Listing")}</th>
                <th>{t("owner", "Owner")}</th>
                <th>{t("category", "Category")}</th>
                <th>{t("transaction", "Transaction")}</th>
                <th>{t("price", "Price")}</th>
                <th>{t("status", "Status")}</th>
                <th>{t("created", "Created")}</th>
                <th>{t("actions", "Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="users-empty-cell">
                    {isLoading ? t("loading_queue", "Loading moderation queue...") : t("no_listings_found", "No listings found")}
                  </td>
                </tr>
              ) : (
                rows.map((listing) => (
                  <tr key={listing.id}>
                    <td>
                      <div className="users-name-cell">
                        <strong>{listing.title}</strong>
                        <span>#{listing.id} • {listing.city}</span>
                      </div>
                    </td>
                    <td>#{listing.owner_id}</td>
                    <td>#{listing.category_id}</td>
                    <td>{transactionLabel(listing.transaction_type, t)}</td>
                    <td>{formatPrice(listing.price, listing.currency, language)}</td>
                    <td>
                      <span className={`users-status-badge ${statusBadgeClass(listing.status)}`}>
                        {statusLabel(listing.status, t)}
                      </span>
                    </td>
                    <td>{formatDateTime(listing.created_at, language)}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-ghost"
                        onClick={() => {
                          const defaults = ACTIONS_BY_STATUS[listing.status] ?? [];
                          setAction(defaults.length > 0 ? defaults[0] : "");
                          setNote("");
                          setSelectedListingId(listing.id);
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
            {t("page", "Page")} {formatInteger(listings?.page ?? page, language)}{totalPages ? ` / ${formatInteger(totalPages, language)}` : ""}
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
        subtitle={selectedListing ? `${t("listing", "Listing")} #${selectedListing.id}` : t("no_listing_selected", "No listing selected")}
      >
        <div className="users-detail-body">
          {!selectedListing ? <p>{t("select_listing_row", "Select a listing row and click Review.")}</p> : null}

          {selectedListing ? (
            <div className="listings-detail-stack">
              <div className="dashboard-stats-grid">
                <article className="dashboard-stat-group">
                  <h3>{t("summary", "Summary")}</h3>
                  <p>{t("title_label", "Title")}: <strong>{selectedListing.title}</strong></p>
                  <p>{t("status", "Status")}: <strong>{statusLabel(selectedListing.status, t)}</strong></p>
                  <p>{t("transaction", "Transaction")}: <strong>{transactionLabel(selectedListing.transaction_type, t)}</strong></p>
                  <p>{t("price", "Price")}: <strong>{formatPrice(selectedListing.price, selectedListing.currency, language)}</strong></p>
                </article>
                <article className="dashboard-stat-group">
                  <h3>{t("metadata", "Metadata")}</h3>
                  <p>{t("owner", "Owner")}: <strong>#{selectedListing.owner_id}</strong></p>
                  <p>{t("category", "Category")}: <strong>#{selectedListing.category_id}</strong></p>
                  <p>{t("views", "Views")}: <strong>{formatInteger(selectedListing.view_count, language)}</strong></p>
                  <p>{t("favorites", "Favorites")}: <strong>{formatInteger(selectedListing.favorite_count, language)}</strong></p>
                </article>
              </div>

              <article className="dashboard-stat-group listings-description-block">
                <h3>{t("description", "Description")}</h3>
                <p>{selectedListing.description}</p>
                <p>
                  {t("location", "Location")}: <strong>{selectedListing.city}</strong>
                  {selectedListing.address_line ? `, ${selectedListing.address_line}` : ""}
                </p>
              </article>

              <form className="reports-form" onSubmit={onModerateSubmit}>
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
                      value={action}
                      onChange={(event) => setAction(event.target.value)}
                      disabled={!canModerateContent || availableActions.length === 0}
                    >
                      {availableActions.length === 0 ? <option value="">{t("no_available_actions", "No available actions")}</option> : null}
                      {availableActions.map((option) => (
                        <option key={option} value={option}>
                          {moderationActionLabel(option, t)}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    {t("current_state", "Current state")}
                    <input
                      value={`${statusLabel(selectedListing.status, t)} (${selectedListing.status})`}
                      readOnly
                    />
                  </label>
                </div>

                <label className="reports-note-label">
                  {t("moderation_note_optional", "Moderation note (optional)")}
                  <textarea
                    className="reports-note-input"
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    placeholder={t("note_placeholder", "Add context for audit trail")}
                    maxLength={1000}
                    disabled={!canModerateContent}
                  />
                </label>

                <div className="users-actions-cell">
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={!canModerateContent || isSubmitting || availableActions.length === 0 || action.length === 0}
                  >
                    {isSubmitting ? t("applying", "Applying...") : t("apply_action", "Apply action")}
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={!canModerateContent}
                    onClick={() => {
                      if (availableActions.length > 0) {
                        setAction(availableActions[0]);
                      }
                      setNote("");
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
