import { Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { AdminSidebar } from "./AdminSidebar";

export function AdminLayout() {
  const { email, logout } = useAuth();

  return (
    <div className="admin-shell">
      <AdminSidebar />
      <div className="admin-main">
        <header className="admin-topbar">
          <div>
            <h2>Operations Console</h2>
            <p>Moderation-first admin workspace</p>
          </div>
          <div className="topbar-actions">
            <span>{email}</span>
            <button type="button" className="btn btn-ghost" onClick={() => void logout()}>
              Log out
            </button>
          </div>
        </header>
        <main className="admin-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
