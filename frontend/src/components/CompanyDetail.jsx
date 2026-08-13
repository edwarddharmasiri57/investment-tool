import { scoreColorClass } from "../scoreColor";
import Disclaimer from "./Disclaimer";
import ResearchNote from "./ResearchNote";

const SUB_SCORE_INFO = {
  value: "Cheaper relative to earnings/book value scores higher (P/E, PEG, P/B).",
  quality: "Profitability & balance sheet strength (ROE, operating margin, debt/equity).",
  momentum: "Price trend & distance from highs (200-day MA, % off 52-week high).",
  growth: "Revenue & earnings growth year-over-year.",
};

function Field({ label, value }) {
  return (
    <>
      <div className="label">{label}</div>
      <div>{value === null || value === undefined ? "—" : value}</div>
    </>
  );
}

function LimitationsList({ items }) {
  if (!items || !items.length) return null;
  return (
    <ul className="limitations-list">
      {items.map((l, i) => (
        <li key={i}>{l}</li>
      ))}
    </ul>
  );
}

function pct(value, digits = 1) {
  return value === null || value === undefined ? "—" : `${value.toFixed(digits)}%`;
}

// Distinct from scoreColorClass: margin-of-safety/premium-discount are centered
// on 0 (positive = cheap/undervalued = good), not a 0-100 scale.
function signedColorClass(value, goodAbove, badBelow) {
  if (value === null || value === undefined) return "score-na";
  if (value >= goodAbove) return "score-good";
  if (value <= badBelow) return "score-bad";
  return "score-mid";
}

function zoneColorClass(zone) {
  if (zone === "safe") return "score-good";
  if (zone === "grey") return "score-mid";
  if (zone === "distress") return "score-bad";
  return "score-na";
}

