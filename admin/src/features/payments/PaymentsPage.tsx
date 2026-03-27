import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "../../app/auth/AuthContext";
import { Modal } from "../common/Modal";

type PaymentStatus = "pending" | "successful" | "failed" | "cancelled" | "refunded";

type PaymentHistoryItem = {
  id: number;
  user_id: number;
  listing_id: number | null;
  amount: string | number;
  currency: string;
  status: PaymentStatus;
  payment_provider: string;
  provider_reference: string | null;
  created_at: string;
  updated_at: string;
  paid_at: string | null;
};

type PaymentHistoryResponse = {
  items: PaymentHistoryItem[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
};

type PaymentFilters = {
  status_filter: PaymentStatus | "";
  user_id: string;
  listing_id: string;
  payment_provider: string;
  created_from: string;
  created_to: string;
  paid_from: string;
  paid_to: string;
};

const initialFilters: PaymentFilters = {
  status_filter: "",
  user_id: "",
  listing_id: "",
  payment_provider: "",
  created_from: "",
  created_to: "",
  paid_from: "",
  paid_to: "",
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

function statusLabel(status: PaymentStatus): string {
  if (status === "pending") {
    return "Pending";
  }
  if (status === "successful") {
    return "Successful";
  }
  if (status === "failed") {
    return "Failed";
  }
  if (status === "cancelled") {
    return "Cancelled";
  }
  return "Refunded";
}

function statusClass(status: PaymentStatus): string {
  if (status === "successful") {
    return "users-status-active";
  }
  if (status === "pending") {
    return "users-status-pending_verification";
  }
  if (status === "failed") {
    return "users-status-blocked";
  }
  return "users-status-deactivated";
}

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Failed to load payments";
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

function formatAmount(amount: string | number, currency: string): string {
  const numericValue = typeof amount === "string" ? Number(amount) : amount;
  if (!Number.isFinite(numericValue)) {
    return `${String(amount)} ${currency}`;
  }

  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(numericValue);
  } catch {
    return `${numericValue.toFixed(2)} ${currency}`;
  }
}

export function PaymentsPage() {
  const { authFetch } = useAuth();

  const [payments, setPayments] = useState<PaymentHistoryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [page, setPage] = useState(1);
  const [draftFilters, setDraftFilters] = useState<PaymentFilters>(initialFilters);
  const [appliedFilters, setAppliedFilters] = useState<PaymentFilters>(initialFilters);

  const [selectedPayment, setSelectedPayment] = useState<PaymentHistoryItem | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);

  const loadPayments = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", "20");

      if (appliedFilters.status_filter) {
        params.set("status_filter", appliedFilters.status_filter);
      }

      const userId = parsePositiveInt(appliedFilters.user_id);
      if (userId !== null) {
        params.set("user_id", String(userId));
      }

      const listingId = parsePositiveInt(appliedFilters.listing_id);
      if (listingId !== null) {
        params.set("listing_id", String(listingId));
      }

      const provider = appliedFilters.payment_provider.trim();
      if (provider.length >= 2) {
        params.set("payment_provider", provider);
      }

      if (appliedFilters.created_from) {
        params.set("created_from", appliedFilters.created_from);
      }
      if (appliedFilters.created_to) {
        params.set("created_to", appliedFilters.created_to);
      }
      if (appliedFilters.paid_from) {
        params.set("paid_from", appliedFilters.paid_from);
      }
      if (appliedFilters.paid_to) {
        params.set("paid_to", appliedFilters.paid_to);
      }

      const response = await authFetch(`/payments/admin?${params.toString()}`);
      if (!response.ok) {
        let message = "Failed to load payments";
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = "Failed to load payments";
        }
        throw new Error(message);
      }

      const payload = (await response.json()) as PaymentHistoryResponse;
      setPayments(payload);

      if (payload.items.length === 0) {
        setSelectedPayment(null);
        setIsDetailModalOpen(false);
      } else if (selectedPayment) {
        const refreshedSelected = payload.items.find((item) => item.id === selectedPayment.id) ?? null;
        setSelectedPayment(refreshedSelected);
      }
    } catch (loadError) {
      setError(extractErrorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, [appliedFilters, authFetch, page, selectedPayment]);

  useEffect(() => {
    void loadPayments();
  }, [loadPayments]);

  const onApplyFilters = () => {
    if (page !== 1) {
      setPage(1);
    }
    setAppliedFilters({
      ...draftFilters,
      payment_provider: draftFilters.payment_provider.trim(),
    });
  };

  const onResetFilters = () => {
    setDraftFilters(initialFilters);
    setAppliedFilters(initialFilters);
    if (page !== 1) {
      setPage(1);
    }
  };

  const rows = payments?.items ?? [];
  const totalPages = payments?.total_pages ?? 0;
  const canPrev = page > 1;
  const canNext = totalPages > 0 && page < totalPages;

  const summaryText = useMemo(() => {
    if (!payments) {
      return "-";
    }
    if (payments.total_items === 0) {
      return "No payments found";
    }

    const from = (payments.page - 1) * payments.page_size + 1;
    const to = Math.min(payments.page * payments.page_size, payments.total_items);
    return `${from}-${to} of ${payments.total_items}`;
  }, [payments]);

  return (
    <section className="module-page">
      <header className="module-header">
        <div>
          <h1>Payments</h1>
          <p>Track payment history, providers, statuses and timestamps.</p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={() => void loadPayments()} disabled={isLoading}>
          {isLoading ? "Refreshing..." : "Refresh"}
        </button>
      </header>

      {error ? <div className="dashboard-error">{error}</div> : null}

      <section className="search-strip payments-search-strip" aria-label="Payments filters">
        <select
          className="users-filter-select"
          value={draftFilters.status_filter}
          onChange={(event) => setDraftFilters((prev) => ({ ...prev, status_filter: event.target.value as PaymentStatus | "" }))}
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="successful">Successful</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
          <option value="refunded">Refunded</option>
        </select>

        <input
          placeholder="User ID"
          value={draftFilters.user_id}
          onChange={(event) => setDraftFilters((prev) => ({ ...prev, user_id: event.target.value }))}
          inputMode="numeric"
        />

        <input
          placeholder="Listing ID"
          value={draftFilters.listing_id}
          onChange={(event) => setDraftFilters((prev) => ({ ...prev, listing_id: event.target.value }))}
          inputMode="numeric"
        />

        <input
          placeholder="Provider"
          value={draftFilters.payment_provider}
          onChange={(event) => setDraftFilters((prev) => ({ ...prev, payment_provider: event.target.value }))}
        />

        <label className="payments-filter-field">
          Created from
          <input
            type="datetime-local"
            value={draftFilters.created_from}
            onChange={(event) => setDraftFilters((prev) => ({ ...prev, created_from: event.target.value }))}
          />
        </label>

        <label className="payments-filter-field">
          Created to
          <input
            type="datetime-local"
            value={draftFilters.created_to}
            onChange={(event) => setDraftFilters((prev) => ({ ...prev, created_to: event.target.value }))}
          />
        </label>

        <label className="payments-filter-field">
          Paid from
          <input
            type="datetime-local"
            value={draftFilters.paid_from}
            onChange={(event) => setDraftFilters((prev) => ({ ...prev, paid_from: event.target.value }))}
          />
        </label>

        <label className="payments-filter-field">
          Paid to
          <input
            type="datetime-local"
            value={draftFilters.paid_to}
            onChange={(event) => setDraftFilters((prev) => ({ ...prev, paid_to: event.target.value }))}
          />
        </label>

        <button type="button" className="btn btn-ghost" onClick={onResetFilters}>
          Reset
        </button>
        <button type="button" className="btn btn-primary" onClick={onApplyFilters}>
          Apply filters
        </button>
      </section>

      <section className="table-card" aria-label="Payments table">
        <div className="table-head users-table-head">
          <strong>Payments</strong>
          <span>{summaryText}</span>
        </div>

        <div className="payments-table-wrap">
          <table className="payments-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>User</th>
                <th>Listing</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Provider</th>
                <th>Created</th>
                <th>Paid</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={9} className="users-empty-cell">
                    {isLoading ? "Loading payments..." : "No payments found"}
                  </td>
                </tr>
              ) : (
                rows.map((item) => (
                  <tr key={item.id}>
                    <td>#{item.id}</td>
                    <td>{item.user_id}</td>
                    <td>{item.listing_id ?? "-"}</td>
                    <td>
                      <strong>{formatAmount(item.amount, item.currency)}</strong>
                    </td>
                    <td>
                      <span className={`users-status-badge ${statusClass(item.status)}`}>
                        {statusLabel(item.status)}
                      </span>
                    </td>
                    <td>
                      <div className="users-name-cell">
                        <strong>{item.payment_provider}</strong>
                        <span>{item.provider_reference ?? "No reference"}</span>
                      </div>
                    </td>
                    <td>{formatDate(item.created_at)}</td>
                    <td>{formatDate(item.paid_at)}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-ghost"
                        onClick={() => {
                          setSelectedPayment(item);
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
            Page {payments?.page ?? page}{totalPages ? ` / ${totalPages}` : ""}
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
        title="Payment detail"
        subtitle={selectedPayment ? `Payment #${selectedPayment.id}` : "No payment selected"}
      >
        <div className="users-detail-body">
          {!selectedPayment ? <p>Select a payment and click Details.</p> : null}

          {selectedPayment ? (
            <div className="dashboard-stats-grid">
              <article className="dashboard-stat-group">
                <h3>Payment</h3>
                <p>ID: <strong>#{selectedPayment.id}</strong></p>
                <p>Status: <strong>{statusLabel(selectedPayment.status)}</strong></p>
                <p>Amount: <strong>{formatAmount(selectedPayment.amount, selectedPayment.currency)}</strong></p>
              </article>

              <article className="dashboard-stat-group">
                <h3>Links</h3>
                <p>User ID: <strong>{selectedPayment.user_id}</strong></p>
                <p>Listing ID: <strong>{selectedPayment.listing_id ?? "-"}</strong></p>
                <p>Provider: <strong>{selectedPayment.payment_provider}</strong></p>
              </article>

              <article className="dashboard-stat-group">
                <h3>Provider Reference</h3>
                <p><strong>{selectedPayment.provider_reference ?? "No provider reference"}</strong></p>
              </article>

              <article className="dashboard-stat-group">
                <h3>Timestamps</h3>
                <p>Created: <strong>{formatDate(selectedPayment.created_at)}</strong></p>
                <p>Updated: <strong>{formatDate(selectedPayment.updated_at)}</strong></p>
                <p>Paid: <strong>{formatDate(selectedPayment.paid_at)}</strong></p>
              </article>
            </div>
          ) : null}
        </div>
      </Modal>
    </section>
  );
}
