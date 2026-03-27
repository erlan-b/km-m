import { NavLink } from "react-router-dom";

import { usePageI18n } from "../i18n/I18nContext";

const navItems = [
  { to: "/dashboard", translationKey: "nav_dashboard", fallback: "Dashboard" },
  { to: "/users", translationKey: "nav_users", fallback: "Users" },
  { to: "/listings", translationKey: "nav_listings", fallback: "Listings Moderation" },
  { to: "/reports", translationKey: "nav_reports", fallback: "Reports" },
  { to: "/categories", translationKey: "nav_categories", fallback: "Categories" },
  { to: "/payments", translationKey: "nav_payments", fallback: "Payments" },
  { to: "/audit-logs", translationKey: "nav_audit_logs", fallback: "Audit Logs" },
];

export function AdminSidebar() {
  const { t } = usePageI18n("layout");

  return (
    <aside className="admin-sidebar" aria-label="Admin navigation">
      <div className="sidebar-brand">
        <strong>{t("brand", "KM-M Admin Panel")}</strong>
      </div>

      <nav>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              isActive ? "sidebar-link sidebar-link-active" : "sidebar-link"
            }
          >
            {t(item.translationKey, item.fallback)}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
