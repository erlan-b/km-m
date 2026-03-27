import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { useAuth } from "../../app/auth/AuthContext";

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
  is_premium: boolean;
  premium_expires_at: string | null;
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

type ModerationActionOption = {
  value: string;
  label: string;
};

const ACTIONS_BY_STATUS: Record<ListingStatus, ModerationActionOption[]> = {
  draft: [
    { value: "approve", label: "Approve" },
    { value: "reject", label: "Reject" },
    { value: "archive", label: "Archive" },
  ],
  pending_review: [
    { value: "approve", label: "Approve" },
    { value: "reject", label: "Reject" },
    { value: "archive", label: "Archive" },
  ],
  rejected: [
    { value: "approve", label: "Approve" },
    { value: "archive", label: "Archive" },
  ],
  published: [
    { value: "deactivate", label: "Deactivate" },
    { value: "archive", label: "Archive" },
  ],
  inactive: [
    { value: "approve", label: "Approve" },
    { value: "archive", label: "Archive" },
  ],
  sold: [{ value: "archive", label: "Archive" }],
  archived: [],
};

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed";
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function formatPrice(value: string | number, currency: string): string {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return `${value} ${currency}`;
  }
  return `${numeric.toLocaleString()} ${currency}`;
}

function statusLabel(status: ListingStatus): string {
  if (status === "pending_review") {
    return "Pending review";
  }
  if (status === "published") {
    return "Published";
  }
  if (status === "rejected") {
    return "Rejected";
  }
  if (status === "inactive") {
    return "Inactive";
  }
  if (status === "sold") {
    return "Sold";
  }
  if (status === "archived") {
    return "Archived";
  }
  return "Draft";
}

