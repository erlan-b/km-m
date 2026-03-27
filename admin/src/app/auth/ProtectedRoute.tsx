import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "./AuthContext";

export function ProtectedRoute() {
  const location = useLocation();
  const { isLoading, isAuthenticated, isAdminLike } = useAuth();

  if (isLoading) {
    return <div className="page-center">Checking session...</div>;
  }

  if (!isAuthenticated) {
    const redirect = encodeURIComponent(`${location.pathname}${location.search}`);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }

  if (!isAdminLike) {
    return <div className="page-center">Access denied: admin or moderator role required.</div>;
  }

  return <Outlet />;
}
