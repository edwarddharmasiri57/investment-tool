import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PieChart, Pie, Cell, Tooltip } from "recharts";
import {
  getPortfolioSummary,
  getPortfolioTrades,
  getCalendar,
  getRegime,
  getMovers,
} from "../api";
import HudPanel from "../components/hud/HudPanel";
import RadialGauge from "../components/hud/RadialGauge";
import CountUp from "../components/hud/CountUp";
import ScanningLoader from "../components/hud/ScanningLoader";
import HudTooltip from "../components/hud/HudTooltip";
import { hudStatusClass } from "../hudStatus";

const DONUT_COLORS = ["#4fd8ff", "#2fb8e0", "#1f8fb0", "#ff8a4f", "#5a7a8a", "#3a5a6a"];

function formatMoney(v) {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function Overview() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState(null);
  const [trades, setTrades] = useState([]);
  const [events, setEvents] = useState([]);
  const [regime, setRegime] = useState(null);
  const [movers, setMovers] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const [summaryData, tradesData, calendarData, regimeData, moversData] = await Promise.all([
          getPortfolioSummary(),
          getPortfolioTrades(),
          getCalendar(),
          getRegime(),
          getMovers(),
        ]);
        if (cancelled) return;
        setSummary(summaryData);
        setTrades(tradesData.trades || []);
        setEvents(calendarData.events || []);
        setRegime(regimeData);
        setMovers(moversData);
      } catch (e) {
        if (!cancelled) setError(e.response?.data?.detail || e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <ScanningLoader text="SYSTEM INITIALIZING" />;
  if (error) return <p className="hud-label status-bad">{error}</p>;
  if (!summary) return null;

  const healthScore = summary.health_score?.score;
  const pnlPositive = summary.total_pnl >= 0;

  const donutData = (summary.allocation || [])
    .filter((a) => a.pct_of_portfolio > 0)
    .map((a) => ({ name: a.ticker, value: a.pct_of_portfolio }));

  const recentTrades = [...trades].reverse().slice(0, 5);

  const now = new Date();
  const upcomingEvents = [...events]
    .filter((e) => new Date(e.date) >= new Date(now.toDateString()))
    .sort((a, b) => new Date(a.date) - new Date(b.date))
    .slice(0, 6);

  return (
    <div className="overview-grid">
      <div className="overview-row">
        <HudPanel
          title="THE CORE / PORTFOLIO HEALTH"
          delay={0}
          className="overview-core"
          style={{ cursor: "pointer" }}
          onClick={() => navigate("/portfolio")}
        >
          <RadialGauge
            value={healthScore}
            label="HEALTH"
            sublabel={summary.total_pnl_pct !== null ? `${summary.total_pnl_pct >= 0 ? "+" : ""}${summary.total_pnl_pct}% P&L` : "—"}
            statusClass={hudStatusClass(healthScore)}
          />
          <p className="hud-label" style={{ textAlign: "center", marginTop: 10 }}>
            60% P&amp;L + 40% diversification &middot; not a standard industry metric
          </p>
        </HudPanel>

        <HudPanel
          title="PORTFOLIO SUMMARY"
          delay={0.08}
          className="overview-summary"
          style={{ cursor: "pointer" }}
          onClick={() => navigate("/portfolio")}
        >
          <div className="hud-metric">
            <span className="hud-label">Total value</span>
            <CountUp value={summary.total_value} decimals={2} prefix="$" className="hud-value" />
          </div>
          <div className="hud-metric">
            <span className="hud-label">Total P&amp;L</span>
            <CountUp
              value={summary.total_pnl}
              decimals={2}
              prefix={pnlPositive ? "+$" : "-$"}
              className={`hud-value ${pnlPositive ? "status-good" : "status-bad"}`}
            />
          </div>
          <p className="hud-label" style={{ marginTop: 8 }}>{summary.account_type}</p>

          {donutData.length > 0 && (
            <div style={{ display: "flex", justifyContent: "center", marginTop: 12 }}>
              <PieChart width={180} height={180}>
                <Pie data={donutData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={78} paddingAngle={2}>
                  {donutData.map((entry, i) => (
                    <Cell key={entry.name} fill={DONUT_COLORS[i % DONUT_COLORS.length]} stroke="var(--bg-panel)" />
                  ))}
                </Pie>
                <Tooltip content={<HudTooltip formatter={(p) => `${p.name}: ${p.value}%`} />} />
              </PieChart>
            </div>
          )}
        </HudPanel>

        {regime && (
          <HudPanel
            title="MARKET REGIME"
            delay={0.16}
            className="overview-regime"
            style={{ cursor: "pointer" }}
            onClick={() => navigate("/forecast")}
          >
            <div className={`hud-metric`}>
              <span className={`hud-value ${hudStatusClass(regime.regime === "Risk-On" ? 100 : regime.regime === "Elevated-Volatility" ? 50 : 0)}`}>
                {regime.regime}
              </span>
            </div>
            <p className="hud-label" style={{ marginTop: 10 }}>{regime.reason}</p>
            <p className="hud-label" style={{ marginTop: 10 }}>
              VIX {regime.vix ?? "—"} &middot; 10y-2y {regime.ten_minus_two_spread_pp ?? "—"}pp
            </p>
          </HudPanel>
        )}
      </div>

      <div className="overview-row">
        <HudPanel title="UPCOMING" delay={0.24} className="overview-feed">
          {upcomingEvents.length === 0 && <p className="hud-label">No upcoming events.</p>}
          <div className="hud-feed">
            {upcomingEvents.map((e, i) => (
              <div
                className="hud-feed-item"
                key={i}
                style={{ cursor: "pointer" }}
                onClick={() => navigate("/calendar", { state: { ticker: e.ticker, date: e.date } })}
              >
                <span className={`hud-feed-icon ${e.type === "earnings" ? "earnings" : "planned"}`}>
                  {e.type === "earnings" ? "◆" : "▸"}
                </span>
                <span className="hud-feed-date">{e.date}</span>
                <span>{e.ticker} — {e.detail}</span>
                <span className="hud-label">{e.type === "earnings" ? "EARNINGS" : "PLANNED"}</span>
              </div>
            ))}
          </div>
        </HudPanel>

        <HudPanel title="RECENT TRADES" delay={0.32} className="overview-feed">
          {recentTrades.length === 0 && <p className="hud-label">No trades logged yet.</p>}
          <div className="hud-feed">
            {recentTrades.map((t) => (
              <div
                className="hud-feed-item"
                key={t.id}
                style={{ cursor: "pointer" }}
                onClick={() => navigate("/portfolio", { state: { ticker: t.ticker } })}
              >
                <span className={`hud-feed-icon trade`}>{t.action === "BUY" ? "▲" : "▼"}</span>
                <span className="hud-feed-date">{t.date}</span>
                <span>
                  {t.action} {t.quantity} {t.ticker} @ ${t.price}
                </span>
                <span className="hud-label">${formatMoney(t.quantity * t.price)}</span>
              </div>
            ))}
          </div>
        </HudPanel>
      </div>

      {movers && (
        <div className="overview-row">
          <HudPanel title="SCORE MOVERS (SINCE LAST SCAN)" delay={0.4} className="overview-feed">
            {!movers.has_data && <p className="hud-label">{movers.note}</p>}
            {movers.has_data && movers.tickers_compared === 0 && (
              <p className="hud-label">No composite-score changes between the last two scans.</p>
            )}
            {movers.has_data && movers.tickers_compared > 0 && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                <div>
                  <p className="hud-label status-good" style={{ marginBottom: 6 }}>Gainers</p>
                  <div className="hud-feed">
                    {movers.gainers.map((m) => (
                      <div className="hud-feed-item" key={m.ticker}>
                        <span className="hud-feed-icon trade status-good">▲</span>
                        <span>{m.ticker}</span>
                        <span className="hud-label">{m.composite_score}</span>
                        <span className="status-good">+{m.delta}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="hud-label status-bad" style={{ marginBottom: 6 }}>Losers</p>
                  <div className="hud-feed">
                    {movers.losers.map((m) => (
                      <div className="hud-feed-item" key={m.ticker}>
                        <span className="hud-feed-icon trade status-bad">▼</span>
                        <span>{m.ticker}</span>
                        <span className="hud-label">{m.composite_score}</span>
                        <span className="status-bad">{m.delta}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </HudPanel>
        </div>
      )}
    </div>
  );
}
