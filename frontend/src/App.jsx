import { useEffect, useState } from "react";
import { Routes, Route } from "react-router-dom";
import { getRegime } from "./api";
import { WatchlistProvider } from "./contexts/WatchlistContext";
import { TickerDetailProvider } from "./contexts/TickerDetailContext";
import Sidebar from "./components/Sidebar";
import RegimeBanner from "./components/RegimeBanner";
import Overview from "./pages/Overview";
import Portfolio from "./pages/Portfolio";
import Screener from "./pages/Screener";
import CalendarPage from "./pages/CalendarPage";
import Forecast from "./pages/Forecast";
import NewsPage from "./pages/NewsPage";
import RiskPage from "./pages/RiskPage";
import "./App.css";
import "./theme.css";

export default function App() {
  const [regime, setRegime] = useState(null);

  useEffect(() => {
    getRegime().then(setRegime).catch(() => {});
  }, []);

  return (
    <>
      <div className="hud-background" />
      <WatchlistProvider>
        <TickerDetailProvider>
          <div className="hud-app">
            <Sidebar />

            <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
              <header className="hud-topbar">
                <h1>Investment Research Dashboard</h1>
                <RegimeBanner regime={regime} />
              </header>

              <main className="hud-main">
                <Routes>
                  <Route path="/" element={<Overview />} />
                  <Route path="/portfolio" element={<Portfolio />} />
                  <Route path="/screener" element={<Screener />} />
                  <Route path="/calendar" element={<CalendarPage />} />
                  <Route path="/forecast" element={<Forecast />} />
                  <Route path="/news" element={<NewsPage />} />
                  <Route path="/risk" element={<RiskPage />} />
                </Routes>
              </main>
            </div>
          </div>
        </TickerDetailProvider>
      </WatchlistProvider>
    </>
  );
}
