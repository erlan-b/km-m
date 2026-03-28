import { useState, type FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { useAuth } from "../../app/auth/AuthContext";
import { useI18n, usePageI18n } from "../../app/i18n/I18nContext";

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login, isLoading, isAuthenticated } = useAuth();
  const { language, setLanguage } = useI18n();
  const { t } = usePageI18n("auth_login");
  const nextLanguage = language === "en" ? "RU" : "EN";
  const currentLanguage = language.toUpperCase();

  const toggleLanguage = () => {
    setLanguage(language === "en" ? "ru" : "en");
  };

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const redirect = searchParams.get("redirect") || "/dashboard";

  if (!isLoading && isAuthenticated) {
    return <Navigate to={redirect} replace />;
  }

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await login(email, password);
      navigate(redirect, { replace: true });
    } catch (submitError) {
      const message = submitError instanceof Error ? submitError.message : t("login_failed", "Login failed");
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-top-right-language language-switch" role="group" aria-label={t("language", "Language")}>
        <button
          type="button"
          className="btn btn-ghost language-toggle-btn auth-language-toggle"
          aria-label={t("language", "Language")}
          title={t("language", "Language")}
          onClick={toggleLanguage}
        >
          <span className="lang-current">{currentLanguage}</span>
          <span className="lang-next" aria-hidden="true">{nextLanguage}</span>
        </button>
      </div>

      <form className="auth-card" onSubmit={onSubmit}>
        <h1>{t("title", "Admin Login")}</h1>

        {error ? <div className="auth-error">{error}</div> : null}

        <label>
          {t("email", "Email")}
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="admin@example.com"
            required
          />
        </label>

        <label>
          {t("password", "Password")}
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="********"
            required
          />
        </label>

        <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
          {isSubmitting ? t("signing_in", "Signing in...") : t("sign_in", "Sign in")}
        </button>
      </form>
    </div>
  );
}
