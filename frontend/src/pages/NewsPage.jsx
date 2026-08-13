import { useEffect, useMemo, useState } from "react";
import { getNews, getPortfolioPositions } from "../api";
import { useWatchlist } from "../contexts/WatchlistContext";
import { useTickerDetail } from "../contexts/TickerDetailContext";
import HudPanel from "../components/hud/HudPanel";
import ScanningLoader from "../components/hud/ScanningLoader";

const SENTIMENT_CLASS = { bullish: "status-good", bearish: "status-bad", neutral: "status-na" };

export default function NewsPage() {
  const { tickers: watchlistTickers } = useWatchlist();
  const { openTicker } = useTickerDetail();

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [fetchErrors, setFetchErrors] = useState([]);

  const [tickerFilter, setTickerFilter] = useState("ALL");
  const [sentimentFilter, setSentimentFilter] = useState("ALL");

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const positionsData = await getPortfolioPositions();
      const positionTickers = (positionsData.positions || []).map((p) => p.ticker);
      const allTickers = Array.from(new Set([...watchlistTickers, ...positionTickers]));
      if (!allTickers.length) {
        setItems([]);
        return;
      }
      const results = await Promise.allSettled(allTickers.map((t) => getNews(t)));
      const allItems = [];
      const errs = [];
      results.forEach((r, i) => {
        if (r.status === "fulfilled") {
          (r.value.items || []).forEach((item) => allItems.push({ ...item, ticker: allTickers[i] }));
        } else {
          errs.push(`${allTickers[i]}: ${r.reason.response?.data?.detail || r.reason.message}`);
        }
      });
      setItems(allItems);
      setFetchErrors(errs);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }

  const allTickersInItems = useMemo(() => Array.from(new Set(items.map((i) => i.ticker))).sort(), [items]);

  const filtered = useMemo(() => {
    const list = items
      .filter((i) => tickerFilter === "ALL" || i.ticker === tickerFilter)
      .filter((i) => sentimentFilter === "ALL" || i.sentiment === sentimentFilter);
    list.sort((a, b) => new Date(b.published || 0) - new Date(a.published || 0));
    return list;
  }, [items, tickerFilter, sentimentFilter]);

  if (loading) return <ScanningLoader text="FETCHING & CLASSIFYING NEWS (ONE ANTHROPIC CALL PER TICKER, CACHED 15MIN)" />;

  return (
    <div className="overview-grid">
      {error && <p className="hud-label status-bad">{error}</p>}
      {fetchErrors.length > 0 && (
        <p className="hud-label status-warn">Some tickers failed to load news: {fetchErrors.join("; ")}</p>
      )}

      <HudPanel title={`NEWS FEED (${filtered.length} ITEMS)`}>
        <div className="detail-actions" style={{ flexWrap: "wrap", gap: 14, alignItems: "center" }}>
          <select value={tickerFilter} onChange={(e) => setTickerFilter(e.target.value)}>
            <option value="ALL">All tickers</option>
            {allTickersInItems.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <select value={sentimentFilter} onChange={(e) => setSentimentFilter(e.target.value)}>
            <option value="ALL">All sentiment</option>
            <option value="bullish">Bullish</option>
            <option value="bearish">Bearish</option>
            <option value="neutral">Neutral</option>
          </select>
          <button onClick={load}>Refresh</button>
        </div>

        <div className="hud-feed" style={{ marginTop: 14 }}>
          {filtered.length === 0 && <p className="hud-label">No news items match the current filters.</p>}
          {filtered.map((item, i) => (
            <div key={i} className="hud-feed-item" style={{ gridTemplateColumns: "16px 130px 64px 1fr auto" }}>
              <span className={`hud-feed-icon ${SENTIMENT_CLASS[item.sentiment] || "status-na"}`}>
                {item.sentiment === "bullish" ? "▲" : item.sentiment === "bearish" ? "▼" : "●"}
              </span>
              <span className="hud-feed-date">{item.published ? item.published.slice(0, 16).replace("T", " ") : "—"}</span>
              <span className="hud-readout" style={{ cursor: "pointer" }} onClick={() => openTicker(item.ticker)}>
                {item.ticker}
              </span>
              <span>
                {item.url ? (
                  <a href={item.url} target="_blank" rel="noreferrer">{item.headline}</a>
                ) : (
                  item.headline
                )}
                <span className="hud-label" style={{ display: "block", marginTop: 2 }}>{item.reason}</span>
              </span>
              <span className={`hud-label ${SENTIMENT_CLASS[item.sentiment] || "status-na"}`}>
                {(item.sentiment || "").toUpperCase()}
              </span>
            </div>
          ))}
        </div>
      </HudPanel>
    </div>
  );
}
