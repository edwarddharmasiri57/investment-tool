import { useMemo, useState } from "react";
import { scoreColorClass } from "../scoreColor";

const COLUMNS = [
  { key: "ticker", label: "Ticker" },
  { key: "name", label: "Name" },
  { key: "sector", label: "Sector" },
  { key: "composite_score", label: "Composite" },
  { key: "blended_score", label: "Blended" },
  { key: "margin_of_safety_pct", label: "Margin of Safety" },
  { key: "altman_zone", label: "Altman Zone" },
  { key: "piotroski_f_score", label: "Piotroski" },
];

function marginColorClass(pct) {
  if (pct === null || pct === undefined) return "score-na";
  if (pct > 20) return "score-good";
  if (pct > -20) return "score-mid";
  return "score-bad";
}

function zoneColorClass(zone) {
  if (zone === "safe") return "score-good";
  if (zone === "grey") return "score-mid";
  if (zone === "distress") return "score-bad";
  return "score-na";
}

export default function DiscoverTable({ results, onSelect }) {
  const [sortKey, setSortKey] = useState("composite_score");
  const [sortDir, setSortDir] = useState("desc");

  const sorted = useMemo(() => {
    const rows = [...results];
    rows.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      if (typeof av === "string" || typeof bv === "string") {
        return sortDir === "asc"
          ? String(av).localeCompare(String(bv))
          : String(bv).localeCompare(String(av));
      }
      return sortDir === "asc" ? av - bv : bv - av;
    });
    return rows;
  }, [results, sortKey, sortDir]);

  function handleSort(key) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  if (!results.length) return <p className="hint-text">No scan results yet.</p>;

  return (
    <table className="screen-table">
      <thead>
        <tr>
          {COLUMNS.map((col) => (
            <th key={col.key} onClick={() => handleSort(col.key)}>
              {col.label}
              {sortKey === col.key ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sorted.map((row) => (
          <tr key={row.ticker} onClick={() => onSelect(row.ticker)}>
            <td>{row.ticker}</td>
            <td>{row.name}</td>
            <td>{row.sector}</td>
            <td className={scoreColorClass(row.composite_score)}>{row.composite_score ?? "—"}</td>
            <td className={scoreColorClass(row.blended_score)}>{row.blended_score ?? "—"}</td>
            <td className={marginColorClass(row.margin_of_safety_pct)}>
              {row.margin_of_safety_pct !== null && row.margin_of_safety_pct !== undefined
                ? `${row.margin_of_safety_pct.toFixed(1)}%`
                : "—"}
            </td>
            <td className={zoneColorClass(row.altman_zone)}>{row.altman_zone ?? "—"}</td>
            <td>{row.piotroski_f_score !== null && row.piotroski_f_score !== undefined ? `${row.piotroski_f_score}/9` : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
