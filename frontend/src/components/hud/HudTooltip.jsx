export default function HudTooltip({ active, payload, label, formatter }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="hud-tooltip">
      {label && <div className="hud-label" style={{ marginBottom: 4 }}>{label}</div>}
      {payload.map((p, i) => (
        <div key={i}>{formatter ? formatter(p) : `${p.name}: ${p.value}`}</div>
      ))}
    </div>
  );
}
