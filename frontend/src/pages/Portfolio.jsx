import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { getPortfolioPositions, getPortfolioSummary, getPortfolioPerformance, getPortfolioOptimize } from "../api";
import { useTickerDetail } from "../contexts/TickerDetailContext";
import HudPanel from "../components/hud/HudPanel";
import ScanningLoader from "../components/hud/ScanningLoader";
import HudTooltip from "../components/hud/HudTooltip";
import LogTradeForm from "../components/LogTradeForm";

const REBALANCE_THRESHOLD_PCT = 15; // flag if any position's MVO-suggested weight differs from current by more than this many percentage points

export default function Portfolio() {
  const { openTicker } = useTickerDetail();
  const location = useLocation();
  const navigate = useNavigate();
  const highlightTicker = location.state?.ticker;

  const [positions, setPositions] = useState([]);
  const [summary, setSummary] = useState(null);
  const [performance, setPerformance] = useState(null);
  const [rebalanceFlags, setRebalanceFlags] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [positionsData, summaryData, perfData, optimizeData] = await Promise.all([
        getPortfolioPositions(),
        getPortfolioSummary(),
        getPortfolioPerformance().catch(() => null), // no trades yet -> 400, non-fatal
        getPortfolioOptimize().catch(() => null), // fewer than 2 positions -> 400, non-fatal
      ]);
      setPositions(positionsData.positions || []);
      setSummary(summaryData);
      setPerformance(perfData);

      if (optimizeData) {
        const flags = optimizeData.tickers
          .map((t) => ({
            ticker: t,
            current: (optimizeData.current_weights[t] || 0) * 100,
            suggested: optimizeData.mvo.weights[t] * 100,
          }))
          .filter((f) => Math.abs(f.suggested - f.current) > REBALANCE_THRESHOLD_PCT);
        setRebalanceFlags(flags);
      } else {
        setRebalanceFlags([]);
      }
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <ScanningLoader text="LOADING POSITIONS" />;

  return (
    <div className="overview-grid">
      {error && <p className="hud-label status-bad">{error}</p>}

      {rebalanceFlags.length > 0 && (
        <HudPanel style={{ cursor: "pointer", borderColor: "var(--accent-warn)" }} onClick={() => navigate("/risk")}>
          <p className="hud-label status-warn">
            ⚠ Optimizer suggests significant rebalancing ({rebalanceFlags.map((f) => `${f.ticker} ${f.current.toFixed(0)}%→${f.suggested.toFixed(0)}%`).join(", ")}) —
            click for detail on /risk. MVO is directional, not precise - see the full caveat there before acting.
          </p>
        </HudPanel>
      )}

      {performance && (
        <div className="overview-row">
          <HudPanel title="SHARPE" delay={0.02}>
            <span className="hud-value">{performance.sharpe_ratio ?? "—"}</span>
          </HudPanel>
          <HudPanel title="SORTINO" delay={0.04}>
            <span className="hud-value">{performance.sortino_ratio ?? "—"}</span>
          </HudPanel>
          <HudPanel title="MAX DRAWDOWN" delay={0.06}>
            <span className={`hud-value ${performance.max_drawdown_pct < 0 ? "status-bad" : ""}`}>{performance.max_drawdown_pct}%</span>
          </HudPanel>
          <HudPanel title="CAGR" delay={0.08}>
            <span className={`hud-value ${performance.cagr_pct >= 0 ? "status-good" : "status-bad"}`}>
              {performance.cagr_pct !== null ? `${performance.cagr_pct}%` : "—"}
            </span>
          </HudPanel>
        </div>
      )}
      {performance?.insufficient_history && (
        <p className="hud-label status-warn">
          Only {performance.trading_days_used} trading days of real history - treat the stat cards above as
          illustrative-of-the-mechanism only, not a real performance read yet.
        </p>
      )}

      <HudPanel title="POSITIONS">
        {summary && <p className="hud-label" style={{ marginBottom: 10 }}>{summary.account_type}</p>}
        {positions.length === 0 ? (
          <p className="hud-label">No open positions.</p>
        ) : (
          <table className="screen-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Qty</th>
                <th>Avg cost</th>
                <th>Current price</th>
                <th>Market value</th>
                <th>Unrealized P&amp;L</th>
                <th>P&amp;L %</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => (
                <tr
                  key={p.ticker}
                  onClick={() => openTicker(p.ticker)}
                  style={highlightTicker === p.ticker ? { boxShadow: "inset 0 0 0 1px var(--accent-cyan)" } : undefined}
                >
                  <td className="hud-readout">{p.ticker}</td>
                  <td>{p.quantity}</td>
                  <td>{p.avg_cost ?? "—"}</td>
                  <td>{p.current_price ?? "—"}</td>
                  <td>{p.market_value ?? "—"}</td>
                  <td className={p.unrealized_pnl >= 0 ? "status-good" : "status-bad"}>{p.unrealized_pnl ?? "—"}</td>
                  <td className={p.unrealized_pnl_pct >= 0 ? "status-good" : "status-bad"}>
                    {p.unrealized_pnl_pct !== null && p.unrealized_pnl_pct !== undefined ? `${p.unrealized_pnl_pct}%` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </HudPanel>

      <HudPanel title="LOG A TRADE" delay={0.08}>
        <LogTradeForm onLogged={load} />
      </HudPanel>

      {performance && performance.nav_series && performance.nav_series.length > 1 && (
        <HudPanel title="PORTFOLIO VALUE OVER TIME" delay={0.16}>
          {performance.insufficient_history && (
            <p className="hud-label status-warn" style={{ marginBottom: 8 }}>
              Only {performance.trading_days_used} trading days of real history - too short for the shape of this
              chart to mean much yet.
            </p>
          )}
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={performance.nav_series}>
              <XAxis dataKey="date" tick={{ fill: "var(--text-dim)", fontSize: 10 }} axisLine={{ stroke: "var(--border-glow)" }} tickLine={false} />
              <YAxis domain={["auto", "auto"]} tick={{ fill: "var(--text-dim)", fontSize: 10 }} axisLine={false} tickLine={false} width={70} />
              <Tooltip content={<HudTooltip formatter={(p) => `$${p.value.toLocaleString()}`} />} />
              <Line type="monotone" dataKey="value" stroke="var(--accent-cyan)" strokeWidth={1.75} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </HudPanel>
      )}
    </div>
  );
}
