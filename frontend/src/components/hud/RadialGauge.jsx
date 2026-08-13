import { motion } from "framer-motion";

const SIZE = 220;
const STROKE = 10;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export default function RadialGauge({ value, label = "PORTFOLIO HEALTH", sublabel, statusClass = "" }) {
  const clamped = Math.max(0, Math.min(100, value ?? 0));
  const offset = CIRCUMFERENCE * (1 - clamped / 100);

  return (
    <div className="radial-gauge" style={{ width: SIZE, height: SIZE }}>
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
        <circle cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} fill="none" stroke="var(--border-glow)" strokeWidth={STROKE} />
        <motion.circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke="var(--accent-cyan)"
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          initial={{ strokeDashoffset: CIRCUMFERENCE }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.2, ease: "easeOut" }}
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
          style={{ filter: "drop-shadow(0 0 6px var(--accent-cyan))" }}
        />
      </svg>
      <div className="radial-gauge-center">
        <div className={`radial-gauge-value ${statusClass}`}>{Math.round(clamped)}</div>
        <div className="hud-label">{label}</div>
        {sublabel && <div className="radial-gauge-sublabel">{sublabel}</div>}
      </div>
    </div>
  );
}
