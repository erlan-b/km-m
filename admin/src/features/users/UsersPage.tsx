import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "../../app/auth/AuthContext";
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
  promotion_count: number;
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

function statusLabel(status: AccountStatus): string {
  if (status === "active") {
    return "Active";
  }
  if (status === "blocked") {
    return "Blocked";
  }
  if (status === "pending_verification") {
    return "Pending verification";
  }
  return "Deactivated";
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed";
}

export function UsersPage() {
  const { authFetch } = useAuth();

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
        throw new Error("Failed to load users");
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
        throw new Error("Failed to load user details");
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

  const applyStatusAction = async (user: AdminUserListItem) => {
    const actionPath = user.account_status === "blocked" ? "unsuspend" : "suspend";
    const actionLabel = actionPath === "suspend" ? "Suspend" : "Unsuspend";

    const confirmed = window.confirm(`${actionLabel} user ${user.full_name}?`);
    if (!confirmed) {
      return;
    }

    const reasonInput = window.prompt("Reason (optional):", "");
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
      return "No users found";
    }

    const from = (users.page - 1) * users.page_size + 1;
    const to = Math.min(users.page * users.page_size, users.total_items);
    return `${from}-${to} of ${users.total_items}`;
  }, [users]);

  return (
    <section className="module-page">
      <header className="module-header">
        <div>
          <h1>Users</h1>
          <p>Search users, inspect profile statistics, suspend and unsuspend.</p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={() => void loadUsers()} disabled={isLoading}>
          {isLoading ? "Refreshing..." : "Refresh"}
        </button>
      </header>

      {error ? <div className="dashboard-error">{error}</div> : null}

      <form className="search-strip" onSubmit={onSearchSubmit}>
        <input
          placeholder="Search by full name or email"
          aria-label="Search users"
          value={queryInput}
          onChange={(event) => setQueryInput(event.target.value)}
        />
        <select
          className="users-filter-select"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as AccountStatus | "")}
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="blocked">Blocked</option>
          <option value="pending_verification">Pending verification</option>
          <option value="deactivated">Deactivated</option>
        </select>
        <select className="users-filter-select" value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}>
          <option value="">All roles</option>
          <option value="admin">Admin</option>
          <option value="moderator">Moderator</option>
          <option value="user">User</option>
        </select>
        <button type="button" className="btn btn-ghost" onClick={onApplyFilters}>Apply filters</button>
        <button type="submit" className="btn btn-primary">Search</button>
      </form>

      <section className="table-card" aria-label="Users table">
        <div className="table-head users-table-head">
          <strong>Users</strong>
          <span>{summaryText}</span>
        </div>

        <div className="users-table-wrap">
          <table className="users-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Status</th>
                <th>Roles</th>
                <th>Language</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="users-empty-cell">
                    {isLoading ? "Loading users..." : "No users found"}
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
                        {statusLabel(user.account_status)}
                      </span>
                    </td>
                    <td>{user.roles.join(", ") || "-"}</td>
                    <td>{user.preferred_language}</td>
                    <td>{formatDate(user.created_at)}</td>
                    <td>
                      <div className="users-actions-cell">
                        <button type="button" className="btn btn-ghost" onClick={() => void openDetail(user.id)}>
                          Details
                        </button>
                        <button
                          type="button"
                          className="btn btn-primary"
                          onClick={() => void applyStatusAction(user)}
                          disabled={actionBusyUserId === user.id}
                        >
                          {actionBusyUserId === user.id
                            ? "Processing..."
                            : user.account_status === "blocked"
                              ? "Unsuspend"
                              : "Suspend"}
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
            Previous
          </button>
          <span className="users-page-indicator">
            Page {users?.page ?? page}{totalPages ? ` / ${totalPages}` : ""}
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
        onClose={closeDetailModal}
        title="User detail"
        subtitle={isDetailLoading ? "Loading..." : selectedDetail ? selectedDetail.email : "No user selected"}
      >
        <div className="users-detail-body">
          {detailError ? <div className="dashboard-error">{detailError}</div> : null}

          {!detailError && isDetailLoading ? <p>Loading user detail...</p> : null}

          {!detailError && !isDetailLoading && !selectedDetail ? <p>Select a user row and click Details.</p> : null}

          {selectedDetail ? (
            <div className="dashboard-stats-grid">
              <article className="dashboard-stat-group">
                <h3>Profile</h3>
                <p>Name: <strong>{selectedDetail.full_name}</strong></p>
                <p>Status: <strong>{statusLabel(selectedDetail.account_status)}</strong></p>
                <p>Roles: <strong>{selectedDetail.roles.join(", ") || "-"}</strong></p>
                <p>Language: <strong>{selectedDetail.preferred_language}</strong></p>
              </article>
              <article className="dashboard-stat-group">
                <h3>Activity</h3>
                <p>Listings: <strong>{selectedDetail.listing_count}</strong></p>
                <p>Active listings: <strong>{selectedDetail.active_listing_count}</strong></p>
                <p>Reports: <strong>{selectedDetail.report_count}</strong></p>
                <p>Conversations: <strong>{selectedDetail.conversation_count}</strong></p>
              </article>
              <article className="dashboard-stat-group">
                <h3>Commerce</h3>
                <p>Payments: <strong>{selectedDetail.payment_count}</strong></p>
                <p>Promotions: <strong>{selectedDetail.promotion_count}</strong></p>
              </article>
              <article className="dashboard-stat-group">
                <h3>Timestamps</h3>
                <p>Created: <strong>{formatDate(selectedDetail.created_at)}</strong></p>
                <p>Updated: <strong>{formatDate(selectedDetail.updated_at)}</strong></p>
              </article>
            </div>
          ) : null}
        </div>
      </Modal>
    </section>
  );
}
