import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { getCalendar, getNews, getPortfolioPositions } from "../api";
import { useWatchlist } from "../contexts/WatchlistContext";
import { useTickerDetail } from "../contexts/TickerDetailContext";
import HudPanel from "../components/hud/HudPanel";
import ScanningLoader from "../components/hud/ScanningLoader";
import MonthGrid from "../components/MonthGrid";

const TYPE_META = {
  earnings: { icon: "◆", cls: "status-warn", label: "EARNINGS" },
  planned_trade: { icon: "▸", cls: "status-na", label: "PLANNED" },
  news: { icon: "≡", cls: "status-good", label: "NEWS" },
};

export default function CalendarPage() {
  const { openTicker } = useTickerDetail();
  const { tickers: watchlistTickers } = useWatchlist();
  const location = useLocation();

  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [newsLoaded, setNewsLoaded] = useState(false);
  const [newsLoading, setNewsLoading] = useState(false);

  const [view, setView] = useState("list");
  const [tickerFilter, setTickerFilter] = useState(location.state?.ticker || "ALL");
  const [typeFilter, setTypeFilter] = useState({ earnings: true, planned_trade: true, news: true });
  const [monthCursor, setMonthCursor] = useState(new Date());

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await getCalendar();
      setEvents(data.events || []);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadNews() {
    setNewsLoading(true);
    setError("");
    try {
      const positionsData = await getPortfolioPositions();
      const positionTickers = (positionsData.positions || []).map((p) => p.ticker);
      const allTickers = Array.from(new Set([...watchlistTickers, ...positionTickers]));

      const results = await Promise.allSettled(allTickers.map((t) => getNews(t)));
      const newsEvents = [];
      results.forEach((r, i) => {
        if (r.status !== "fulfilled") return;
        const ticker = allTickers[i];
        (r.value.items || []).forEach((item) => {
          if (!item.published) return;
          newsEvents.push({
            type: "news",
            date: item.published.slice(0, 10),
            ticker,
            detail: item.headline,
            notes: `${(item.sentiment || "").toUpperCase()} - ${item.reason || ""}`,
            url: item.url,
          });
        });
      });
      setEvents((prev) => [...prev.filter((e) => e.type !== "news"), ...newsEvents]);
      setNewsLoaded(true);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setNewsLoading(false);
    }
  }

  const allTickersInEvents = useMemo(() => Array.from(new Set(events.map((e) => e.ticker))).sort(), [events]);

  const filtered = useMemo(
    () =>
      events
        .filter((e) => typeFilter[e.type])
        .filter((e) => tickerFilter === "ALL" || e.ticker === tickerFilter)
        .sort((a, b) => new Date(a.date) - new Date(b.date)),
    [events, typeFilter, tickerFilter]
  );

  if (loading) return <ScanningLoader text="LOADING CALENDAR" />;

  return (
    <div className="overview-grid">
      {error && <p className="hud-label status-bad">{error}</p>}

      <HudPanel title="CALENDAR / FORECAST FEED">
        <div className="detail-actions" style={{ flexWrap: "wrap", gap: 14, alignItems: "center" }}>
          <nav className="hud-nav">
            <button className={view === "list" ? "active" : ""} onClick={() => setView("list")}>List</button>
            <button className={view === "month" ? "active" : ""} onClick={() => setView("month")}>Month</button>
          </nav>

          <select value={tickerFilter} onChange={(e) => setTickerFilter(e.target.value)}>
            <option value="ALL">All tickers</option>
            {allTickersInEvents.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>

          {["earnings", "planned_trade", "news"].map((t) => (
            <label key={t} className="hud-label" style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <input type="checkbox" checked={typeFilter[t]} onChange={() => setTypeFilter((f) => ({ ...f, [t]: !f[t] }))} />
              {TYPE_META[t].label}
            </label>
          ))}

          {!newsLoaded && (
            <button onClick={loadNews} disabled={newsLoading}>
              {newsLoading ? "Loading news..." : "Load news events (Anthropic API, cached 15min)"}
            </button>
          )}
        </div>

        {view === "list" ? (
          <div className="hud-feed" style={{ marginTop: 14 }}>
            {filtered.length === 0 && <p className="hud-label">No events match the current filters.</p>}
            {filtered.map((e, i) => {
              const meta = TYPE_META[e.type] || TYPE_META.planned_trade;
              return (
                <div
                  className="hud-feed-item"
                  key={i}
                  style={{ cursor: "pointer" }}
                  onClick={() => openTicker(e.ticker)}
                  title={e.notes || ""}
                >
                  <span className={`hud-feed-icon ${meta.cls}`}>{meta.icon}</span>
                  <span className="hud-feed-date">{e.date}</span>
                  <span>{e.ticker} — {e.detail}</span>
                  <span className={`hud-label ${meta.cls}`}>{meta.label}</span>
                </div>
              );
            })}
          </div>
        ) : (
          <MonthGrid monthCursor={monthCursor} setMonthCursor={setMonthCursor} events={filtered} onSelectEvent={(e) => openTicker(e.ticker)} />
        )}
      </HudPanel>
    </div>
  );
}