export default function CompanyDetail({
  ticker,
  company,
  tradeScore,
  dcf,
  dcfError,
  comps,
  compsError,
  risk,
  riskError,
  loading,
  error,
  onClose,
  isWatchlisted,
  onToggleWatchlist,
  onRequestResearch,
  research,
  researchLoading,
  researchError,
}) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Close">×</button>
        <h2>{ticker}</h2>

        {loading && <p>Loading...</p>}
        {error && <p className="error-text">{error}</p>}

        {!loading && !error && company && (
          <>
            <div className="detail-actions">
              <button onClick={onToggleWatchlist}>
                {isWatchlisted ? "Remove from watchlist" : "Add to watchlist"}
              </button>
              <button onClick={onRequestResearch} disabled={researchLoading}>
                {researchLoading ? "Generating..." : "Generate research note"}
              </button>
            </div>
            {!research && (
              <p className="hint-text">
                Research note costs an Anthropic API call and takes a few seconds to generate.
              </p>
            )}

            <div className="detail-section">
              <h3>Overview</h3>
              <div className="detail-grid">
                <Field label="Name" value={company.data.name} />
                <Field label="Sector" value={company.data.sector} />
                <Field label="Industry" value={company.data.industry} />
                <Field label="Price" value={company.data.price} />
                <Field label="Market cap" value={company.data.market_cap} />
                <Field label="Recommendation" value={company.data.recommendation} />
              </div>
            </div>

            {tradeScore && (
              <div className="detail-section">
                <h3>Trade score</h3>
                <div className="detail-grid">
                  <Field
                    label="Composite trade score"
                    value={
                      <span className={scoreColorClass(tradeScore.trade_score)}>
                        {tradeScore.trade_score ?? "—"}
                      </span>
                    }
                  />
                  <Field label="Financials (weight)" value={`${tradeScore.pillar_scores.financials ?? "—"} (${tradeScore.weights.financials})`} />
                  <Field label="News (weight)" value={`${tradeScore.pillar_scores.news ?? "—"} (${tradeScore.weights.news})`} />
                  <Field label="Social (weight)" value={`${tradeScore.pillar_scores.social ?? "—"} (${tradeScore.weights.social})`} />
                </div>
                {(tradeScore.news_error || tradeScore.social_error) && (
                  <p className="hint-text">
                    {tradeScore.news_error && `News unavailable: ${tradeScore.news_error}`}
                    {tradeScore.social_error && ` Social unavailable: ${tradeScore.social_error}`}
                  </p>
                )}
              </div>
            )}

            <div className="detail-section">
              <h3>DCF (intrinsic value)</h3>
              {dcfError && <p className="error-text">{dcfError}</p>}
              {dcf && (
                <>
                  <div className="detail-grid">
                    <Field label="Intrinsic value/share" value={`$${dcf.intrinsic_value_per_share}`} />
                    <Field label="Current price" value={`$${dcf.price}`} />
                    <Field
                      label="Margin of safety"
                      value={<span className={signedColorClass(dcf.margin_of_safety_pct, 20, -20)}>{pct(dcf.margin_of_safety_pct)}</span>}
                    />
                    <Field label="WACC (CAPM cost of equity)" value={pct(dcf.wacc * 100, 2)} />
                    <Field label="Growth rate used" value={pct(dcf.growth_rate_used * 100, 2)} />
                    <Field label="Terminal growth rate" value={pct(dcf.terminal_growth_rate * 100, 2)} />
                    <Field label="Enterprise value" value={dcf.enterprise_value.toLocaleString()} />
                    <Field label="Net debt" value={dcf.net_debt.toLocaleString()} />
                  </div>
                  <LimitationsList items={dcf.limitations} />
                </>
              )}
            </div>

            <div className="detail-section">
              <h3>Comparable company analysis</h3>
              {compsError && <p className="error-text">{compsError}</p>}
              {comps && (
                <>
                  <p className="hint-text">
                    {comps.sector} peers: {comps.peers_used.join(", ") || "none found"}
                  </p>
                  <table className="comps-table">
                    <thead>
                      <tr>
                        <th></th>
                        <th>Company</th>
                        <th>Peer median</th>
                        <th>Premium/discount</th>
                      </tr>
                    </thead>
                    <tbody>
                      {["ev_to_ebitda", "ev_to_revenue", "pe_ratio"].map((key) => (
                        <tr key={key}>
                          <td>{key.replace(/_/g, " ").toUpperCase()}</td>
                          <td>{comps.company[key] ?? "—"}</td>
                          <td>{comps.peer_median[key] ?? "—"}</td>
                          <td className={signedColorClass(comps.premium_discount_pct[key] === null ? null : -comps.premium_discount_pct[key], 10, -10)}>
                            {pct(comps.premium_discount_pct[key])}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <LimitationsList items={comps.limitations} />
                </>
              )}
            </div>

            <div className="detail-section">
              <h3>Credit / quality risk</h3>
              {riskError && <p className="error-text">{riskError}</p>}
              {risk && (
                <>
                  <div className="detail-grid">
                    <Field label="Altman Z-Score" value={risk.altman_z_score.z_score} />
                    <Field
                      label="Zone"
                      value={<span className={zoneColorClass(risk.altman_z_score.zone)}>{risk.altman_z_score.zone ?? "n/a"}</span>}
                    />
                    <Field
                      label="Piotroski F-Score"
                      value={risk.piotroski_f_score.f_score !== null ? `${risk.piotroski_f_score.f_score}/9` : "—"}
                    />
                    <Field label="Signals evaluated" value={risk.piotroski_f_score.signals_evaluated} />
                  </div>
                  {risk.altman_z_score.note && <p className="hint-text">{risk.altman_z_score.note}</p>}
                  {risk.piotroski_f_score.note && <p className="hint-text">{risk.piotroski_f_score.note}</p>}
                  <LimitationsList items={risk.limitations} />
                </>
              )}
            </div>

            <div className="detail-section">
              <h3>Fundamentals sub-scores ({company.scores.data_completeness})</h3>
              <div className="detail-grid">
                {Object.entries(company.scores.sub_scores).map(([key, val]) => (
                  <Field
                    key={key}
                    label={key[0].toUpperCase() + key.slice(1)}
                    value={<span className={scoreColorClass(val)}>{val ?? "—"}</span>}
                  />
                ))}
              </div>
              <ul className="research-note">
                {Object.keys(company.scores.sub_scores).map((key) => (
                  <li key={key} style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 4 }}>
                    <strong>{key}:</strong> {SUB_SCORE_INFO[key]}
                  </li>
                ))}
              </ul>
            </div>

            <div className="detail-section">
              <h3>Raw fundamentals</h3>
              <div className="detail-grid">
                <Field label="P/E" value={company.data.pe_ratio} />
                <Field label="Forward P/E" value={company.data.forward_pe} />
                <Field label="PEG" value={company.data.peg_ratio} />
                <Field label="Price/Book" value={company.data.price_to_book} />
                <Field label="ROE" value={company.data.roe} />
                <Field label="Operating margin" value={company.data.operating_margin} />
                <Field label="Debt/Equity" value={company.data.debt_to_equity} />
                <Field label="Current ratio" value={company.data.current_ratio} />
                <Field label="Revenue growth" value={company.data.revenue_growth} />
                <Field label="Earnings growth" value={company.data.earnings_growth} />
                <Field label="Dividend yield" value={company.data.dividend_yield} />
                <Field label="Beta" value={company.data.beta} />
                <Field label="52w high" value={company.data["52w_high"]} />
                <Field label="52w low" value={company.data["52w_low"]} />
                <Field label="% from 52w high" value={company.data.pct_from_52w_high} />
                <Field label="% above 200d MA" value={company.data.pct_above_200d_ma} />
                <Field label="Analyst target" value={company.data.analyst_target_price} />
              </div>
            </div>

            {researchError && <p className="error-text">{researchError}</p>}
            {research && <ResearchNote note={research} />}

            <Disclaimer text={company.disclaimer} />
          </>
        )}
      </div>
    </div>
  );
}
