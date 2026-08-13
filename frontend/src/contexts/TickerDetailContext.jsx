import { createContext, useContext, useState } from "react";
import { getCompany, getTradeScore, getDcf, getComps, getRisk, getResearch } from "../api";
import CompanyDetail from "../components/CompanyDetail";
import { useWatchlist } from "./WatchlistContext";

const TickerDetailContext = createContext(null);

function detailFrom(settledResult) {
  if (settledResult.status === "fulfilled") return { value: settledResult.value, error: "" };
  const e = settledResult.reason;
  return { value: null, error: e.response?.data?.detail || e.message };
}

/* Centralizes the company-detail-modal fetch/state so any page (Overview,
   Calendar, News, Risk, Screener, ...) can open the same modal via
   useTickerDetail().openTicker(ticker) without prop-drilling through routes. */
export function TickerDetailProvider({ children }) {
  const { tickers: watchlist, addTicker, removeTicker } = useWatchlist();

  const [selectedTicker, setSelectedTicker] = useState(null);
  const [company, setCompany] = useState(null);
  const [tradeScore, setTradeScore] = useState(null);
  const [dcf, setDcf] = useState(null);
  const [dcfError, setDcfError] = useState("");
  const [comps, setComps] = useState(null);
  const [compsError, setCompsError] = useState("");
  const [risk, setRisk] = useState(null);
  const [riskError, setRiskError] = useState("");
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [research, setResearch] = useState(null);
  const [researchLoading, setResearchLoading] = useState(false);
  const [researchError, setResearchError] = useState("");

  async function openTicker(ticker) {
    setSelectedTicker(ticker);
    setCompany(null);
    setTradeScore(null);
    setDcf(null);
    setDcfError("");
    setComps(null);
    setCompsError("");
    setRisk(null);
    setRiskError("");
    setDetailError("");
    setResearch(null);
    setResearchError("");
    setDetailLoading(true);

    const [companyR, tradeScoreR, dcfR, compsR, riskR] = await Promise.allSettled([
      getCompany(ticker),
      getTradeScore(ticker),
      getDcf(ticker),
      getComps(ticker),
      getRisk(ticker),
    ]);

    const companyResult = detailFrom(companyR);
    setCompany(companyResult.value);
    setDetailError(companyResult.error);

    setTradeScore(detailFrom(tradeScoreR).value);

    const dcfResult = detailFrom(dcfR);
    setDcf(dcfResult.value);
    setDcfError(dcfResult.error);

    const compsResult = detailFrom(compsR);
    setComps(compsResult.value);
    setCompsError(compsResult.error);

    const riskResult = detailFrom(riskR);
    setRisk(riskResult.value);
    setRiskError(riskResult.error);

    setDetailLoading(false);
  }

  function closeDetail() {
    setSelectedTicker(null);
  }

  async function toggleWatchlist() {
    if (!selectedTicker) return;
    if (watchlist.includes(selectedTicker)) {
      await removeTicker(selectedTicker);
    } else {
      await addTicker(selectedTicker);
    }
  }

  async function requestResearch() {
    if (!selectedTicker) return;
    setResearchLoading(true);
    setResearchError("");
    try {
      const data = await getResearch(selectedTicker);
      setResearch(data.research);
    } catch (e) {
      setResearchError(e.response?.data?.detail || e.message);
    } finally {
      setResearchLoading(false);
    }
  }

  return (
    <TickerDetailContext.Provider value={{ openTicker }}>
      {children}
      {selectedTicker && (
        <CompanyDetail
          ticker={selectedTicker}
          company={company}
          tradeScore={tradeScore}
          dcf={dcf}
          dcfError={dcfError}
          comps={comps}
          compsError={compsError}
          risk={risk}
          riskError={riskError}
          loading={detailLoading}
          error={detailError}
          onClose={closeDetail}
          isWatchlisted={watchlist.includes(selectedTicker)}
          onToggleWatchlist={toggleWatchlist}
          onRequestResearch={requestResearch}
          research={research}
          researchLoading={researchLoading}
          researchError={researchError}
        />
      )}
    </TickerDetailContext.Provider>
  );
}

export function useTickerDetail() {
  const ctx = useContext(TickerDetailContext);
  if (!ctx) throw new Error("useTickerDetail must be used within TickerDetailProvider");
  return ctx;
}
