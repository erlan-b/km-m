import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../../app/auth/AuthContext";
import { usePageI18n } from "../../app/i18n/I18nContext";
import { formatDateTime, formatInteger } from "../../shared/i18n/format";
import { Modal } from "../common/Modal";

type AccountStatus = "active" | "blocked" | "pending_verification" | "deactivated";

type AdminUserListItem = {
  id: number;
  full_name: string;
  email: string;
  preferred_language: string;
  account_status: AccountStatus;
  roles: string[];
  created_at: string;
  updated_at: string;
};

type AdminUserListResponse = {
  items: AdminUserListItem[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
};

type AdminUserDetailResponse = {
  id: number;
  full_name: string;
  email: string;
  preferred_language: string;
  account_status: AccountStatus;
  roles: string[];
  created_at: string;
  updated_at: string;
  listing_count: number;
  active_listing_count: number;
  payment_count: number;
  subscription_count: number;
  report_count: number;
  conversation_count: number;
};

type AdminUserStatusResponse = {
  id: number;
  full_name: string;
  email: string;
  account_status: AccountStatus;
  updated_at: string;
  message: string;
};

function statusLabel(status: AccountStatus, t: (key: string, fallback: string) => string): string {
  if (status === "active") {
    return t("status_active", "Active");
  }
  if (status === "blocked") {
    return t("status_blocked", "Blocked");
  }
  if (status === "pending_verification") {
    return t("status_pending_verification", "Pending verification");
  }
  return t("status_deactivated", "Deactivated");
}

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed";
}

