import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../../app/auth/AuthContext";
import { usePageI18n } from "../../app/i18n/I18nContext";
import { formatCurrency, formatDateTime, formatInteger } from "../../shared/i18n/format";

type AdminDashboardResponse = {
  generated_at: string;
  total_users: number;
  active_users: number;
  blocked_users: number;
  total_listings: number;
  pending_listings: number;
  approved_listings: number;
  rejected_listings: number;
  total_conversations: number;
  total_messages: number;
  total_reports: number;
  total_payments: number;
  total_promotion_revenue: string | number;
  active_subscriptions: number;
  active_promotions: number;
};

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Failed to load dashboard";
}

export function DashboardPage() {
  const { authFetch } = useAuth();
  const { t, language } = usePageI18n("dashboard");

  const [data, setData] = useState<AdminDashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await authFetch("/admin/dashboard");
      if (!response.ok) {
        let message = "Failed to load dashboard";
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = "Failed to load dashboard";
        }
        throw new Error(message);
      }

      const payload = (await response.json()) as AdminDashboardResponse;
      setData(payload);
    } catch (loadError) {
      setError(extractErrorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, [authFetch]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const generatedAtText = useMemo(() => {
    return formatDateTime(data?.generated_at ?? null, language);
  }, [data?.generated_at, language]);

  const fmtCount = (value: number | undefined) => (value == null ? "--" : formatInteger(value, language));

  const totalUsers = fmtCount(data?.total_users);
  const pendingListings = fmtCount(data?.pending_listings);
  const totalReports = fmtCount(data?.total_reports);

  return (
    <section className="module-page">
      <header className="module-header">
        <div>
          <h1>{t("title", "Dashboard")}</h1>
          <p>{t("subtitle", "Operational overview and moderation shortcuts.")}</p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={() => void loadDashboard()} disabled={isLoading}>
          {isLoading ? t("refreshing", "Refreshing...") : t("refresh", "Refresh")}
        </button>
      </header>

      {error ? <div className="dashboard-error">{error}</div> : null}

      <div className="kpi-grid">
        <article>
          <h3>{t("total_users", "Total Users")}</h3>
          <strong>{totalUsers}</strong>
        </article>
        <article>
          <h3>{t("pending_listings", "Pending Listings")}</h3>
          <strong>{pendingListings}</strong>
        </article>
        <article>
          <h3>{t("total_reports", "Total Reports")}</h3>
          <strong>{totalReports}</strong>
        </article>
        <article>
          <h3>{t("active_promotions", "Active Promotions")}</h3>
          <strong>{fmtCount(data?.active_promotions)}</strong>
        </article>
      </div>

      <section className="table-card" aria-label="Detailed dashboard metrics">
        <div className="table-head">
          <strong>{t("detailed_statistics", "Detailed statistics")}</strong>
          <span>{t("generated_at", "Generated at")}: {generatedAtText}</span>
        </div>
        <div className="dashboard-stats-grid">
          <article className="dashboard-stat-group">
            <h3>{t("users_section", "Users")}</h3>
            <p>{t("active", "Active")}: <strong>{fmtCount(data?.active_users)}</strong></p>
            <p>{t("blocked", "Blocked")}: <strong>{fmtCount(data?.blocked_users)}</strong></p>
          </article>
          <article className="dashboard-stat-group">
            <h3>{t("listings_section", "Listings")}</h3>
            <p>{t("total", "Total")}: <strong>{fmtCount(data?.total_listings)}</strong></p>
            <p>{t("approved", "Approved")}: <strong>{fmtCount(data?.approved_listings)}</strong></p>
            <p>{t("rejected", "Rejected")}: <strong>{fmtCount(data?.rejected_listings)}</strong></p>
          </article>
          <article className="dashboard-stat-group">
            <h3>{t("communication_section", "Communication")}</h3>
            <p>{t("conversations", "Conversations")}: <strong>{fmtCount(data?.total_conversations)}</strong></p>
            <p>{t("messages", "Messages")}: <strong>{fmtCount(data?.total_messages)}</strong></p>
          </article>
          <article className="dashboard-stat-group">
            <h3>{t("payments_section", "Payments")}</h3>
            <p>{t("total_payments", "Total payments")}: <strong>{fmtCount(data?.total_payments)}</strong></p>
            <p>
              {t("promotion_revenue", "Promotion revenue")}: <strong>{data ? formatCurrency(data.total_promotion_revenue, "KGS", language) : "--"}</strong>
            </p>
            <p>{t("active_subscriptions", "Active subscriptions")}: <strong>{fmtCount(data?.active_subscriptions)}</strong></p>
          </article>
        </div>
      </section>

      <section className="quick-actions">
        <h2>{t("quick_actions", "Quick actions")}</h2>
        <div>
          <Link className="btn btn-primary" to="/listings">{t("review_listings", "Review listings")}</Link>
          <Link className="btn btn-ghost" to="/reports">{t("open_reports_queue", "Open reports queue")}</Link>
          <Link className="btn btn-ghost" to="/users">{t("manage_users", "Manage users")}</Link>
        </div>
      </section>
    </section>
  );
}
