// Pure presentational SVG sparkline — no library, no axes, no labels (D-15, D-16).
//
// Each ticker's price array (capped at 100, FIFO) is mapped to a polyline within
// the configured viewport. Line color is green if the latest price is at or above
// the first price in the window, red otherwise. Range defaults guard against a
// flat-line divide-by-zero on the very first ticks.
//
// No 'use client' directive: this component holds no state and reads no hooks.
// It's safe to render inside any 'use client' parent (WatchlistRow imports it).

interface SparklineProps {
  prices: number[];
  width?: number;
  height?: number;
}

export function Sparkline({ prices, width = 80, height = 30 }: SparklineProps) {
  if (prices.length < 2) {
    return <svg width={width} height={height} />;
  }

  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1; // avoid div-by-zero on a flat-line window
  const pts = prices
    .map((p, i) => {
      const x = (i / (prices.length - 1)) * width;
      const y = height - ((p - min) / range) * height;
      return `${x},${y}`;
    })
    .join(" ");

  const isUp = prices[prices.length - 1] >= prices[0];
  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline
        points={pts}
        fill="none"
        stroke={isUp ? "#26a641" : "#f85149"}
        strokeWidth={1.5}
      />
    </svg>
  );
}
