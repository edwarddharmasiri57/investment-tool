import axios from "axios";

const client = axios.create({
  baseURL: "http://localhost:8000",
});

function unwrap(promise) {
  return promise.then((r) => r.data);
}

export const getScreen = (tickers) => unwrap(client.post("/api/screen", { tickers }));
export const getCompany = (ticker) => unwrap(client.get(`/api/company/${ticker}`));
export const getTradeScore = (ticker) => unwrap(client.get(`/api/trade-score/${ticker}`));
export const getResearch = (ticker) => unwrap(client.post(`/api/research/${ticker}`));
export const getWatchlist = () => unwrap(client.get("/api/watchlist"));
export const addToWatchlist = (ticker) => unwrap(client.post("/api/watchlist", { ticker }));
export const removeFromWatchlist = (ticker) => unwrap(client.delete(`/api/watchlist/${ticker}`));

export const getDcf = (ticker) => unwrap(client.get(`/api/dcf/${ticker}`));
export const getComps = (ticker) => unwrap(client.get(`/api/comps/${ticker}`));
export const getRisk = (ticker) => unwrap(client.get(`/api/risk/${ticker}`));
export const getDiscover = () => unwrap(client.get("/api/discover"));
export const triggerScan = (tickers) => unwrap(client.post("/api/discover/scan", tickers ? { tickers } : {}));
export const getMovers = () => unwrap(client.get("/api/discover/movers"));

export const getBlend = (ticker) => unwrap(client.get(`/api/blend/${ticker}`));
export const getRegime = () => unwrap(client.get("/api/regime"));

export const logTrade = (trade) => unwrap(client.post("/api/portfolio/trade", trade));
export const getPortfolioPositions = () => unwrap(client.get("/api/portfolio/positions"));
export const getPortfolioSummary = () => unwrap(client.get("/api/portfolio/summary"));
export const getPortfolioTrades = () => unwrap(client.get("/api/portfolio/trades"));
export const logPlannedTrade = (planned) => unwrap(client.post("/api/portfolio/planned", planned));
export const getPlannedTrades = () => unwrap(client.get("/api/portfolio/planned"));
export const getCalendar = () => unwrap(client.get("/api/calendar"));
export const getPortfolioPerformance = () => unwrap(client.get("/api/portfolio/performance"));
export const getPortfolioOptimize = () => unwrap(client.get("/api/portfolio/optimize"));

export const getFactors = (ticker) => unwrap(client.get(`/api/factors/${ticker}`));
export const getCapm = (ticker) => unwrap(client.get(`/api/capm/${ticker}`));
export const getNews = (ticker) => unwrap(client.get(`/api/news/${ticker}`));

export default client;
