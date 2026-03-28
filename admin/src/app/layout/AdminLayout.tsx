import { Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { useI18n, usePageI18n } from "../i18n/I18nContext";
import { AdminSidebar } from "./AdminSidebar";

export function AdminLayout() {
  const { email, logout } = useAuth();
  const { language, setLanguage } = useI18n();
  const { t } = usePageI18n("layout");
  const nextLanguage = language === "en" ? "RU" : "EN";
  const currentLanguage = language.toUpperCase();

  const toggleLanguage = () => {
    setLanguage(language === "en" ? "ru" : "en");
  };

  return (
    <div className="admin-shell">
      <AdminSidebar />
      <div className="admin-main">
        <header className="admin-topbar">
          <div>
            <h2>{t("operations_console", "Operations Console")}</h2>
            <p>{t("workspace_subtitle", "Moderation-first admin workspace")}</p>
          </div>
          <div className="topbar-actions">
            <div className="language-switch" role="group" aria-label={t("language", "Language")}>
              <button
                type="button"
                className="btn btn-ghost language-toggle-btn"
                aria-label={t("language", "Language")}
                title={t("language", "Language")}
                onClick={toggleLanguage}
              >
                <span className="lang-current">{currentLanguage}</span>
                <span className="lang-next" aria-hidden="true">{nextLanguage}</span>
              </button>
            </div>
            <span>{email}</span>
            <button type="button" className="btn btn-ghost" onClick={() => void logout()}>
              {t("logout", "Log out")}
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
