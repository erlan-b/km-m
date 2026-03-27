import { Navigate, Route, Routes } from "react-router-dom";

import { ProtectedRoute } from "../auth/ProtectedRoute";
import { AdminLayout } from "../layout/AdminLayout";
import { LoginPage } from "../../features/auth/LoginPage";
import { DashboardPage } from "../../features/dashboard/DashboardPage";
import { UsersPage } from "../../features/users/UsersPage";
import { ReportsPage } from "../../features/reports/ReportsPage";
import { ListingsModerationPage } from "../../features/listings/ListingsModerationPage";
import { CategoriesPage } from "../../features/categories/CategoriesPage";
import { PaymentsPage } from "../../features/payments/PaymentsPage";
import { AuditLogsPage } from "../../features/audit/AuditLogsPage";

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
          <Route path="/categories" element={<CategoriesPage />} />
          <Route path="/payments" element={<PaymentsPage />} />
          <Route path="/audit-logs" element={<AuditLogsPage />} />
        </Route>
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
