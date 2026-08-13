import { useMemo, useState } from "react";
import { scoreColorClass } from "../scoreColor";

const COLUMNS = [
  { key: "ticker", label: "Ticker" },
  { key: "name", label: "Name" },
  { key: "composite_score", label: "Composite" },
  { key: "value", label: "Value" },
  { key: "quality", label: "Quality" },
  { key: "momentum", label: "Momentum" },
  { key: "growth", label: "Growth" },
];

function getValue(row, key) {
  if (key === "value" || key === "quality" || key === "momentum" || key === "growth") {
    return row.sub_scores?.[key] ?? null;
  }
  return row[key] ?? null;
}

export default function ScreenTable({ results, onSelect }) {
  const [sortKey, setSortKey] = useState("composite_score");
  const [sortDir, setSortDir] = useState("desc");

  const sorted = useMemo(() => {
    const rows = [...results];
    rows.sort((a, b) => {
      const av = getValue(a, sortKey);
      const bv = getValue(b, sortKey);
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
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

  if (!results.length) return null;

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
            <td className={scoreColorClass(row.composite_score)}>
              {row.composite_score ?? "—"}
            </td>
            <td className={scoreColorClass(row.sub_scores?.value)}>
              {row.sub_scores?.value ?? "—"}
            </td>
            <td className={scoreColorClass(row.sub_scores?.quality)}>
              {row.sub_scores?.quality ?? "—"}
            </td>
            <td className={scoreColorClass(row.sub_scores?.momentum)}>
              {row.sub_scores?.momentum ?? "—"}
            </td>
            <td className={scoreColorClass(row.sub_scores?.growth)}>
              {row.sub_scores?.growth ?? "—"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
