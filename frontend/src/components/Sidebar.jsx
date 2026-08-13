import { NavLink } from "react-router-dom";
import Watchlist from "./Watchlist";
import { useWatchlist } from "../contexts/WatchlistContext";
import { useTickerDetail } from "../contexts/TickerDetailContext";

const NAV_ITEMS = [
  { to: "/", label: "Overview", icon: "◈", end: true },
  { to: "/portfolio", label: "Portfolio", icon: "◆" },
  { to: "/screener", label: "Screener", icon: "⌗" },
  { to: "/calendar", label: "Calendar", icon: "▦" },
  { to: "/forecast", label: "Forecast", icon: "▹" },
  { to: "/news", label: "News", icon: "≡" },
  { to: "/risk", label: "Risk", icon: "▲" },
];

export default function Sidebar() {
  const { tickers, loading, addTicker, removeTicker } = useWatchlist();
  const { openTicker } = useTickerDetail();

  return (
    <aside className="hud-sidebar">
      <div className="hud-sidebar-brand">
        <span className="hud-label">SYSTEM</span>
      </div>

      <nav className="hud-sidenav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => `hud-sidenav-item ${isActive ? "active" : ""}`}
          >
            <span className="hud-sidenav-icon">{item.icon}</span>
            <span className="hud-sidenav-label">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="hud-sidebar-watchlist">
        <Watchlist tickers={tickers} loading={loading} onSelect={openTicker} onAdd={addTicker} onRemove={removeTicker} />
      </div>
    </aside>
  );
}
