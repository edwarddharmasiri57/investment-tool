import { LineChart, Line, ResponsiveContainer } from "recharts";

export default function Sparkline({ data, dataKey = "value", height = 32, width = 100 }) {
  if (!data || data.length < 2) return <span className="hud-label">—</span>;
  return (
    <div style={{ width, height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <Line
            type="monotone"
            dataKey={dataKey}
            stroke="var(--accent-cyan)"
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