export function UsersPage() {
  const { authFetch } = useAuth();
  const { t, language } = usePageI18n("users");
  const navigate = useNavigate();

  const [users, setUsers] = useState<AdminUserListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [queryInput, setQueryInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<AccountStatus | "">("");
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [page, setPage] = useState(1);

  const [selectedDetail, setSelectedDetail] = useState<AdminUserDetailResponse | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [actionBusyUserId, setActionBusyUserId] = useState<number | null>(null);

  const loadUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", "20");

      if (searchTerm.trim()) {
        params.set("q", searchTerm.trim());
      }
      if (statusFilter) {
        params.set("status_filter", statusFilter);
      }
      if (roleFilter.trim()) {
        params.set("role", roleFilter.trim());
      }

      const response = await authFetch(`/admin/users?${params.toString()}`);
      if (!response.ok) {
        throw new Error(t("error_load_users", "Failed to load users"));
      }

      const payload = (await response.json()) as AdminUserListResponse;
      setUsers(payload);
    } catch (loadError) {
      setError(extractErrorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, [authFetch, page, roleFilter, searchTerm, statusFilter]);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  const onSearchSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPage(1);
    setSearchTerm(queryInput);
  };

  const onApplyFilters = () => {
    setPage(1);
    void loadUsers();
  };

  const openDetail = async (userId: number) => {
    setIsDetailModalOpen(true);
    setIsDetailLoading(true);
    setDetailError(null);
    setSelectedDetail(null);

    try {
      const response = await authFetch(`/admin/users/${userId}`);
      if (!response.ok) {
        throw new Error(t("error_load_user_details", "Failed to load user details"));
      }
      const payload = (await response.json()) as AdminUserDetailResponse;
      setSelectedDetail(payload);
    } catch (detailLoadError) {
      setSelectedDetail(null);
      setDetailError(extractErrorMessage(detailLoadError));
    } finally {
      setIsDetailLoading(false);
    }
  };

  const closeDetailModal = () => {
    setIsDetailModalOpen(false);
  };

  const openRelatedSection = (path: string) => {
    if (!selectedDetail) {
      return;
    }

    setIsDetailModalOpen(false);
    navigate(`${path}?user_id=${selectedDetail.id}`);
  };

  const applyStatusAction = async (user: AdminUserListItem) => {
    const actionPath = user.account_status === "blocked" ? "unsuspend" : "suspend";
    const actionLabel = actionPath === "suspend" ? t("suspend", "Suspend") : t("unsuspend", "Unsuspend");

    const confirmed = window.confirm(`${actionLabel} ${t("user_label", "user")} ${user.full_name}?`);
    if (!confirmed) {
      return;
    }

    const reasonInput = window.prompt(t("reason_optional", "Reason (optional):"), "");
    const reason = typeof reasonInput === "string" && reasonInput.trim() ? reasonInput.trim() : null;

    setActionBusyUserId(user.id);
    setError(null);

    try {
      const response = await authFetch(`/admin/users/${user.id}/${actionPath}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      });

      if (!response.ok) {
        let message = `Failed to ${actionPath} user`;
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = `Failed to ${actionPath} user`;
        }
        throw new Error(message);
      }

      const payload = (await response.json()) as AdminUserStatusResponse;

      setUsers((prev) => {
        if (!prev) {
          return prev;
        }
        return {
          ...prev,
          items: prev.items.map((item) =>
            item.id === payload.id
              ? {
                  ...item,
                  account_status: payload.account_status,
                  updated_at: payload.updated_at,
                }
              : item,
          ),
        };
      });

      if (selectedDetail?.id === payload.id) {
        setSelectedDetail({
          ...selectedDetail,
          account_status: payload.account_status,
          updated_at: payload.updated_at,
        });
      }
    } catch (actionError) {
      setError(extractErrorMessage(actionError));
    } finally {
      setActionBusyUserId(null);
    }
  };

  const rows = users?.items ?? [];
  const totalPages = users?.total_pages ?? 0;
  const canPrev = page > 1;
  const canNext = totalPages > 0 && page < totalPages;

  const summaryText = useMemo(() => {
    if (!users) {
      return "-";
    }
    if (users.total_items === 0) {
      return t("no_users_found", "No users found");
    }

    const from = (users.page - 1) * users.page_size + 1;
    const to = Math.min(users.page * users.page_size, users.total_items);
    return `${formatInteger(from, language)}-${formatInteger(to, language)} ${t("of", "of")} ${formatInteger(users.total_items, language)}`;
  }, [language, t, users]);

  return (
    <section className="module-page">
      <header className="module-header">
        <div>
          <h1>{t("title", "Users")}</h1>
          <p>{t("subtitle", "Search users, inspect profile statistics, suspend and unsuspend.")}</p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={() => void loadUsers()} disabled={isLoading}>
          {isLoading ? t("refreshing", "Refreshing...") : t("refresh", "Refresh")}
        </button>
      </header>

      {error ? <div className="dashboard-error">{error}</div> : null}

      <form className="search-strip" onSubmit={onSearchSubmit}>
        <input
          placeholder={t("search_placeholder", "Search by full name or email")}
          aria-label={t("search_users", "Search users")}
          value={queryInput}
          onChange={(event) => setQueryInput(event.target.value)}
        />
        <select
          className="users-filter-select"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as AccountStatus | "")}
        >
          <option value="">{t("all_statuses", "All statuses")}</option>
          <option value="active">{t("status_active", "Active")}</option>
          <option value="blocked">{t("status_blocked", "Blocked")}</option>
          <option value="pending_verification">{t("status_pending_verification", "Pending verification")}</option>
          <option value="deactivated">{t("status_deactivated", "Deactivated")}</option>
        </select>
        <select className="users-filter-select" value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}>
          <option value="">{t("all_roles", "All roles")}</option>
          <option value="admin">{t("role_admin", "Admin")}</option>
          <option value="moderator">{t("role_moderator", "Moderator")}</option>
          <option value="user">{t("role_user", "User")}</option>
        </select>
        <button type="button" className="btn btn-ghost" onClick={onApplyFilters}>{t("apply_filters", "Apply filters")}</button>
        <button type="submit" className="btn btn-primary">{t("search", "Search")}</button>
      </form>

      <section className="table-card" aria-label="Users table">
        <div className="table-head users-table-head">
          <strong>{t("table_users", "Users")}</strong>
          <span>{summaryText}</span>
        </div>

        <div className="users-table-wrap">
          <table className="users-table">
            <thead>
              <tr>
                <th>{t("user_column", "User")}</th>
                <th>{t("status", "Status")}</th>
                <th>{t("roles", "Roles")}</th>
                <th>{t("language", "Language")}</th>
                <th>{t("created", "Created")}</th>
                <th>{t("actions", "Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="users-empty-cell">
                    {isLoading ? t("loading_users", "Loading users...") : t("no_users_found", "No users found")}
                  </td>
                </tr>
              ) : (
                rows.map((user) => (
                  <tr key={user.id}>
                    <td>
                      <div className="users-name-cell">
                        <strong>{user.full_name}</strong>
                        <span>{user.email}</span>
                      </div>
                    </td>
                    <td>
                      <span className={`users-status-badge users-status-${user.account_status}`}>
                        {statusLabel(user.account_status, t)}
                      </span>
                    </td>
                    <td>{user.roles.join(", ") || "-"}</td>
                    <td>{user.preferred_language}</td>
                    <td>{formatDateTime(user.created_at, language)}</td>
                    <td>
                      <div className="users-actions-cell">
                        <button type="button" className="btn btn-ghost" onClick={() => void openDetail(user.id)}>
                          {t("details", "Details")}
                        </button>
                        <button
                          type="button"
                          className="btn btn-primary"
                          onClick={() => void applyStatusAction(user)}
                          disabled={actionBusyUserId === user.id}
                        >
                          {actionBusyUserId === user.id
                            ? t("processing", "Processing...")
                            : user.account_status === "blocked"
                              ? t("unsuspend", "Unsuspend")
                              : t("suspend", "Suspend")}
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
            {t("page", "Page")} {formatInteger(users?.page ?? page, language)}{totalPages ? ` / ${formatInteger(totalPages, language)}` : ""}
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
        onClose={closeDetailModal}
        title={t("user_detail", "User detail")}
        subtitle={isDetailLoading ? t("loading", "Loading...") : selectedDetail ? selectedDetail.email : t("no_user_selected", "No user selected")}
      >
        <div className="users-detail-body">
          {detailError ? <div className="dashboard-error">{detailError}</div> : null}

          {!detailError && isDetailLoading ? <p>{t("loading_user_detail", "Loading user detail...")}</p> : null}

          {!detailError && !isDetailLoading && !selectedDetail ? <p>{t("select_user_row", "Select a user row and click Details.")}</p> : null}

          {selectedDetail ? (
            <div className="dashboard-stats-grid">
              <article className="dashboard-stat-group">
                <h3>{t("profile", "Profile")}</h3>
                <p>{t("name", "Name")}: <strong>{selectedDetail.full_name}</strong></p>
                <p>{t("status", "Status")}: <strong>{statusLabel(selectedDetail.account_status, t)}</strong></p>
                <p>{t("subscription", "Subscription")}: <strong>{selectedDetail.subscription_count > 0 ? t("sub", "Sub") : t("no_sub", "No sub")}</strong></p>
                <p>{t("roles", "Roles")}: <strong>{selectedDetail.roles.join(", ") || "-"}</strong></p>
                <p>{t("language", "Language")}: <strong>{selectedDetail.preferred_language}</strong></p>
              </article>
              <article className="dashboard-stat-group">
                <h3>{t("activity", "Activity")}</h3>
                <p>{t("listings", "Listings")}: <strong>{formatInteger(selectedDetail.listing_count, language)}</strong></p>
                <p>{t("active_listings", "Active listings")}: <strong>{formatInteger(selectedDetail.active_listing_count, language)}</strong></p>
                <p>{t("reports", "Reports")}: <strong>{formatInteger(selectedDetail.report_count, language)}</strong></p>
                <p>{t("conversations", "Conversations")}: <strong>{formatInteger(selectedDetail.conversation_count, language)}</strong></p>
              </article>
              <article className="dashboard-stat-group">
                <h3>{t("commerce", "Commerce")}</h3>
                <p>{t("payments", "Payments")}: <strong>{formatInteger(selectedDetail.payment_count, language)}</strong></p>
                <p>{t("subscriptions", "Subscriptions")}: <strong>{formatInteger(selectedDetail.subscription_count, language)}</strong></p>
                <div className="users-detail-links">
                  <button type="button" className="btn btn-ghost" onClick={() => openRelatedSection("/payments")}>
                    {t("open_payments", "Open payments")}
                  </button>
                  <button type="button" className="btn btn-ghost" onClick={() => openRelatedSection("/promotions")}>
                    {t("open_promotions", "Open promotions")}
                  </button>
                  <button type="button" className="btn btn-ghost" onClick={() => openRelatedSection("/messages")}>
                    {t("open_messages", "Open messages")}
                  </button>
                </div>
              </article>
              <article className="dashboard-stat-group">
                <h3>{t("timestamps", "Timestamps")}</h3>
                <p>{t("created", "Created")}: <strong>{formatDateTime(selectedDetail.created_at, language)}</strong></p>
                <p>{t("updated", "Updated")}: <strong>{formatDateTime(selectedDetail.updated_at, language)}</strong></p>
              </article>
            </div>
          ) : null}
        </div>
      </Modal>
    </section>
  );
}
