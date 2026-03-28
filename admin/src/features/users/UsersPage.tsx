import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../../app/auth/AuthContext";
import { usePageI18n } from "../../app/i18n/I18nContext";
import { formatDateTime, formatInteger, localeFromLanguage } from "../../shared/i18n/format";
import { Modal } from "../common/Modal";

type AccountStatus = "active" | "blocked" | "pending_verification" | "deactivated";
type SellerType = "owner" | "company";
type VerificationStatus = "unverified" | "pending" | "verified" | "rejected";

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
  phone: string | null;
  profile_image_url: string | null;
  bio: string | null;
  city: string | null;
  preferred_language: string;
  account_status: AccountStatus;
  seller_type: SellerType;
  company_name: string | null;
  verification_status: VerificationStatus;
  verified_badge: boolean;
  response_rate: number | null;
  last_seen_at: string | null;
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

type AdminUserVerificationActionRequest = {
  verification_status: VerificationStatus;
  reason: string | null;
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

function sellerTypeLabel(sellerType: SellerType, t: (key: string, fallback: string) => string): string {
  if (sellerType === "company") {
    return t("seller_type_company", "Company");
  }
  return t("seller_type_owner", "Owner");
}

function verificationStatusLabel(
  verificationStatus: VerificationStatus,
  t: (key: string, fallback: string) => string,
): string {
  if (verificationStatus === "verified") {
    return t("verification_verified", "Verified");
  }
  if (verificationStatus === "pending") {
    return t("verification_pending", "Pending");
  }
  if (verificationStatus === "rejected") {
    return t("verification_rejected", "Rejected");
  }
  return t("verification_unverified", "Unverified");
}

function formatPercent(value: number | null, language: "en" | "ru"): string {
  if (value === null || !Number.isFinite(value)) {
    return "-";
  }

  return `${new Intl.NumberFormat(localeFromLanguage(language), {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value)}%`;
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
  const [verificationStatusDraft, setVerificationStatusDraft] = useState<VerificationStatus>("unverified");
  const [isVerificationSubmitting, setIsVerificationSubmitting] = useState(false);

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
  }, [authFetch, page, roleFilter, searchTerm, statusFilter, t]);

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

  useEffect(() => {
    const nextVerificationStatus = selectedDetail?.verification_status;
    if (!nextVerificationStatus) {
      return;
    }
    setVerificationStatusDraft(nextVerificationStatus);
  }, [selectedDetail?.verification_status]);

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

  const applyVerificationStatus = async () => {
    if (!selectedDetail) {
      return;
    }

    const nextLabel = verificationStatusLabel(verificationStatusDraft, t);
    const confirmed = window.confirm(
      `${t("set_verification_status", "Set verification status")} '${nextLabel}' ${t("for_user", "for user")} ${selectedDetail.full_name}?`,
    );
    if (!confirmed) {
      return;
    }

    const reasonInput = window.prompt(t("reason_optional", "Reason (optional):"), "");
    const reason = typeof reasonInput === "string" && reasonInput.trim() ? reasonInput.trim() : null;

    setIsVerificationSubmitting(true);
    setDetailError(null);

    try {
      const body: AdminUserVerificationActionRequest = {
        verification_status: verificationStatusDraft,
        reason,
      };

      const response = await authFetch(`/admin/users/${selectedDetail.id}/verification`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        let message = t("error_update_verification", "Failed to update verification status");
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = t("error_update_verification", "Failed to update verification status");
        }
        throw new Error(message);
      }

      const payload = (await response.json()) as AdminUserDetailResponse;
      setSelectedDetail(payload);
      setVerificationStatusDraft(payload.verification_status);

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
                  updated_at: payload.updated_at,
                }
              : item,
          ),
        };
      });
    } catch (actionError) {
      setDetailError(extractErrorMessage(actionError));
    } finally {
      setIsVerificationSubmitting(false);
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
            <div className="dashboard-stats-grid users-detail-grid">
              <article className="dashboard-stat-group">
                <h3>{t("profile", "Profile")}</h3>
                <p>{t("id", "ID")}: <strong>#{formatInteger(selectedDetail.id, language)}</strong></p>
                <p>{t("name", "Name")}: <strong>{selectedDetail.full_name}</strong></p>
                <p>{t("email", "Email")}: <strong>{selectedDetail.email}</strong></p>
                <p>{t("phone", "Phone")}: <strong>{selectedDetail.phone ?? "-"}</strong></p>
                <p>{t("city", "City")}: <strong>{selectedDetail.city ?? "-"}</strong></p>
                <p>{t("roles", "Roles")}: <strong>{selectedDetail.roles.join(", ") || "-"}</strong></p>
                <p>{t("language", "Language")}: <strong>{selectedDetail.preferred_language}</strong></p>
              </article>

              <article className="dashboard-stat-group">
                <h3>{t("verification", "Verification")}</h3>
                <p>{t("status", "Status")}: <strong>{statusLabel(selectedDetail.account_status, t)}</strong></p>
                <p>{t("verification_status", "Verification status")}: <strong>{verificationStatusLabel(selectedDetail.verification_status, t)}</strong></p>
                <p>{t("verified_badge", "Verified badge")}: <strong>{selectedDetail.verified_badge ? t("yes", "Yes") : t("no", "No")}</strong></p>
                <p>{t("seller_type", "Seller type")}: <strong>{sellerTypeLabel(selectedDetail.seller_type, t)}</strong></p>
                <p>{t("company_name", "Company name")}: <strong>{selectedDetail.company_name ?? "-"}</strong></p>
                <p>{t("response_rate", "Response rate")}: <strong>{formatPercent(selectedDetail.response_rate, language)}</strong></p>

                <div className="users-verification-controls">
                  <label>
                    {t("manage_verification", "Manage verification")}
                    <select
                      className="users-filter-select"
                      value={verificationStatusDraft}
                      onChange={(event) => setVerificationStatusDraft(event.target.value as VerificationStatus)}
                    >
                      <option value="unverified">{t("verification_unverified", "Unverified")}</option>
                      <option value="pending">{t("verification_pending", "Pending")}</option>
                      <option value="verified">{t("verification_verified", "Verified")}</option>
                      <option value="rejected">{t("verification_rejected", "Rejected")}</option>
                    </select>
                  </label>

                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={isVerificationSubmitting || verificationStatusDraft === selectedDetail.verification_status}
                    onClick={() => void applyVerificationStatus()}
                  >
                    {isVerificationSubmitting ? t("applying", "Applying...") : t("apply_verification", "Apply verification")}
                  </button>
                </div>
              </article>

              <article className="dashboard-stat-group">
                <h3>{t("profile_data", "Profile data")}</h3>
                <p>{t("profile_image_url", "Profile image URL")}: <strong>{selectedDetail.profile_image_url ?? "-"}</strong></p>
                <p>{t("bio", "Bio")}: <strong>{selectedDetail.bio ?? "-"}</strong></p>
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
              </article>

              <article className="dashboard-stat-group">
                <h3>{t("timestamps", "Timestamps")}</h3>
                <p>{t("last_seen", "Last seen")}: <strong>{formatDateTime(selectedDetail.last_seen_at, language)}</strong></p>
                <p>{t("created", "Created")}: <strong>{formatDateTime(selectedDetail.created_at, language)}</strong></p>
                <p>{t("updated", "Updated")}: <strong>{formatDateTime(selectedDetail.updated_at, language)}</strong></p>
              </article>

              <article className="dashboard-stat-group users-related-actions-card">
                <h3>{t("related_sections", "Related sections")}</h3>
                <div className="users-related-actions">
                  <div className="users-related-action-item">
                    <p>{t("payments_records", "Payments records")}</p>
                    <button type="button" className="btn btn-ghost" onClick={() => openRelatedSection("/payments")}>
                      {t("open_payments", "Open payments")}
                    </button>
                  </div>
                  <div className="users-related-action-item">
                    <p>{t("promotions_management", "Promotions management")}</p>
                    <button type="button" className="btn btn-ghost" onClick={() => openRelatedSection("/promotions")}>
                      {t("open_promotions", "Open promotions")}
                    </button>
                  </div>
                  <div className="users-related-action-item">
                    <p>{t("messages_history", "Messages history")}</p>
                    <button type="button" className="btn btn-ghost" onClick={() => openRelatedSection("/messages")}>
                      {t("open_messages", "Open messages")}
                    </button>
                  </div>
                </div>
              </article>
            </div>
          ) : null}
        </div>
      </Modal>
    </section>
  );
}
