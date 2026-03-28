import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "../../app/auth/AuthContext";
import { usePageI18n } from "../../app/i18n/I18nContext";
import { formatCurrency, formatDateTime, formatInteger } from "../../shared/i18n/format";
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

function statusLabel(status: PaymentStatus, t: (key: string, fallback: string) => string): string {
  if (status === "pending") {
    return t("status_pending", "Pending");
  }
  if (status === "successful") {
    return t("status_successful", "Successful");
  }
  if (status === "failed") {
    return t("status_failed", "Failed");
  }
  if (status === "cancelled") {
    return t("status_cancelled", "Cancelled");
  }
  return t("status_refunded", "Refunded");
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

export function PaymentsPage() {
  const { authFetch } = useAuth();
  const { t, language } = usePageI18n("payments");

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
        let message = t("error_load_payments", "Failed to load payments");
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = t("error_load_payments", "Failed to load payments");
        }
        throw new Error(message);
      }

      const payload = (await response.json()) as PaymentHistoryResponse;
      setPayments(payload);

      if (payload.items.length === 0) {
        setSelectedPayment(null);
        setIsDetailModalOpen(false);
      } else {
        setSelectedPayment((previous) => {
          if (!previous) {
            return previous;
          }
          return payload.items.find((item) => item.id === previous.id) ?? null;
        });
      }
    } catch (loadError) {
      setError(extractErrorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, [appliedFilters, authFetch, page]);

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
      return t("no_payments_found", "No payments found");
    }

    const from = (payments.page - 1) * payments.page_size + 1;
    const to = Math.min(payments.page * payments.page_size, payments.total_items);
    return `${formatInteger(from, language)}-${formatInteger(to, language)} ${t("of", "of")} ${formatInteger(payments.total_items, language)}`;
  }, [language, payments, t]);

  return (
    <section className="module-page">
      <header className="module-header">
        <div>
          <h1>{t("title", "Payments")}</h1>
          <p>{t("subtitle", "Track payment history, providers, statuses and timestamps.")}</p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={() => void loadPayments()} disabled={isLoading}>
          {isLoading ? t("refreshing", "Refreshing...") : t("refresh", "Refresh")}
        </button>
      </header>

      {error ? <div className="dashboard-error">{error}</div> : null}

      <section className="search-strip payments-search-strip" aria-label={t("payments_filters", "Payments filters")}>
        <select
          className="users-filter-select"
          value={draftFilters.status_filter}
          onChange={(event) => setDraftFilters((prev) => ({ ...prev, status_filter: event.target.value as PaymentStatus | "" }))}
        >
          <option value="">{t("all_statuses", "All statuses")}</option>
          <option value="pending">{t("status_pending", "Pending")}</option>
          <option value="successful">{t("status_successful", "Successful")}</option>
          <option value="failed">{t("status_failed", "Failed")}</option>
          <option value="cancelled">{t("status_cancelled", "Cancelled")}</option>
          <option value="refunded">{t("status_refunded", "Refunded")}</option>
        </select>

        <input
          placeholder={t("user_id", "User ID")}
          value={draftFilters.user_id}
          onChange={(event) => setDraftFilters((prev) => ({ ...prev, user_id: event.target.value }))}
          inputMode="numeric"
        />

        <input
          placeholder={t("listing_id", "Listing ID")}
          value={draftFilters.listing_id}
          onChange={(event) => setDraftFilters((prev) => ({ ...prev, listing_id: event.target.value }))}
          inputMode="numeric"
        />

        <input
          placeholder={t("provider", "Provider")}
          value={draftFilters.payment_provider}
          onChange={(event) => setDraftFilters((prev) => ({ ...prev, payment_provider: event.target.value }))}
        />

        <label className="payments-filter-field">
          {t("created_from", "Created from")}
          <input
            type="datetime-local"
            value={draftFilters.created_from}
            onChange={(event) => setDraftFilters((prev) => ({ ...prev, created_from: event.target.value }))}
          />
        </label>

        <label className="payments-filter-field">
          {t("created_to", "Created to")}
          <input
            type="datetime-local"
            value={draftFilters.created_to}
            onChange={(event) => setDraftFilters((prev) => ({ ...prev, created_to: event.target.value }))}
          />
        </label>

        <label className="payments-filter-field">
          {t("paid_from", "Paid from")}
          <input
            type="datetime-local"
            value={draftFilters.paid_from}
            onChange={(event) => setDraftFilters((prev) => ({ ...prev, paid_from: event.target.value }))}
          />
        </label>

        <label className="payments-filter-field">
          {t("paid_to", "Paid to")}
          <input
            type="datetime-local"
            value={draftFilters.paid_to}
            onChange={(event) => setDraftFilters((prev) => ({ ...prev, paid_to: event.target.value }))}
          />
        </label>

        <button type="button" className="btn btn-ghost" onClick={onResetFilters}>
          {t("reset", "Reset")}
        </button>
        <button type="button" className="btn btn-primary" onClick={onApplyFilters}>
          {t("apply_filters", "Apply filters")}
        </button>
      </section>

      <section className="table-card" aria-label={t("payments_table", "Payments table")}>
        <div className="table-head users-table-head">
          <strong>{t("table_payments", "Payments")}</strong>
          <span>{summaryText}</span>
        </div>

        <div className="payments-table-wrap">
          <table className="payments-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>{t("user", "User")}</th>
                <th>{t("listing", "Listing")}</th>
                <th>{t("amount", "Amount")}</th>
                <th>{t("status", "Status")}</th>
                <th>{t("provider", "Provider")}</th>
                <th>{t("created", "Created")}</th>
                <th>{t("paid", "Paid")}</th>
                <th>{t("actions", "Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={9} className="users-empty-cell">
                    {isLoading ? t("loading_payments", "Loading payments...") : t("no_payments_found", "No payments found")}
                  </td>
                </tr>
              ) : (
                rows.map((item) => (
                  <tr key={item.id}>
                    <td>#{formatInteger(item.id, language)}</td>
                    <td>{formatInteger(item.user_id, language)}</td>
                    <td>{item.listing_id == null ? "-" : formatInteger(item.listing_id, language)}</td>
                    <td>
                      <strong>{formatCurrency(item.amount, item.currency, language)}</strong>
                    </td>
                    <td>
                      <span className={`users-status-badge ${statusClass(item.status)}`}>
                        {statusLabel(item.status, t)}
                      </span>
                    </td>
                    <td>
                      <div className="users-name-cell">
                        <strong>{item.payment_provider}</strong>
                        <span>{item.provider_reference ?? t("no_reference", "No reference")}</span>
                      </div>
                    </td>
                    <td>{formatDateTime(item.created_at, language)}</td>
                    <td>{formatDateTime(item.paid_at, language)}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-ghost"
                        onClick={() => {
                          setSelectedPayment(item);
                          setIsDetailModalOpen(true);
                        }}
                      >
                        {t("details", "Details")}
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
            {t("page", "Page")} {formatInteger(payments?.page ?? page, language)}{totalPages ? ` / ${formatInteger(totalPages, language)}` : ""}
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
        open={isDetailModalOpen}
        onClose={() => setIsDetailModalOpen(false)}
        title={t("payment_detail", "Payment detail")}
        subtitle={selectedPayment ? `${t("payment", "Payment")} #${formatInteger(selectedPayment.id, language)}` : t("no_payment_selected", "No payment selected")}
      >
        <div className="users-detail-body">
          {!selectedPayment ? <p>{t("select_payment", "Select a payment and click Details.")}</p> : null}

          {selectedPayment ? (
            <div className="dashboard-stats-grid">
              <article className="dashboard-stat-group">
                <h3>{t("payment", "Payment")}</h3>
                <p>ID: <strong>#{formatInteger(selectedPayment.id, language)}</strong></p>
                <p>{t("status", "Status")}: <strong>{statusLabel(selectedPayment.status, t)}</strong></p>
                <p>{t("amount", "Amount")}: <strong>{formatCurrency(selectedPayment.amount, selectedPayment.currency, language)}</strong></p>
              </article>

              <article className="dashboard-stat-group">
                <h3>{t("links", "Links")}</h3>
                <p>{t("user_id", "User ID")}: <strong>{formatInteger(selectedPayment.user_id, language)}</strong></p>
                <p>{t("listing_id", "Listing ID")}: <strong>{selectedPayment.listing_id == null ? "-" : formatInteger(selectedPayment.listing_id, language)}</strong></p>
                <p>{t("provider", "Provider")}: <strong>{selectedPayment.payment_provider}</strong></p>
              </article>

              <article className="dashboard-stat-group">
                <h3>{t("provider_reference", "Provider Reference")}</h3>
                <p><strong>{selectedPayment.provider_reference ?? t("no_provider_reference", "No provider reference")}</strong></p>
              </article>

              <article className="dashboard-stat-group">
                <h3>{t("timestamps", "Timestamps")}</h3>
                <p>{t("created", "Created")}: <strong>{formatDateTime(selectedPayment.created_at, language)}</strong></p>
                <p>{t("updated", "Updated")}: <strong>{formatDateTime(selectedPayment.updated_at, language)}</strong></p>
                <p>{t("paid", "Paid")}: <strong>{formatDateTime(selectedPayment.paid_at, language)}</strong></p>
              </article>
            </div>
          ) : null}
        </div>
      </Modal>
    </section>
  );
}
