interface ComparisonBarItem {
  label: string;
  value: number;
  display: string;
  tone?: "cyan" | "green" | "amber" | "red";
}

interface ComparisonBarsProps {
  items: ComparisonBarItem[];
}

export function ComparisonBars({ items }: ComparisonBarsProps) {
  const max = Math.max(...items.map((item) => Math.abs(item.value)), 1e-9);
  return (
    <div className="comparison-bars">
      {items.map((item) => (
        <div className="comparison-bar-row" key={item.label}>
          <div className="comparison-bar-label"><span>{item.label}</span><strong>{item.display}</strong></div>
          <div className="comparison-bar-track">
            <i className={`comparison-bar-fill comparison-bar-fill--${item.tone ?? "cyan"}`} style={{ width: `${Math.max(1.5, 100 * Math.abs(item.value) / max)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}
