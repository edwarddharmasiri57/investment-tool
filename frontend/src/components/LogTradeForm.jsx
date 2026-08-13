import { useState } from "react";
import { logTrade } from "../api";

const TODAY = new Date().toISOString().slice(0, 10);

export default function LogTradeForm({ onLogged }) {
  const [ticker, setTicker] = useState("");
  const [action, setAction] = useState("BUY");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [date, setDate] = useState(TODAY);
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await logTrade({
        ticker: ticker.toUpperCase().trim(),
        action,
        quantity: parseFloat(quantity),
        price: parseFloat(price),
        date,
        notes,
      });
      setTicker("");
      setQuantity("");
      setPrice("");
      setNotes("");
      onLogged?.();
    } catch (e2) {
      setError(e2.response?.data?.detail || e2.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="screen-form" onSubmit={handleSubmit}>
      <p className="hud-label status-warn">
        Manual journal entry only - this does not execute a real trade anywhere.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: 10 }}>
        <div>
          <label className="hud-label" htmlFor="lt-ticker">Ticker</label>
          <input id="lt-ticker" value={ticker} onChange={(e) => setTicker(e.target.value)} required />
        </div>
        <div>
          <label className="hud-label" htmlFor="lt-action">Action</label>
          <select id="lt-action" value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </select>
        </div>
        <div>
          <label className="hud-label" htmlFor="lt-qty">Quantity</label>
          <input id="lt-qty" type="number" step="any" min="0" value={quantity} onChange={(e) => setQuantity(e.target.value)} required />
        </div>
        <div>
          <label className="hud-label" htmlFor="lt-price">Price</label>
          <input id="lt-price" type="number" step="any" min="0" value={price} onChange={(e) => setPrice(e.target.value)} required />
        </div>
        <div>
          <label className="hud-label" htmlFor="lt-date">Date</label>
          <input id="lt-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </div>
      </div>
      <div>
        <label className="hud-label" htmlFor="lt-notes">Notes</label>
        <input id="lt-notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="optional" style={{ width: "100%" }} />
      </div>
      {error && <p className="hud-label status-bad">{error}</p>}
      <button type="submit" disabled={loading}>{loading ? "Logging..." : "Log trade"}</button>
    </form>
  );
}
