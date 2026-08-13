import { useEffect, useState } from "react";
import { getScreen, getDiscover, triggerScan } from "../api";
import { useTickerDetail } from "../contexts/TickerDetailContext";
import ScreenForm from "../components/ScreenForm";
import ScreenTable from "../components/ScreenTable";
import DiscoverTable from "../components/DiscoverTable";
import HudPanel from "../components/hud/HudPanel";
import Disclaimer from "../components/Disclaimer";

export default function Screener() {
  const { openTicker } = useTickerDetail();
  const [tab, setTab] = useState("mylist");

  const [results, setResults] = useState([]);
  const [screenErrors, setScreenErrors] = useState([]);
  const [disclaimer, setDisclaimer] = useState("");
  const [screenLoading, setScreenLoading] = useState(false);
  const [screenError, setScreenError] = useState("");

  const [discoverScan, setDiscoverScan] = useState(null);
  const [discoverLoading, setDiscoverLoading] = useState(false);
  const [discoverError, setDiscoverError] = useState("");
  const [discoverStatusMessage, setDiscoverStatusMessage] = useState("");

  useEffect(() => {
    if (tab === "discover" && !discoverScan) refreshDiscover();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function runScreen(tickers) {
    setScreenLoading(true);
    setScreenError("");
    try {
      const data = await getScreen(tickers);
      setResults(data.results);
      setScreenErrors(data.errors || []);
      setDisclaimer(data.disclaimer);
    } catch (e) {
      setScreenError(e.response?.data?.detail || e.message);
    } finally {
      setScreenLoading(false);
    }
  }

  async function refreshDiscover() {
    setDiscoverLoading(true);
    setDiscoverError("");
    try {
      const data = await getDiscover();
      setDiscoverScan(data);
    } catch (e) {
      if (e.response?.status === 404) {
        setDiscoverScan(null);
      } else {
        setDiscoverError(e.response?.data?.detail || e.message);
      }
    } finally {
      setDiscoverLoading(false);
    }
  }

  async function runFullScan() {
    setDiscoverStatusMessage("");
    try {
      const data = await triggerScan();
      setDiscoverStatusMessage(data.message || data.status);
    } catch (e) {
      setDiscoverError(e.response?.data?.detail || e.message);
    }
  }

  return (
    <div className="overview-grid">
      <nav className="hud-nav" style={{ marginBottom: 4 }}>
        <button className={tab === "mylist" ? "active" : ""} onClick={() => setTab("mylist")}>
          My List
        </button>
        <button className={tab === "discover" ? "active" : ""} onClick={() => setTab("discover")}>
          Discover
        </button>
      </nav>

      {tab === "mylist" && (
        <HudPanel title="MANUAL SCREEN">
          <ScreenForm onSubmit={runScreen} loading={screenLoading} />
          {screenError && <p className="hud-label status-bad">{screenError}</p>}
          {screenErrors.length > 0 && (
            <ul className="error-list">
              {screenErrors.map((e) => (
                <li key={e.ticker}>{e.ticker}: {e.error}</li>
              ))}
            </ul>
          )}
          <ScreenTable results={results} onSelect={openTicker} />
          <Disclaimer text={disclaimer} />
        </HudPanel>
      )}

      {tab === "discover" && (
        <HudPanel title="S&P 500 DISCOVERY SCAN">
          <div className="detail-actions">
            <button onClick={refreshDiscover} disabled={discoverLoading}>
              {discoverLoading ? "Loading..." : "Refresh"}
            </button>
            <button onClick={runFullScan}>Run full S&amp;P 500 scan</button>
          </div>
          {discoverStatusMessage && <p className="hud-label">{discoverStatusMessage}</p>}
          {discoverError && <p className="hud-label status-bad">{discoverError}</p>}
          {!discoverScan && !discoverLoading && !discoverError && (
            <p className="hud-label">
              No scan has run yet. Click "Run full S&amp;P 500 scan" (takes tens of minutes) or wait for the daily
              06:00 automatic scan.
            </p>
          )}
          {discoverScan && (
            <>
              <p className="hud-label">
                Scanned {discoverScan.companies_scored}/{discoverScan.universe_size} companies (finished{" "}
                {new Date(discoverScan.finished_at).toLocaleString()}), {discoverScan.errors.length} errors.
              </p>
              <DiscoverTable results={discoverScan.results} onSelect={openTicker} />
              <Disclaimer text={discoverScan.disclaimer} />
            </>
          )}
        </HudPanel>
      )}
    </div>
  );
}
