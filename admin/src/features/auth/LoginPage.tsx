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
      <form className="auth-card" onSubmit={onSubmit}>
        <div className="auth-lang-row">
          <span>{t("language", "Language")}</span>
          <div className="language-switch" role="group" aria-label={t("language", "Language")}> 
            <button
              type="button"
              className={language === "ru" ? "btn btn-primary" : "btn btn-ghost"}
              onClick={() => setLanguage("ru")}
            >
              RU
            </button>
            <button
              type="button"
              className={language === "en" ? "btn btn-primary" : "btn btn-ghost"}
              onClick={() => setLanguage("en")}
            >
              EN
            </button>
          </div>
        </div>

        <h1>{t("title", "Admin Login")}</h1>
        <p>{t("subtitle", "Sign in to moderation and operations workspace.")}</p>

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
