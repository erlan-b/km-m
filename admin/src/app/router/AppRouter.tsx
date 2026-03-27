import { Navigate, Route, Routes } from "react-router-dom";

import { ProtectedRoute } from "../auth/ProtectedRoute";
import { AdminLayout } from "../layout/AdminLayout";
import { LoginPage } from "../../features/auth/LoginPage";
import { DashboardPage } from "../../features/dashboard/DashboardPage";
import { ModulePage } from "../../features/common/ModulePage";

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AdminLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/users" element={<ModulePage title="Users" subtitle="Search users, inspect profile, suspend and unsuspend." />} />
          <Route path="/listings" element={<ModulePage title="Listings Moderation" subtitle="Moderation queue with approve, reject and archive actions." />} />
          <Route path="/reports" element={<ModulePage title="Reports" subtitle="Review reports, inspect targets and resolve or dismiss." />} />
          <Route path="/categories" element={<ModulePage title="Categories" subtitle="Manage taxonomy, ordering and dynamic attributes." />} />
          <Route path="/payments" element={<ModulePage title="Payments" subtitle="Track provider status, users, listing links and timeline." />} />
          <Route path="/promotions" element={<ModulePage title="Promotions" subtitle="Monitor active and expired promotions, package controls." />} />
          <Route path="/localization" element={<ModulePage title="Localization" subtitle="Manage language entries and publication status." />} />
          <Route path="/audit-logs" element={<ModulePage title="Audit Logs" subtitle="Trace moderation actions and operational changes." />} />
        </Route>
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
