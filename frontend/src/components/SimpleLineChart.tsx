interface ChartSeries {
  name: string;
  color: string;
  values: number[];
}

interface SimpleLineChartProps {
  series: ChartSeries[];
  unit: string;
}

const WIDTH = 900;
const HEIGHT = 250;
const PADDING = 30;

function polyline(values: number[], minimum: number, maximum: number) {
  if (!values.length) return "";
  const span = Math.max(maximum - minimum, 1e-9);
  return values
    .map((value, index) => {
      const x = PADDING + (index / Math.max(values.length - 1, 1)) * (WIDTH - 2 * PADDING);
      const y = HEIGHT - PADDING - ((value - minimum) / span) * (HEIGHT - 2 * PADDING);
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

export function SimpleLineChart({ series, unit }: SimpleLineChartProps) {
  const allValues = series.flatMap((item) => item.values).filter(Number.isFinite);
  if (!allValues.length) return <div className="empty-chart">暂无可绘制数据</div>;
  const minimum = Math.min(0, ...allValues);
  const maximum = Math.max(...allValues);
  return (
    <div className="simple-chart">
      <div className="chart-legend">
        {series.map((item) => <span key={item.name}><i style={{ background: item.color }} />{item.name}</span>)}
        <em>单位：{unit}</em>
      </div>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="时序趋势图">
        {[0, 1, 2, 3, 4].map((index) => {
          const y = PADDING + index * ((HEIGHT - 2 * PADDING) / 4);
          return <line key={index} x1={PADDING} x2={WIDTH - PADDING} y1={y} y2={y} className="chart-gridline" />;
        })}
        {series.map((item) => (
          <polyline
            key={item.name}
            points={polyline(item.values, minimum, maximum)}
            fill="none"
            stroke={item.color}
            strokeWidth="2.5"
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>
      <div className="chart-axis"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div>
    </div>
  );
}
