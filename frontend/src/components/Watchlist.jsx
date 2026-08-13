import { useState } from "react";

export default function Watchlist({ tickers, loading, onSelect, onAdd, onRemove }) {
  const [input, setInput] = useState("");

  function handleAdd(e) {
    e.preventDefault();
    const ticker = input.trim().toUpperCase();
    if (ticker) {
      onAdd(ticker);
      setInput("");
    }
  }

  return (
    <div className="watchlist">
      <h2>Watchlist</h2>
      <form className="watchlist-form" onSubmit={handleAdd}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Add ticker"
        />
        <button type="submit">+</button>
      </form>
      {loading && <p className="hint-text">Loading...</p>}
      {!loading && tickers.length === 0 && <p className="hint-text">No tickers yet.</p>}
      <ul>
        {tickers.map((ticker) => (
          <li key={ticker}>
            <button className="watchlist-ticker" onClick={() => onSelect(ticker)}>
              {ticker}
            </button>
            <button className="watchlist-remove" onClick={() => onRemove(ticker)} aria-label={`Remove ${ticker}`}>
              ×
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
