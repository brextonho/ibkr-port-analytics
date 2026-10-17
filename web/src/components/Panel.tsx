import type { ReactNode } from "react";

export function Panel({
  title,
  children,
  height,
  actions,
}: {
  title?: string;
  children: ReactNode;
  height?: number;
  actions?: ReactNode;
}) {
  return (
    <section className="panel">
      {actions ? (
        <div className="panel-head">
          <h2 className="panel-title">{title}</h2>
          {actions}
        </div>
      ) : (
        title && <h2 className="panel-title">{title}</h2>
      )}
      <div style={height ? { height, position: "relative" } : undefined}>
        {children}
      </div>
    </section>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="empty-state">{children}</p>;
}

export function LoadingOrError({
  loading,
  error,
}: {
  loading: boolean;
  error: string | null;
}) {
  if (loading) return <p className="empty-state">Loading…</p>;
  if (error) return <p className="empty-state">Failed to load: {error}</p>;
  return null;
}
