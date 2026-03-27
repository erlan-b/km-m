import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/users", label: "Users" },
  { to: "/listings", label: "Listings Moderation" },
  { to: "/reports", label: "Reports" },
  { to: "/categories", label: "Categories" },
  { to: "/payments", label: "Payments" },
  { to: "/promotions", label: "Promotions" },
  { to: "/localization", label: "Localization" },
  { to: "/audit-logs", label: "Audit Logs" },
];

export function AdminSidebar() {
  return (
    <aside className="admin-sidebar" aria-label="Admin navigation">
      <div className="sidebar-brand">
        <span>KM</span>
        <strong>Admin</strong>
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
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
