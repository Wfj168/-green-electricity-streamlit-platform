import type { PropsWithChildren, ReactNode } from "react";

interface PanelProps extends PropsWithChildren {
  title: string;
  extra?: ReactNode;
  className?: string;
}

export function Panel({ title, extra, className = "", children }: PanelProps) {
  return (
    <section className={`page-panel ${className}`}>
      <header className="panel-header"><h2>{title}</h2>{extra}</header>
      <div className="panel-body">{children}</div>
    </section>
  );
}
