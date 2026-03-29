import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "../../app/auth/AuthContext";
import { usePageI18n } from "../../app/i18n/I18nContext";
import { formatCurrency, formatDateTime, formatInteger } from "../../shared/i18n/format";
import { Modal } from "../common/Modal";

type PromotionStatus = "pending" | "active" | "expired" | "cancelled";

type PromotionPackageItem = {
  id: number;
  title: string;
  description: string | null;
  duration_days: number;
  price: string | number;
  currency: string;
  is_active: boolean;
  created_at: string;
};

type PromotionPackageListResponse = {
  items: PromotionPackageItem[];
};

type PromotionItem = {
  id: number;
  listing_id: number;
  user_id: number;
  promotion_package_id: number;
  target_city: string | null;
  target_category_id: number | null;
  starts_at: string;
  ends_at: string;
  status: PromotionStatus;
  purchased_price: string | number;
  currency: string;
  created_at: string;
};

type PromotionListResponse = {
  items: PromotionItem[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
};

type PromotionFilters = {
  status_filter: PromotionStatus | "";
  listing_id: string;
  user_id: string;
  promotion_package_id: string;
};

type PackageFormState = {
  title: string;
  description: string;
  inputLanguage: SupportedLanguage;
  duration_days: string;
  price: string;
  currency: string;
  is_active: boolean;
};

type SupportedLanguage = "en" | "ru";

type I18nSearchResponse = {
  items: { id: number; text_key: string; language: string }[];
};

const initialFilters: PromotionFilters = {
  status_filter: "",
  listing_id: "",
  user_id: "",
  promotion_package_id: "",
};

const initialPackageForm: PackageFormState = {
  title: "",
  description: "",
  inputLanguage: "en",
  duration_days: "7",
  price: "0.00",
  currency: "KGS",
  is_active: true,
};

const promotionStatusValues: PromotionStatus[] = ["pending", "active", "expired", "cancelled"];

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

function parsePromotionStatus(value: string | null): PromotionStatus | "" {
  if (value === null) {
    return "";
  }

  return promotionStatusValues.includes(value as PromotionStatus) ? (value as PromotionStatus) : "";
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

function readPromotionFiltersFromSearchParams(searchParams: URLSearchParams): PromotionFilters {
  return {
    status_filter: parsePromotionStatus(searchParams.get("status_filter")),
    listing_id: searchParams.get("listing_id") ?? "",
    user_id: searchParams.get("user_id") ?? "",
    promotion_package_id: searchParams.get("promotion_package_id") ?? "",
  };
}

function arePromotionFiltersEqual(left: PromotionFilters, right: PromotionFilters): boolean {
  return (
    left.status_filter === right.status_filter &&
    left.listing_id === right.listing_id &&
    left.user_id === right.user_id &&
    left.promotion_package_id === right.promotion_package_id
  );
}

function buildPromotionSearchParams(filters: PromotionFilters, page: number): URLSearchParams {
  const params = new URLSearchParams();

  if (page > 1) {
    params.set("page", String(page));
  }

  if (filters.status_filter) {
    params.set("status_filter", filters.status_filter);
  }

  const listingId = parsePositiveInt(filters.listing_id);
  if (listingId !== null) {
    params.set("listing_id", String(listingId));
  }

  const userId = parsePositiveInt(filters.user_id);
  if (userId !== null) {
    params.set("user_id", String(userId));
  }

  const packageId = parsePositiveInt(filters.promotion_package_id);
  if (packageId !== null) {
    params.set("promotion_package_id", String(packageId));
  }

  return params;
}

function statusLabel(status: PromotionStatus, t: (key: string, fallback: string) => string): string {
  if (status === "pending") {
    return t("status_pending", "Pending");
  }
  if (status === "active") {
    return t("status_active", "Active");
  }
  if (status === "expired") {
    return t("status_expired", "Expired");
  }
  return t("status_cancelled", "Cancelled");
}

function statusClass(status: PromotionStatus): string {
  if (status === "active") {
    return "users-status-active";
  }
  if (status === "pending") {
    return "users-status-pending_verification";
  }
  if (status === "expired") {
    return "users-status-deactivated";
  }
  return "users-status-blocked";
}

export function PromotionsPage() {
  const { authFetch, canManageAdministration } = useAuth();
  const { t, language } = usePageI18n("promotions");
  const defaultInputLanguage: SupportedLanguage = language === "ru" ? "ru" : "en";
  const [searchParams, setSearchParams] = useSearchParams();

  const [packages, setPackages] = useState<PromotionPackageItem[]>([]);
  const [isPackagesLoading, setIsPackagesLoading] = useState(true);
  const [packagesError, setPackagesError] = useState<string | null>(null);

  const [promotions, setPromotions] = useState<PromotionListResponse | null>(null);
  const [isPromotionsLoading, setIsPromotionsLoading] = useState(true);
  const [promotionsError, setPromotionsError] = useState<string | null>(null);

  const [page, setPage] = useState(() => readPageParam(searchParams.get("page")));
  const [draftFilters, setDraftFilters] = useState<PromotionFilters>(() => readPromotionFiltersFromSearchParams(searchParams));
  const [appliedFilters, setAppliedFilters] = useState<PromotionFilters>(() => readPromotionFiltersFromSearchParams(searchParams));

  const [isPackageModalOpen, setIsPackageModalOpen] = useState(false);
  const [editingPackage, setEditingPackage] = useState<PromotionPackageItem | null>(null);
  const [packageForm, setPackageForm] = useState<PackageFormState>(initialPackageForm);
  const [packageFormError, setPackageFormError] = useState<string | null>(null);
  const [isPackageSaving, setIsPackageSaving] = useState(false);

  const [busyPackageId, setBusyPackageId] = useState<number | null>(null);
  const [busyPromotionId, setBusyPromotionId] = useState<number | null>(null);

  useEffect(() => {
    const queryFilters = readPromotionFiltersFromSearchParams(searchParams);
    const queryPage = readPageParam(searchParams.get("page"));

    setDraftFilters((previous) => (arePromotionFiltersEqual(previous, queryFilters) ? previous : queryFilters));
    setAppliedFilters((previous) => (arePromotionFiltersEqual(previous, queryFilters) ? previous : queryFilters));
    setPage((previous) => (previous === queryPage ? previous : queryPage));
  }, [searchParams]);

  const loadPackages = useCallback(async () => {
    setIsPackagesLoading(true);
    setPackagesError(null);

    try {
      const response = await authFetch("/promotions/packages/admin");
      if (!response.ok) {
        let message = t("error_load_packages", "Failed to load promotion packages");
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = t("error_load_packages", "Failed to load promotion packages");
        }
        throw new Error(message);
      }

      const payload = (await response.json()) as PromotionPackageListResponse;
      setPackages(payload.items ?? []);
    } catch (error) {
      setPackagesError(extractErrorMessage(error, t("error_load_packages", "Failed to load promotion packages")));
    } finally {
      setIsPackagesLoading(false);
    }
  }, [authFetch, t]);

  const loadPromotions = useCallback(async () => {
    setIsPromotionsLoading(true);
    setPromotionsError(null);

    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", "20");

      if (appliedFilters.status_filter) {
        params.set("status_filter", appliedFilters.status_filter);
      }

      const listingId = parsePositiveInt(appliedFilters.listing_id);
      if (listingId !== null) {
        params.set("listing_id", String(listingId));
      }

      const userId = parsePositiveInt(appliedFilters.user_id);
      if (userId !== null) {
        params.set("user_id", String(userId));
      }

      const packageId = parsePositiveInt(appliedFilters.promotion_package_id);
      if (packageId !== null) {
        params.set("promotion_package_id", String(packageId));
      }

      const response = await authFetch(`/promotions/admin?${params.toString()}`);
      if (!response.ok) {
        let message = t("error_load_promotions", "Failed to load promotions");
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = t("error_load_promotions", "Failed to load promotions");
        }
        throw new Error(message);
      }

      const payload = (await response.json()) as PromotionListResponse;
      setPromotions(payload);
    } catch (error) {
      setPromotionsError(extractErrorMessage(error, t("error_load_promotions", "Failed to load promotions")));
    } finally {
      setIsPromotionsLoading(false);
    }
  }, [appliedFilters, authFetch, page, t]);

  useEffect(() => {
    void loadPackages();
  }, [loadPackages]);

  useEffect(() => {
    void loadPromotions();
  }, [loadPromotions]);

  const onApplyFilters = () => {
    const nextFilters: PromotionFilters = {
      status_filter: draftFilters.status_filter,
      listing_id: draftFilters.listing_id.trim(),
      user_id: draftFilters.user_id.trim(),
      promotion_package_id: draftFilters.promotion_package_id.trim(),
    };

    setPage(1);
    setAppliedFilters(nextFilters);
    setSearchParams(buildPromotionSearchParams(nextFilters, 1), { replace: true });
  };

  const onResetFilters = () => {
    setDraftFilters(initialFilters);
    setAppliedFilters(initialFilters);
    setPage(1);
    setSearchParams(new URLSearchParams(), { replace: true });
  };

  const openCreatePackageModal = () => {
    if (!canManageAdministration) {
      setPackagesError(t("access_denied_admin_management", "Access denied: admin or superadmin role required"));
      return;
    }

    setEditingPackage(null);
    setPackageForm({
      ...initialPackageForm,
      inputLanguage: defaultInputLanguage,
      currency: "KGS",
      price: "0.00",
      duration_days: "7",
    });
    setPackageFormError(null);
    setIsPackageModalOpen(true);
  };

  const openEditPackageModal = (item: PromotionPackageItem) => {
    if (!canManageAdministration) {
      setPackagesError(t("access_denied_admin_management", "Access denied: admin or superadmin role required"));
      return;
    }

    setEditingPackage(item);
    setPackageForm({
      title: item.title,
      description: item.description ?? "",
      inputLanguage: defaultInputLanguage,
      duration_days: String(item.duration_days),
      price: typeof item.price === "string" ? item.price : String(item.price),
      currency: item.currency,
      is_active: item.is_active,
    });
    setPackageFormError(null);
    setIsPackageModalOpen(true);
  };

  const savePackage = async () => {
    if (!canManageAdministration) {
      setPackageFormError(t("access_denied_admin_management", "Access denied: admin or superadmin role required"));
      return;
    }

    const trimmedTitle = packageForm.title.trim();
    const durationDays = Number.parseInt(packageForm.duration_days, 10);
    const price = Number(packageForm.price);
    const currency = packageForm.currency.trim().toUpperCase();

    if (trimmedTitle.length < 2) {
      setPackageFormError(t("error_title_required", "Title must contain at least 2 characters"));
      return;
    }
    if (!Number.isFinite(durationDays) || durationDays <= 0) {
      setPackageFormError(t("error_duration_invalid", "Duration must be greater than 0"));
      return;
    }
    if (!Number.isFinite(price) || price <= 0) {
      setPackageFormError(t("error_price_invalid", "Price must be greater than 0"));
      return;
    }
    if (currency.length < 3) {
      setPackageFormError(t("error_currency_invalid", "Currency code must have at least 3 characters"));
      return;
    }

    setIsPackageSaving(true);
    setPackageFormError(null);

    const upsertLocalizationEntry = async (
      pageKey: "promotions",
      textKey: string,
      languageCode: SupportedLanguage,
      textValue: string,
    ) => {
      const params = new URLSearchParams({
        page_key: pageKey,
        language: languageCode,
        q: textKey,
        page_size: "100",
        include_inactive: "true",
      });

      const searchResponse = await authFetch(`/i18n/admin/entries?${params.toString()}`);
      if (!searchResponse.ok) {
        throw new Error("Failed to search localization entries");
      }

      const searchPayload = (await searchResponse.json()) as I18nSearchResponse;
      const existing = searchPayload.items.find((item) => item.text_key === textKey && item.language === languageCode);

      if (existing) {
        const patchResponse = await authFetch(`/i18n/admin/entries/${existing.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text_value: textValue,
            is_active: true,
          }),
        });

        if (!patchResponse.ok) {
          throw new Error("Failed to update localization entry");
        }
        return;
      }

      const createResponse = await authFetch("/i18n/admin/entries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          page_key: pageKey,
          text_key: textKey,
          language: languageCode,
          text_value: textValue,
          is_active: true,
        }),
      });

      if (!createResponse.ok) {
        throw new Error("Failed to create localization entry");
      }
    };

    const syncPromotionLocalizationFromSource = async (
      packageId: number,
      sourceLanguage: SupportedLanguage,
      titleValue: string,
      descriptionValue: string | null,
    ) => {
      await upsertLocalizationEntry("promotions", `package_${packageId}_title`, sourceLanguage, titleValue);
      if (descriptionValue && descriptionValue.trim()) {
        await upsertLocalizationEntry("promotions", `package_${packageId}_description`, sourceLanguage, descriptionValue.trim());
      }
    };

    try {
      const payload = {
        title: trimmedTitle,
        description: packageForm.description.trim() || null,
        duration_days: durationDays,
        price: price.toFixed(2),
        currency,
        is_active: packageForm.is_active,
      };

      const isEdit = editingPackage !== null;
      const path = isEdit ? `/promotions/packages/admin/${editingPackage.id}` : "/promotions/packages/admin";
      const method = isEdit ? "PATCH" : "POST";

      const response = await authFetch(path, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        let message = t("error_save_package", "Failed to save promotion package");
        try {
          const errorPayload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof errorPayload?.error?.message === "string") {
            message = errorPayload.error.message;
          } else if (typeof errorPayload?.detail === "string") {
            message = errorPayload.detail;
          }
        } catch {
          message = t("error_save_package", "Failed to save promotion package");
        }
        throw new Error(message);
      }

      const savedPackage = (await response.json()) as PromotionPackageItem;

      if (!isEdit) {
        try {
          await syncPromotionLocalizationFromSource(
            savedPackage.id,
            packageForm.inputLanguage,
            payload.title,
            payload.description,
          );
        } catch {
          setPackagesError(t("warning_created_without_localization", "Package created, but source-language localization entries were not fully saved"));
        }
      }

      setIsPackageModalOpen(false);
      setEditingPackage(null);
      await loadPackages();
    } catch (error) {
      setPackageFormError(extractErrorMessage(error, t("error_save_package", "Failed to save promotion package")));
    } finally {
      setIsPackageSaving(false);
    }
  };

  const togglePackageActive = async (item: PromotionPackageItem) => {
    if (!canManageAdministration) {
      setPackagesError(t("access_denied_admin_management", "Access denied: admin or superadmin role required"));
      return;
    }

    setBusyPackageId(item.id);
    setPackagesError(null);

    try {
      const response = await authFetch(`/promotions/packages/admin/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !item.is_active }),
      });

      if (!response.ok) {
        let message = t("error_toggle_package", "Failed to update package status");
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = t("error_toggle_package", "Failed to update package status");
        }
        throw new Error(message);
      }

      await loadPackages();
    } catch (error) {
      setPackagesError(extractErrorMessage(error, t("error_toggle_package", "Failed to update package status")));
    } finally {
      setBusyPackageId(null);
    }
  };

  const deactivatePromotion = async (item: PromotionItem) => {
    if (!canManageAdministration) {
      setPromotionsError(t("access_denied_admin_management", "Access denied: admin or superadmin role required"));
      return;
    }

    const confirmed = window.confirm(t("confirm_deactivate_promotion", "Deactivate this promotion?"));
    if (!confirmed) {
      return;
    }

    const reasonInput = window.prompt(t("deactivate_reason_optional", "Reason (optional):"), "");
    const reason = typeof reasonInput === "string" && reasonInput.trim() ? reasonInput.trim() : null;

    setBusyPromotionId(item.id);
    setPromotionsError(null);

    try {
      const response = await authFetch(`/promotions/admin/${item.id}/deactivate`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      });

      if (!response.ok) {
        let message = t("error_deactivate_promotion", "Failed to deactivate promotion");
        try {
          const payload = (await response.json()) as { error?: { message?: string }; detail?: unknown };
          if (typeof payload?.error?.message === "string") {
            message = payload.error.message;
          } else if (typeof payload?.detail === "string") {
            message = payload.detail;
          }
        } catch {
          message = t("error_deactivate_promotion", "Failed to deactivate promotion");
        }
        throw new Error(message);
      }

      await loadPromotions();
    } catch (error) {
      setPromotionsError(extractErrorMessage(error, t("error_deactivate_promotion", "Failed to deactivate promotion")));
    } finally {
      setBusyPromotionId(null);
    }
  };

  const promotionRows = promotions?.items ?? [];
  const promotionTotalPages = promotions?.total_pages ?? 0;
  const canPromotionPrev = page > 1;
  const canPromotionNext = promotionTotalPages > 0 && page < promotionTotalPages;

  const promotionSummary = useMemo(() => {
    if (!promotions) {
      return "-";
    }
    if (promotions.total_items === 0) {
      return t("no_promotions_found", "No promotions found");
    }

    const from = (promotions.page - 1) * promotions.page_size + 1;
    const to = Math.min(promotions.page * promotions.page_size, promotions.total_items);
    return `${formatInteger(from, language)}-${formatInteger(to, language)} ${t("of", "of")} ${formatInteger(promotions.total_items, language)}`;
  }, [language, promotions, t]);

  return (
    <section className="module-page">
      <header className="module-header">
        <div>
          <h1>{t("title", "Promotions and subscriptions")}</h1>
          <p>{t("subtitle", "Manage promotion packages, monitor activation windows, and control subscription visibility.")}</p>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => {
            void loadPackages();
            void loadPromotions();
          }}
          disabled={isPackagesLoading || isPromotionsLoading}
        >
          {isPackagesLoading || isPromotionsLoading ? t("refreshing", "Refreshing...") : t("refresh", "Refresh")}
        </button>
      </header>

      {packagesError ? <div className="dashboard-error">{packagesError}</div> : null}
      {promotionsError ? <div className="dashboard-error">{promotionsError}</div> : null}

      <section className="search-strip promotions-search-strip" aria-label={t("filters", "Filters") }>
        <select
          className="users-filter-select"
          value={draftFilters.status_filter}
          onChange={(event) => setDraftFilters((prev) => ({ ...prev, status_filter: event.target.value as PromotionStatus | "" }))}
        >
          <option value="">{t("all_statuses", "All statuses")}</option>
          <option value="pending">{t("status_pending", "Pending")}</option>
          <option value="active">{t("status_active", "Active")}</option>
          <option value="expired">{t("status_expired", "Expired")}</option>
          <option value="cancelled">{t("status_cancelled", "Cancelled")}</option>
        </select>

        <input
          placeholder={t("listing_id", "Listing ID")}
          value={draftFilters.listing_id}
          onChange={(event) => setDraftFilters((prev) => ({ ...prev, listing_id: event.target.value }))}
          inputMode="numeric"
        />

        <input
          placeholder={t("user_id", "User ID")}
          value={draftFilters.user_id}
          onChange={(event) => setDraftFilters((prev) => ({ ...prev, user_id: event.target.value }))}
          inputMode="numeric"
        />

        <input
          placeholder={t("package_id", "Package ID")}
          value={draftFilters.promotion_package_id}
          onChange={(event) => setDraftFilters((prev) => ({ ...prev, promotion_package_id: event.target.value }))}
          inputMode="numeric"
        />

        <button type="button" className="btn btn-ghost" onClick={onResetFilters}>
          {t("reset", "Reset")}
        </button>
        <button type="button" className="btn btn-primary" onClick={onApplyFilters}>
          {t("apply_filters", "Apply filters")}
        </button>
      </section>

      <section className="table-card" aria-label={t("packages_table", "Promotion packages table") }>
        <div className="table-head users-table-head">
          <strong>{t("packages", "Promotion packages")}</strong>
          <div className="users-actions-cell">
            <span>{formatInteger(packages.length, language)} {t("total", "total")}</span>
            {canManageAdministration ? (
              <button type="button" className="btn btn-primary" onClick={openCreatePackageModal}>
                {t("create_package", "Create package")}
              </button>
            ) : null}
          </div>
        </div>

        <div className="promotions-table-wrap">
          <table className="promotions-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>{t("title_label", "Title")}</th>
                <th>{t("duration", "Duration")}</th>
                <th>{t("price", "Price")}</th>
                <th>{t("status", "Status")}</th>
                <th>{t("created", "Created")}</th>
                <th>{t("actions", "Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {packages.length === 0 ? (
                <tr>
                  <td colSpan={7} className="users-empty-cell">
                    {isPackagesLoading ? t("loading_packages", "Loading packages...") : t("no_packages_found", "No packages found")}
                  </td>
                </tr>
              ) : (
                packages.map((item) => (
                  <tr key={item.id}>
                    <td>#{formatInteger(item.id, language)}</td>
                    <td>
                      <div className="users-name-cell">
                        <strong>{item.title}</strong>
                        <span>{item.description ?? "-"}</span>
                      </div>
                    </td>
                    <td>{formatInteger(item.duration_days, language)} {t("days", "days")}</td>
                    <td>{formatCurrency(item.price, item.currency, language)}</td>
                    <td>
                      <span className={`users-status-badge ${item.is_active ? "users-status-active" : "users-status-deactivated"}`}>
                        {item.is_active ? t("package_active", "Active") : t("package_inactive", "Inactive")}
                      </span>
                    </td>
                    <td>{formatDateTime(item.created_at, language)}</td>
                    <td>
                      {canManageAdministration ? (
                        <div className="users-actions-cell">
                          <button type="button" className="btn btn-ghost" onClick={() => openEditPackageModal(item)}>
                            {t("edit", "Edit")}
                          </button>
                          <button
                            type="button"
                            className="btn btn-ghost"
                            disabled={busyPackageId === item.id}
                            onClick={() => void togglePackageActive(item)}
                          >
                            {busyPackageId === item.id
                              ? t("processing", "Processing...")
                              : item.is_active
                                ? t("deactivate", "Deactivate")
                                : t("activate", "Activate")}
                          </button>
                        </div>
                      ) : "-"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="table-card" aria-label={t("promotions_table", "Promotions table") }>
        <div className="table-head users-table-head">
          <strong>{t("promotions", "Promotions")}</strong>
          <span>{promotionSummary}</span>
        </div>

        <div className="promotions-table-wrap">
          <table className="promotions-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>{t("listing", "Listing")}</th>
                <th>{t("user", "User")}</th>
                <th>{t("package", "Package")}</th>
                <th>{t("target", "Target")}</th>
                <th>{t("status", "Status")}</th>
                <th>{t("window", "Window")}</th>
                <th>{t("price", "Price")}</th>
                <th>{t("created", "Created")}</th>
                <th>{t("actions", "Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {promotionRows.length === 0 ? (
                <tr>
                  <td colSpan={10} className="users-empty-cell">
                    {isPromotionsLoading ? t("loading_promotions", "Loading promotions...") : t("no_promotions_found", "No promotions found")}
                  </td>
                </tr>
              ) : (
                promotionRows.map((item) => (
                  <tr key={item.id}>
                    <td>#{formatInteger(item.id, language)}</td>
                    <td>{formatInteger(item.listing_id, language)}</td>
                    <td>{formatInteger(item.user_id, language)}</td>
                    <td>{formatInteger(item.promotion_package_id, language)}</td>
                    <td>
                      <div className="users-name-cell">
                        <strong>{item.target_city ?? t("all_cities", "All cities")}</strong>
                        <span>
                          {item.target_category_id === null
                            ? t("all_categories", "All categories")
                            : `${t("category_id", "Category ID")}: ${formatInteger(item.target_category_id, language)}`}
                        </span>
                      </div>
                    </td>
                    <td>
                      <span className={`users-status-badge ${statusClass(item.status)}`}>
                        {statusLabel(item.status, t)}
                      </span>
                    </td>
                    <td>
                      <div className="users-name-cell">
                        <strong>{formatDateTime(item.starts_at, language)}</strong>
                        <span>{formatDateTime(item.ends_at, language)}</span>
                      </div>
                    </td>
                    <td>{formatCurrency(item.purchased_price, item.currency, language)}</td>
                    <td>{formatDateTime(item.created_at, language)}</td>
                    <td>
                      {canManageAdministration ? (
                        <button
                          type="button"
                          className="btn btn-ghost"
                          disabled={
                            busyPromotionId === item.id ||
                            item.status === "cancelled" ||
                            item.status === "expired"
                          }
                          onClick={() => void deactivatePromotion(item)}
                        >
                          {busyPromotionId === item.id ? t("processing", "Processing...") : t("deactivate", "Deactivate")}
                        </button>
                      ) : "-"}
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
            disabled={!canPromotionPrev}
            onClick={() => {
              const nextPage = Math.max(1, page - 1);
              setPage(nextPage);
              setSearchParams(buildPromotionSearchParams(appliedFilters, nextPage), { replace: true });
            }}
          >
            {t("previous", "Previous")}
          </button>
          <span className="users-page-indicator">
            {t("page", "Page")} {formatInteger(promotions?.page ?? page, language)}{promotionTotalPages ? ` / ${formatInteger(promotionTotalPages, language)}` : ""}
          </span>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={!canPromotionNext}
            onClick={() => {
              const nextPage = page + 1;
              setPage(nextPage);
              setSearchParams(buildPromotionSearchParams(appliedFilters, nextPage), { replace: true });
            }}
          >
            {t("next", "Next")}
          </button>
        </div>
      </section>

      <Modal
        open={isPackageModalOpen}
        onClose={() => {
          setIsPackageModalOpen(false);
          setEditingPackage(null);
        }}
        title={editingPackage ? t("edit_package", "Edit package") : t("create_package", "Create package")}
        subtitle={editingPackage ? `${t("package", "Package")} #${formatInteger(editingPackage.id, language)}` : t("new_package", "New package")}
      >
        <div className="users-detail-body">
          {packageFormError ? <div className="dashboard-error">{packageFormError}</div> : null}

          <form
            className="promotions-form"
            onSubmit={(event) => {
              event.preventDefault();
              void savePackage();
            }}
          >
            <div className="promotions-form-grid">
              <label>
                {t("title_label", "Title")}
                <input
                  value={packageForm.title}
                  onChange={(event) => setPackageForm((prev) => ({ ...prev, title: event.target.value }))}
                  maxLength={120}
                  required
                />
              </label>

              {!editingPackage ? (
                <label>
                  {t("input_language", "Input language")}
                  <select
                    className="users-filter-select"
                    value={packageForm.inputLanguage}
                    onChange={(event) => setPackageForm((prev) => ({
                      ...prev,
                      inputLanguage: event.target.value as SupportedLanguage,
                    }))}
                  >
                    <option value="en">{t("language_english", "English")}</option>
                    <option value="ru">{t("language_russian", "Русский")}</option>
                  </select>
                </label>
              ) : null}

              <label>
                {t("currency", "Currency")}
                <input
                  value={packageForm.currency}
                  onChange={(event) => setPackageForm((prev) => ({ ...prev, currency: event.target.value }))}
                  maxLength={10}
                  required
                />
              </label>

              <label>
                {t("duration_days", "Duration days")}
                <input
                  value={packageForm.duration_days}
                  onChange={(event) => setPackageForm((prev) => ({ ...prev, duration_days: event.target.value }))}
                  inputMode="numeric"
                  required
                />
              </label>

              <label>
                {t("price", "Price")}
                <input
                  value={packageForm.price}
                  onChange={(event) => setPackageForm((prev) => ({ ...prev, price: event.target.value }))}
                  inputMode="decimal"
                  required
                />
              </label>
            </div>

            <label className="promotions-textarea-field">
              {t("description", "Description")}
              <textarea
                value={packageForm.description}
                onChange={(event) => setPackageForm((prev) => ({ ...prev, description: event.target.value }))}
                maxLength={2000}
              />
            </label>

            <label className="categories-checkbox-label">
              <input
                type="checkbox"
                checked={packageForm.is_active}
                onChange={(event) => setPackageForm((prev) => ({ ...prev, is_active: event.target.checked }))}
              />
              {t("package_active", "Active")}
            </label>

            <div className="users-actions-cell">
              <button type="submit" className="btn btn-primary" disabled={isPackageSaving}>
                {isPackageSaving ? t("saving", "Saving...") : editingPackage ? t("save_changes", "Save changes") : t("create", "Create")}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => {
                  if (editingPackage) {
                    openEditPackageModal(editingPackage);
                  } else {
                    setPackageForm({ ...initialPackageForm, inputLanguage: defaultInputLanguage });
                  }
                }}
              >
                {t("reset", "Reset")}
              </button>
            </div>
          </form>
        </div>
      </Modal>
    </section>
  );
}
