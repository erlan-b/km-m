import { Link } from "react-router-dom";

export function DashboardPage() {
  return (
    <section className="module-page">
      <header className="module-header">
        <div>
          <h1>Dashboard</h1>
          <p>Operational overview and moderation shortcuts.</p>
        </div>
      </header>

      <div className="kpi-grid">
        <article>
          <h3>Total Users</h3>
          <strong>--</strong>
        </article>
        <article>
          <h3>Pending Listings</h3>
          <strong>--</strong>
        </article>
        <article>
          <h3>Open Reports</h3>
          <strong>--</strong>
        </article>
        <article>
          <h3>Active Promotions</h3>
          <strong>--</strong>
        </article>
      </div>

      <section className="quick-actions">
        <h2>Quick actions</h2>
        <div>
          <Link className="btn btn-primary" to="/listings">Review listings</Link>
          <Link className="btn btn-ghost" to="/reports">Open reports queue</Link>
          <Link className="btn btn-ghost" to="/users">Manage users</Link>
        </div>
      </section>
    </section>
  );
}