function transactionLabel(value: TransactionType): string {
  if (value === "sale") {
    return "Sale";
  }
  if (value === "rent_long") {
    return "Long rent";
  }
  return "Daily rent";
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
  const { authFetch } = useAuth();

  const [listings, setListings] = useState<ListingListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [queryInput, setQueryInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<ListingStatus | "">("pending_review");
  const [transactionTypeFilter, setTransactionTypeFilter] = useState<TransactionType | "">("");
  const [cityFilter, setCityFilter] = useState("");
  const [sortBy, setSortBy] = useState<"newest" | "oldest" | "price_asc" | "price_desc">("newest");
  const [page, setPage] = useState(1);

  const [selectedListingId, setSelectedListingId] = useState<number | null>(null);
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
        throw new Error("Failed to load listings moderation queue");
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
  }, [authFetch, cityFilter, page, searchTerm, selectedListingId, sortBy, statusFilter, transactionTypeFilter]);

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
      return [] as ModerationActionOption[];
    }
    return ACTIONS_BY_STATUS[selectedListing.status] ?? [];
  }, [selectedListing]);

  useEffect(() => {
    if (availableActions.length === 0) {
      setAction("");
    } else {
      setAction(availableActions[0].value);
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

    if (!selectedListing || !action) {
      return;
    }

    const confirmed = window.confirm(`Apply action '${action}' to listing #${selectedListing.id}?`);
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
        let message = "Failed to apply moderation action";
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = "Failed to apply moderation action";
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
      return "No listings found";
    }

    const from = (listings.page - 1) * listings.page_size + 1;
    const to = Math.min(listings.page * listings.page_size, listings.total_items);
    return `${from}-${to} of ${listings.total_items}`;
  }, [listings]);

  return (
    <section className="module-page">
      <header className="module-header">
        <div>
          <h1>Listings Moderation</h1>
          <p>Review queue, apply status transitions, and keep moderation notes.</p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={() => void loadListings()} disabled={isLoading}>
          {isLoading ? "Refreshing..." : "Refresh"}
        </button>
      </header>

      {error ? <div className="dashboard-error">{error}</div> : null}

      <form className="search-strip listings-search-strip" onSubmit={onSearchSubmit}>
        <input
          placeholder="Search by title or description"
          aria-label="Search listings"
          value={queryInput}
          onChange={(event) => setQueryInput(event.target.value)}
        />
        <select
          className="users-filter-select"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as ListingStatus | "")}
        >
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="pending_review">Pending review</option>
          <option value="published">Published</option>
          <option value="rejected">Rejected</option>
          <option value="inactive">Inactive</option>
          <option value="sold">Sold</option>
          <option value="archived">Archived</option>
        </select>
        <select
          className="users-filter-select"
          value={transactionTypeFilter}
          onChange={(event) => setTransactionTypeFilter(event.target.value as TransactionType | "")}
        >
          <option value="">All transaction types</option>
          <option value="sale">Sale</option>
          <option value="rent_long">Long rent</option>
          <option value="rent_daily">Daily rent</option>
        </select>
        <input
          placeholder="City"
          aria-label="Filter by city"
          value={cityFilter}
          onChange={(event) => setCityFilter(event.target.value)}
        />
        <select
          className="users-filter-select"
          value={sortBy}
          onChange={(event) => setSortBy(event.target.value as "newest" | "oldest" | "price_asc" | "price_desc")}
        >
          <option value="newest">Newest</option>
          <option value="oldest">Oldest</option>
          <option value="price_asc">Price asc</option>
          <option value="price_desc">Price desc</option>
        </select>
        <button type="button" className="btn btn-ghost" onClick={onApplyFilters}>
          Apply filters
        </button>
        <button type="submit" className="btn btn-primary">Search</button>
      </form>

      <section className="table-card" aria-label="Listings moderation queue">
        <div className="table-head users-table-head">
          <strong>Queue</strong>
          <span>{summaryText}</span>
        </div>

        <div className="listings-table-wrap">
          <table className="listings-table">
            <thead>
              <tr>
                <th>Listing</th>
                <th>Owner</th>
                <th>Category</th>
                <th>Transaction</th>
                <th>Price</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="users-empty-cell">
                    {isLoading ? "Loading moderation queue..." : "No listings found"}
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
                    <td>{transactionLabel(listing.transaction_type)}</td>
                    <td>{formatPrice(listing.price, listing.currency)}</td>
                    <td>
                      <span className={`users-status-badge ${statusBadgeClass(listing.status)}`}>
                        {statusLabel(listing.status)}
                      </span>
                    </td>
                    <td>{formatDate(listing.created_at)}</td>
                    <td>
                      <button type="button" className="btn btn-ghost" onClick={() => setSelectedListingId(listing.id)}>
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
            Page {listings?.page ?? page}{totalPages ? ` / ${totalPages}` : ""}
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

      <section className="table-card" aria-label="Listing moderation panel">
        <div className="table-head">
          <strong>Moderation action</strong>
          <span>{selectedListing ? `Listing #${selectedListing.id}` : "No listing selected"}</span>
        </div>

        <div className="users-detail-body">
          {!selectedListing ? <p>Select a listing row and click Review.</p> : null}

          {selectedListing ? (
            <div className="listings-detail-stack">
              <div className="dashboard-stats-grid">
                <article className="dashboard-stat-group">
                  <h3>Summary</h3>
                  <p>Title: <strong>{selectedListing.title}</strong></p>
                  <p>Status: <strong>{statusLabel(selectedListing.status)}</strong></p>
                  <p>Transaction: <strong>{transactionLabel(selectedListing.transaction_type)}</strong></p>
                  <p>Price: <strong>{formatPrice(selectedListing.price, selectedListing.currency)}</strong></p>
                </article>
                <article className="dashboard-stat-group">
                  <h3>Metadata</h3>
                  <p>Owner: <strong>#{selectedListing.owner_id}</strong></p>
                  <p>Category: <strong>#{selectedListing.category_id}</strong></p>
                  <p>Views: <strong>{selectedListing.view_count}</strong></p>
                  <p>Favorites: <strong>{selectedListing.favorite_count}</strong></p>
                </article>
              </div>

              <article className="dashboard-stat-group listings-description-block">
                <h3>Description</h3>
                <p>{selectedListing.description}</p>
                <p>
                  Location: <strong>{selectedListing.city}</strong>
                  {selectedListing.address_line ? `, ${selectedListing.address_line}` : ""}
                </p>
              </article>

              <form className="reports-form" onSubmit={onModerateSubmit}>
                <div className="reports-form-grid">
                  <label>
                    Action
                    <select
                      className="users-filter-select"
                      value={action}
                      onChange={(event) => setAction(event.target.value)}
                      disabled={availableActions.length === 0}
                    >
                      {availableActions.length === 0 ? <option value="">No available actions</option> : null}
                      {availableActions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    Current state
                    <input
                      value={`${statusLabel(selectedListing.status)} (${selectedListing.status})`}
                      readOnly
                    />
                  </label>
                </div>

                <label className="reports-note-label">
                  Moderation note (optional)
                  <textarea
                    className="reports-note-input"
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    placeholder="Add context for audit trail"
                    maxLength={1000}
                  />
                </label>

                <div className="users-actions-cell">
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={isSubmitting || availableActions.length === 0 || action.length === 0}
                  >
                    {isSubmitting ? "Applying..." : "Apply action"}
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => {
                      if (availableActions.length > 0) {
                        setAction(availableActions[0].value);
                      }
                      setNote("");
                    }}
                  >
                    Reset form
                  </button>
                </div>
              </form>
            </div>
          ) : null}
        </div>
      </section>
    </section>
  );
}
