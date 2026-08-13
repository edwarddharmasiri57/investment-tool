import { useState } from "react";

export default function ScreenForm({ onSubmit, loading }) {
  const [text, setText] = useState("AAPL, MSFT, GOOGL");

  function handleSubmit(e) {
    e.preventDefault();
    const tickers = text
      .split(",")
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);
    if (tickers.length) onSubmit(tickers);
  }

  return (
    <form className="screen-form" onSubmit={handleSubmit}>
      <label htmlFor="tickers">Tickers (comma-separated)</label>
      <textarea
        id="tickers"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={3}
        placeholder="AAPL, MSFT, GOOGL"
      />
      <button type="submit" disabled={loading}>
        {loading ? "Screening..." : "Run screen"}
      </button>
    </form>
  );
}
