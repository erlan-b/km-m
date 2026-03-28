import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "./AuthContext";

export function ProtectedRoute() {
  const location = useLocation();
  const { isLoading, isAuthenticated, isAdminPanelOperator } = useAuth();

  if (isLoading) {
    return <div className="page-center">Checking session...</div>;
  }

  if (!isAuthenticated) {
    const redirect = encodeURIComponent(`${location.pathname}${location.search}`);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }

  if (!isAdminPanelOperator) {
    return <div className="page-center">Access denied: support, moderator, admin or superadmin role required.</div>;
  }

  return <Outlet />;
}
