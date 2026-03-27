import { Navigate, Route, Routes } from "react-router-dom";

import { ProtectedRoute } from "../auth/ProtectedRoute";
import { AdminLayout } from "../layout/AdminLayout";
import { LoginPage } from "../../features/auth/LoginPage";
import { DashboardPage } from "../../features/dashboard/DashboardPage";
import { ModulePage } from "../../features/common/ModulePage";
import { UsersPage } from "../../features/users/UsersPage";
import { ReportsPage } from "../../features/reports/ReportsPage";
import { ListingsModerationPage } from "../../features/listings/ListingsModerationPage";

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AdminLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/users" element={<UsersPage />} />
          <Route path="/listings" element={<ListingsModerationPage />} />
          <Route path="/reports" element={<ReportsPage />} />
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
