import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "./AuthContext";

type Capability = "moderation" | "management";

type CapabilityRouteProps = {
  capability: Capability;
};

function capabilityMessage(capability: Capability): string {
  if (capability === "moderation") {
    return "Access denied: moderator, admin or superadmin role required.";
  }
  return "Access denied: admin or superadmin role required.";
}

export function CapabilityRoute({ capability }: CapabilityRouteProps) {
  const location = useLocation();
  const {
    isLoading,
    isAuthenticated,
    isAdminPanelOperator,
    canModerateContent,
    canManageAdministration,
  } = useAuth();

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

  const allowed = capability === "moderation" ? canModerateContent : canManageAdministration;
  if (!allowed) {
    return <div className="page-center">{capabilityMessage(capability)}</div>;
  }

  return <Outlet />;
}
