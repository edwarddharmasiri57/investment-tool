import { useEffect, useMemo, useState } from "react";
import { getCompany, getDcf, getCapm, getBlend, getPortfolioPositions } from "../api";
import { useWatchlist } from "../contexts/WatchlistContext";
import HudPanel from "../components/hud/HudPanel";
import ScanningLoader from "../components/hud/ScanningLoader";

function pct(v, digits = 1) {
  return v === null || v === undefined || Number.isNaN(v) ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

/* Not a statistical confidence interval - just the spread across three
   independently-flawed methods (DCF, CAPM, analyst consensus), each with
   its own documented limitations. Low/high = min/max of whatever's
   available; base = simple average. Deliberately not a single false-precise
   number. */
function computeReturnRange({ dcf, capm, analystTargetPct }) {
  const sources = [];
  if (dcf?.margin_of_safety_pct !== null && dcf?.margin_of_safety_pct !== undefined) {
    sources.push({ source: "DCF margin of safety", value: dcf.margin_of_safety_pct });
  }
  if (capm?.capm_expected_return_pct !== null && capm?.capm_expected_return_pct !== undefined) {
    sources.push({ source: "CAPM expected return", value: capm.capm_expected_return_pct });
  }
  if (analystTargetPct !== null && analystTargetPct !== undefined) {
    sources.push({ source: "Analyst target price", value: analystTargetPct });
  }
  if (!sources.length) return null;
  const nums = sources.map((s) => s.value);
  return {
    low: Math.min(...nums),
    base: nums.reduce((a, b) => a + b, 0) / nums.length,
    high: Math.max(...nums),
    sources,
  };
}

function RangeRow({ range }) {
  if (!range) return <p className="hud-label">Not enough data to synthesize a range.</p>;
  return (
    <>
      <div style={{ display: "flex", gap: 28, alignItems: "baseline", flexWrap: "wrap" }}>
        <div className="hud-metric">
          <span className="hud-label">Low</span>
          <span className="hud-value status-bad">{pct(range.low)}</span>
        </div>
        <div className="hud-metric">
          <span className="hud-label">Base (avg)</span>
          <span className="hud-value">{pct(range.base)}</span>
        </div>
        <div className="hud-metric">
          <span className="hud-label">High</span>
          <span className="hud-value status-good">{pct(range.high)}</span>
        </div>
      </div>
      {range.sources && (
        <p className="hud-label" style={{ marginTop: 10 }}>
          Sources: {range.sources.map((s) => `${s.source} (${pct(s.value)})`).join(" · ")}
        </p>
      )}
    </>
  );
}

export default function Forecast() {
  const { tickers: watchlistTickers } = useWatchlist();
  const [positionTickers, setPositionTickers] = useState([]);
  const [ticker, setTicker] = useState(null);

  const [company, setCompany] = useState(null);
  const [dcf, setDcf] = useState(null);
  const [dcfError, setDcfError] = useState("");
  const [capm, setCapm] = useState(null);
  const [capmError, setCapmError] = useState("");
  const [blend, setBlend] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [portfolioForecast, setPortfolioForecast] = useState(null);
  const [portfolioLoading, setPortfolioLoading] = useState(true);

  const availableTickers = useMemo(
    () => Array.from(new Set([...positionTickers, ...watchlistTickers])).sort(),
    [positionTickers, watchlistTickers]
  );

  useEffect(() => {
    getPortfolioPositions()
      .then((d) => setPositionTickers((d.positions || []).map((p) => p.ticker)))
      .catch(() => {});
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
    setError("");
    setDcfError("");
    setCapmError("");
    try {
      setCompany(await getCompany(t));
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
      setLoading(false);
      return;
    }
    const [dcfR, capmR, blendR] = await Promise.allSettled([getDcf(t), getCapm(t), getBlend(t)]);
    if (dcfR.status === "fulfilled") {
      setDcf(dcfR.value);
    } else {
      setDcf(null);
      setDcfError(dcfR.reason.response?.data?.detail || dcfR.reason.message);
    }
    if (capmR.status === "fulfilled") {
      setCapm(capmR.value);
    } else {
      setCapm(null);
      setCapmError(capmR.reason.response?.data?.detail || capmR.reason.message);
    }
    setBlend(blendR.status === "fulfilled" ? blendR.value : null);
    setLoading(false);
  }

  useEffect(() => {
    async function loadPortfolioForecast() {
      setPortfolioLoading(true);
      try {
        const posData = await getPortfolioPositions();
        const positions = posData.positions || [];
        const totalValue = positions.reduce((sum, p) => sum + (p.market_value || 0), 0);
        if (!positions.length || !totalValue) {
          setPortfolioForecast(null);
          return;
        }

        const details = await Promise.all(
          positions.map(async (p) => {
            const [companyR, dcfR, capmR] = await Promise.allSettled([getCompany(p.ticker), getDcf(p.ticker), getCapm(p.ticker)]);
            const companyData = companyR.status === "fulfilled" ? companyR.value : null;
            const dcfData = dcfR.status === "fulfilled" ? dcfR.value : null;
            const capmData = capmR.status === "fulfilled" ? capmR.value : null;
            const price = companyData?.data?.price;
            const target = companyData?.data?.analyst_target_price;
            const analystPct = price && target ? ((target - price) / price) * 100 : null;
            const range = computeReturnRange({ dcf: dcfData, capm: capmData, analystTargetPct: analystPct });
            return { ticker: p.ticker, weight: (p.market_value || 0) / totalValue, range };
          })
        );

        const usable = details.filter((d) => d.range);
        if (!usable.length) {
          setPortfolioForecast(null);
          return;
        }
        const weightSum = usable.reduce((s, d) => s + d.weight, 0);
        setPortfolioForecast({
          base: usable.reduce((s, d) => s + d.range.base * d.weight, 0) / weightSum,
          low: usable.reduce((s, d) => s + d.range.low * d.weight, 0) / weightSum,
          high: usable.reduce((s, d) => s + d.range.high * d.weight, 0) / weightSum,
          details: usable,
        });
      } catch {
        setPortfolioForecast(null);
      } finally {
        setPortfolioLoading(false);
      }
    }
    loadPortfolioForecast();
  }, []);

  const price = company?.data?.price;
  const target = company?.data?.analyst_target_price;
  const analystPct = price && target ? ((target - price) / price) * 100 : null;
  const returnRange = computeReturnRange({ dcf, capm, analystTargetPct: analystPct });

  return (
    <div className="overview-grid">
      <HudPanel title="TICKER FORECAST">
        <select value={ticker || ""} onChange={(e) => setTicker(e.target.value)}>
          {availableTickers.length === 0 && <option value="">No tickers in watchlist/portfolio</option>}
          {availableTickers.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </HudPanel>

      {loading && <ScanningLoader text={`ANALYZING ${ticker}`} />}
      {error && <p className="hud-label status-bad">{error}</p>}

      {!loading && company && (
        <>
          <div className="overview-row">
            <HudPanel title="DCF (BASE CASE)" delay={0.05}>
              {dcfError && <p className="hud-label status-bad">{dcfError}</p>}
              {dcf && (
                <div className="hud-metric">
                  <span className="hud-label">Intrinsic value vs price</span>
                  <span className="hud-value">${dcf.intrinsic_value_per_share} vs ${dcf.price}</span>
                  <span className={`hud-label ${dcf.margin_of_safety_pct >= 0 ? "status-good" : "status-bad"}`}>
                    Margin of safety: {pct(dcf.margin_of_safety_pct)}
                  </span>
                  <p className="hud-label" style={{ marginTop: 6 }}>Base case only - no bull/bear sensitivity built.</p>
                </div>
              )}
            </HudPanel>

            <HudPanel title="CAPM EXPECTED RETURN" delay={0.1}>
              {capmError && <p className="hud-label status-bad">{capmError}</p>}
              {capm && (
                <div className="hud-metric">
                  <span className="hud-label">Beta {capm.beta} &middot; R&sup2; {capm.r_squared}</span>
                  <span className="hud-value">{pct(capm.capm_expected_return_pct)}</span>
                </div>
              )}
            </HudPanel>

            <HudPanel title="ANALYST TARGET" delay={0.15}>
              <div className="hud-metric">
                <span className="hud-label">Target vs price</span>
                <span className="hud-value">${target ?? "—"} vs ${price ?? "—"}</span>
                <span className={`hud-label ${analystPct >= 0 ? "status-good" : "status-bad"}`}>{pct(analystPct)}</span>
              </div>
            </HudPanel>
          </div>

          <HudPanel title="EXPECTED RETURN RANGE (SYNTHESIZED)" delay={0.2}>
            <RangeRow range={returnRange} />
            <p className="hud-label status-warn" style={{ marginTop: 6 }}>
              Not a statistical confidence interval - each source has its own limitations (see the DCF/CAPM
              panels above and the blended-score breakdown below).
            </p>
          </HudPanel>

          {blend && (
            <HudPanel title="BLENDED SCORE BREAKDOWN" delay={0.25}>
              <div className="hud-metric" style={{ marginBottom: 10 }}>
                <span className="hud-label">Blended score</span>
                <span className="hud-value">{blend.blended_score ?? "—"}</span>
              </div>
              <table className="screen-table">
                <thead>
                  <tr>
                    <th>View</th>
                    <th>Score</th>
                    <th>Confidence</th>
                    <th>Weight</th>
                    <th>Contribution</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(blend.breakdown).map(([k, v]) => (
                    <tr key={k}>
                      <td>{k}</td>
                      <td>{v.score}</td>
                      <td>{v.confidence}</td>
                      <td>{v.normalized_weight}</td>
                      <td>{v.contribution}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {blend.regime_note && <p className="hud-label status-warn" style={{ marginTop: 8 }}>{blend.regime_note}</p>}
            </HudPanel>
          )}
        </>
      )}

      <HudPanel title="PORTFOLIO-LEVEL EXPECTED RETURN" delay={0.3}>
        {portfolioLoading && <ScanningLoader text="AGGREGATING HOLDINGS" />}
        {!portfolioLoading && !portfolioForecast && <p className="hud-label">No positions with enough data to aggregate.</p>}
        {!portfolioLoading && portfolioForecast && (
          <>
            <RangeRow range={portfolioForecast} />
            <p className="hud-label" style={{ marginTop: 8 }}>
              Weighted by position market value across {portfolioForecast.details.length} holding(s) with usable data.
            </p>
          </>
        )}
      </HudPanel>
    </div>
  );
}
