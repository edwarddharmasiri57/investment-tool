const REGIME_CLASS = {
  "Risk-On": "regime-on",
  "Risk-Off": "regime-off",
  "Elevated-Volatility": "regime-elevated",
};

export default function RegimeBanner({ regime }) {
  if (!regime) return null;
  const cls = REGIME_CLASS[regime.regime] || "regime-unknown";
  return (
    <div className={`regime-banner ${cls}`} title={regime.reason}>
      <span className="regime-label">{regime.regime}</span>
      <span className="regime-detail">
        VIX {regime.vix ?? "—"} · 10y-2y {regime.ten_minus_two_spread_pp != null ? `${regime.ten_minus_two_spread_pp > 0 ? "+" : ""}${regime.ten_minus_two_spread_pp}pp` : "—"}
      </span>
    </div>
  );
}
