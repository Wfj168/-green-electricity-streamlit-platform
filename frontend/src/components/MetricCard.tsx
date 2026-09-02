import type { ReactNode } from "react";

interface MetricCardProps {
  label: string;
  value?: string;
  unit?: string;
  meta?: string;
  tone?: "cyan" | "green" | "amber" | "red";
  icon: ReactNode;
}

export function MetricCard({
  label,
  value = "--",
  unit = "",
  meta = "尚未接入",
  tone = "cyan",
  icon,
}: MetricCardProps) {
  return (
    <article className={`metric-card metric-card--${tone}`}>
      <div className="metric-icon">{icon}</div>
      <div className="metric-content">
        <span className="metric-label">{label}</span>
        <div className="metric-value"><strong>{value}</strong><span>{unit}</span></div>
        <div className="metric-meta"><span>{meta}</span></div>
      </div>
    </article>
  );
}
