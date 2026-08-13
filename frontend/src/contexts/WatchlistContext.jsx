import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { getWatchlist, addToWatchlist, removeFromWatchlist } from "../api";

const WatchlistContext = createContext(null);

export function WatchlistProvider({ children }) {
  const [tickers, setTickers] = useState([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getWatchlist();
      setTickers(data.watchlist || []);
    } catch {
      // sidebar failing to load isn't fatal to the rest of the app
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const addTicker = useCallback(
    async (ticker) => {
      await addToWatchlist(ticker);
      await refresh();
    },
    [refresh]
  );

  const removeTicker = useCallback(
    async (ticker) => {
      await removeFromWatchlist(ticker);
      await refresh();
    },
    [refresh]
  );

  return (
    <WatchlistContext.Provider value={{ tickers, loading, addTicker, removeTicker, refresh }}>
      {children}
    </WatchlistContext.Provider>
  );
}

export function useWatchlist() {
  const ctx = useContext(WatchlistContext);
  if (!ctx) throw new Error("useWatchlist must be used within WatchlistProvider");
  return ctx;
}
