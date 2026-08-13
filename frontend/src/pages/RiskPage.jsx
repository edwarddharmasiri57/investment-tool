import { useEffect, useMemo, useState } from "react";
import { getRisk, getFactors, getPortfolioOptimize, getPortfolioPositions } from "../api";
import { useWatchlist } from "../contexts/WatchlistContext";
import HudPanel from "../components/hud/HudPanel";
import ScanningLoader from "../components/hud/ScanningLoader";

function zoneClass(zone) {
  if (zone === "safe") return "status-good";
  if (zone === "grey") return "status-warn";
  if (zone === "distress") return "status-bad";
  return "status-na";
}

function corrColor(v) {
  if (v === null || v === undefined) return "transparent";
  if (v > 0.8) return "rgba(255, 79, 106, 0.35)";
  const intensity = Math.min(1, Math.max(0, Math.abs(v)));
  return `rgba(79, 216, 255, ${0.08 + intensity * 0.35})`;
}

export default function RiskPage() {
  const { tickers: watchlistTickers } = useWatchlist();
  const [positionTickers, setPositionTickers] = useState([]);
  const [ticker, setTicker] = useState(null);

  const [risk, setRisk] = useState(null);
  const [riskError, setRiskError] = useState("");
  const [factors, setFactors] = useState(null);
  const [factorsError, setFactorsError] = useState("");
  const [loading, setLoading] = useState(false);

  const [optimize, setOptimize] = useState(null);
  const [optimizeError, setOptimizeError] = useState("");
  const [optimizeLoading, setOptimizeLoading] = useState(true);

  const availableTickers = useMemo(
    () => Array.from(new Set([...positionTickers, ...watchlistTickers])).sort(),
    [positionTickers, watchlistTickers]
  );

  useEffect(() => {
    getPortfolioPositions()
      .then((d) => setPositionTickers((d.positions || []).map((p) => p.ticker)))
      .catch(() => {});
    getPortfolioOptimize()
      .then(setOptimize)
      .catch((e) => setOptimizeError(e.response?.data?.detail || e.message))
      .finally(() => setOptimizeLoading(false));
  }, []);

  useEffect(() => {
    if (!ticker && availableTickers.length > 0) setTicker(availableTickers[0]);
  }, [availableTickers, ticker]);

  useEffect(() => {
    if (ticker) loadTicker(ticker);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker]);

  async function loadTicker(t) {
    setLoading(true);
    setRiskError("");
    setFactorsError("");
    const [riskR, factorsR] = await Promise.allSettled([getRisk(t), getFactors(t)]);
    if (riskR.status === "fulfilled") {
      setRisk(riskR.value);
    } else {
      setRisk(null);
      setRiskError(riskR.reason.response?.data?.detail || riskR.reason.message);
    }
    if (factorsR.status === "fulfilled") {
      setFactors(factorsR.value);
    } else {
      setFactors(null);
      setFactorsError(factorsR.reason.response?.data?.detail || factorsR.reason.message);
    }
    setLoading(false);
  }

  return (
    <div className="overview-grid">
      <HudPanel title="TICKER RISK PROFILE">
        <select value={ticker || ""} onChange={(e) => setTicker(e.target.value)}>
          {availableTickers.length === 0 && <option value="">No tickers in watchlist/portfolio</option>}
          {availableTickers.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </HudPanel>

      {loading && <ScanningLoader text={`ASSESSING ${ticker}`} />}

      {!loading && (
        <div className="overview-row">
          <HudPanel title="ALTMAN Z-SCORE / PIOTROSKI F-SCORE" delay={0.05}>
            {riskError && <p className="hud-label status-bad">{riskError}</p>}
            {risk && (
              <>
                <div className="hud-metric" style={{ marginBottom: 10 }}>
                  <span className="hud-label">Altman Z-Score</span>
                  <span className={`hud-value ${zoneClass(risk.altman_z_score.zone)}`}>
                    {risk.altman_z_score.z_score ?? "—"} ({risk.altman_z_score.zone ?? "n/a"})
                  </span>
                  <span className="hud-label">safe &gt;2.99 &middot; grey 1.81-2.99 &middot; distress &lt;1.81</span>
                </div>
                <div className="hud-metric">
                  <span className="hud-label">Piotroski F-Score</span>
                  <span className="hud-value">
                    {risk.piotroski_f_score.f_score !== null ? `${risk.piotroski_f_score.f_score}/9` : "—"}
                  </span>
                  <span className="hud-label">
                    signals evaluated: {risk.piotroski_f_score.signals_evaluated}/9 &middot; higher = stronger
                    fundamentals, &le;2 often flags a value trap
                  </span>
                </div>
              </>
            )}
          </HudPanel>

          <HudPanel title="FAMA-FRENCH FACTOR EXPOSURES" delay={0.1}>
            {factorsError && <p className="hud-label status-bad">{factorsError}</p>}
            {factors && (
              <>
                <p className="hud-label" style={{ marginBottom: 8 }}>
                  R&sup2; {factors.r_squared} &middot; {factors.months_used} months ({factors.period_range})
                </p>
                <table className="screen-table">
                  <thead>
                    <tr><th>Factor</th><th>Loading</th></tr>
                  </thead>
                  <tbody>
                    {Object.entries(factors.factor_loadings).map(([k, v]) => (
                      <tr key={k}><td>{k}</td><td>{v}</td></tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </HudPanel>
        </div>
      )}

      <HudPanel title="CORRELATION MATRIX (CURRENT HOLDINGS)" delay={0.15}>
        {optimizeLoading && <ScanningLoader text="LOADING PORTFOLIO OPTIMIZER" />}
        {optimizeError && <p className="hud-label status-bad">{optimizeError}</p>}
        {optimize && (
          <>
            <div style={{ overflowX: "auto" }}>
              <table className="screen-table">
                <thead>
                  <tr>
                    <th></th>
                    {optimize.tickers.map((t) => (
                      <th key={t}>{t}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {optimize.tickers.map((t1) => (
                    <tr key={t1}>
                      <td className="hud-readout">{t1}</td>
                      {optimize.tickers.map((t2) => (
                        <td key={t2} style={{ background: corrColor(optimize.correlation_matrix[t1][t2]), textAlign: "center" }}>
                          {optimize.correlation_matrix[t1][t2]}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {optimize.high_correlation_warnings.length > 0 && (
              <p className="hud-label status-bad" style={{ marginTop: 10 }}>
                High correlation (&gt;0.8): {optimize.high_correlation_warnings.map((w) => `${w.pair.join("/")} (${w.correlation})`).join(", ")}
              </p>
            )}
          </>
        )}
      </HudPanel>

      <HudPanel title="PORTFOLIO OPTIMIZER: CURRENT vs MVO vs RISK PARITY" delay={0.2}>
        {optimize && (
          <>
            <table className="screen-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Current weight</th>
                  <th>MVO suggested</th>
                  <th>Risk parity suggested</th>
                </tr>
              </thead>
              <tbody>
                {optimize.tickers.map((t) => (
                  <tr key={t}>
                    <td className="hud-readout">{t}</td>
                    <td>{optimize.current_weights[t] !== null ? `${(optimize.current_weights[t] * 100).toFixed(1)}%` : "—"}</td>
                    <td>{(optimize.mvo.weights[t] * 100).toFixed(1)}%</td>
                    <td>{(optimize.risk_parity.weights[t] * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="hud-label" style={{ marginTop: 10 }}>
              MVO: expected return {optimize.mvo.expected_annual_return_pct}% &middot; volatility{" "}
              {optimize.mvo.expected_annual_volatility_pct}% &middot; Sharpe {optimize.mvo.sharpe_ratio}
            </p>
            <ul className="limitations-list" style={{ marginTop: 10 }}>
              {optimize.limitations.map((l, i) => (
                <li key={i}>{l}</li>
              ))}
            </ul>
          </>
        )}
      </HudPanel>
    </div>
  );
}
