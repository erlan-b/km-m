import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../../app/auth/AuthContext";
import { usePageI18n } from "../../app/i18n/I18nContext";

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
  total_subscription_revenue: string | number;
  active_subscriptions: number;
};

function formatRevenue(value: string | number): string {
  const numericValue = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(numericValue)) {
    return String(value);
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(numericValue);
}

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Failed to load dashboard";
}

export function DashboardPage() {
  const { authFetch } = useAuth();
  const { t } = usePageI18n("dashboard");

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
    if (!data?.generated_at) {
      return "-";
    }

    const parsed = new Date(data.generated_at);
    if (Number.isNaN(parsed.getTime())) {
      return data.generated_at;
    }

    return parsed.toLocaleString();
  }, [data?.generated_at]);

  const totalUsers = data?.total_users ?? "--";
  const pendingListings = data?.pending_listings ?? "--";
  const totalReports = data?.total_reports ?? "--";
  const activeSubscriptions = data?.active_subscriptions ?? "--";

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
          <h3>{t("active_subscriptions", "Active Subscriptions")}</h3>
          <strong>{activeSubscriptions}</strong>
        </article>
      </div>

      <section className="table-card" aria-label="Detailed dashboard metrics">
        <div className="table-head">
          <strong>Detailed statistics</strong>
          <span>{t("generated_at", "Generated at")}: {generatedAtText}</span>
        </div>
        <div className="dashboard-stats-grid">
          <article className="dashboard-stat-group">
            <h3>Users</h3>
            <p>Active: <strong>{data?.active_users ?? "--"}</strong></p>
            <p>Blocked: <strong>{data?.blocked_users ?? "--"}</strong></p>
          </article>
          <article className="dashboard-stat-group">
            <h3>Listings</h3>
            <p>Total: <strong>{data?.total_listings ?? "--"}</strong></p>
            <p>Approved: <strong>{data?.approved_listings ?? "--"}</strong></p>
            <p>Rejected: <strong>{data?.rejected_listings ?? "--"}</strong></p>
          </article>
          <article className="dashboard-stat-group">
            <h3>Communication</h3>
            <p>Conversations: <strong>{data?.total_conversations ?? "--"}</strong></p>
            <p>Messages: <strong>{data?.total_messages ?? "--"}</strong></p>
          </article>
          <article className="dashboard-stat-group">
            <h3>Payments</h3>
            <p>Total payments: <strong>{data?.total_payments ?? "--"}</strong></p>
            <p>Subscription revenue: <strong>{data ? formatRevenue(data.total_subscription_revenue) : "--"}</strong></p>
          </article>
        </div>
      </section>

      <section className="quick-actions">
        <h2>Quick actions</h2>
        <div>
          <Link className="btn btn-primary" to="/listings">Review listings</Link>
          <Link className="btn btn-ghost" to="/reports">Open reports queue</Link>
          <Link className="btn btn-ghost" to="/users">Manage users</Link>
        </div>
      </section>
    </section>
  );
}
