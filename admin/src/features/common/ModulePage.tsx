import type { ReactNode } from "react";

type ModulePageProps = {
  title: string;
  subtitle: string;
  actions?: ReactNode;
};

export function ModulePage({ title, subtitle, actions }: ModulePageProps) {
  return (
    <section className="module-page">
      <header className="module-header">
        <div>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        {actions ? <div className="module-actions">{actions}</div> : null}
      </header>

      <div className="search-strip">
        <input placeholder="Search" aria-label="Search" />
        <button type="button" className="btn btn-ghost">Filters</button>
        <button type="button" className="btn btn-primary">Search</button>
      </div>

      <section className="table-card" aria-label={`${title} table`}>
        <div className="table-head">
          <strong>Data</strong>
          <span>Pending actions and records</span>
        </div>
        <div className="table-placeholder">
          <div className="row" />
          <div className="row" />
          <div className="row" />
        </div>
        <div className="table-footer">
          <button type="button" className="btn btn-ghost">Previous</button>
          <button type="button" className="btn btn-ghost">Next</button>
        </div>
      </section>
    </section>
  );
}
