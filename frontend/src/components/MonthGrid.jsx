function daysInMonth(year, month) {
  return new Date(year, month + 1, 0).getDate();
}

const TYPE_DOT_COLOR = {
  earnings: "var(--accent-warn)",
  news: "var(--accent-cyan)",
  planned_trade: "var(--text-dim)",
};

export default function MonthGrid({ monthCursor, setMonthCursor, events, onSelectEvent }) {
  const year = monthCursor.getFullYear();
  const month = monthCursor.getMonth();
  const firstDay = new Date(year, month, 1).getDay();
  const numDays = daysInMonth(year, month);

  const eventsByDay = {};
  events.forEach((e) => {
    const d = new Date(e.date);
    if (d.getFullYear() === year && d.getMonth() === month) {
      const day = d.getDate();
      (eventsByDay[day] = eventsByDay[day] || []).push(e);
    }
  });

  const cells = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= numDays; d++) cells.push(d);

  return (
    <div style={{ marginTop: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <button onClick={() => setMonthCursor(new Date(year, month - 1, 1))}>&laquo;</button>
        <span className="hud-label">{monthCursor.toLocaleString("default", { month: "long", year: "numeric" })}</span>
        <button onClick={() => setMonthCursor(new Date(year, month + 1, 1))}>&raquo;</button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 4 }}>
        {["S", "M", "T", "W", "T", "F", "S"].map((d, i) => (
          <div key={i} className="hud-label" style={{ textAlign: "center" }}>{d}</div>
        ))}
        {cells.map((day, i) => (
          <div
            key={i}
            style={{
              minHeight: 66,
              border: "1px solid var(--border-glow)",
              borderRadius: 3,
              padding: 4,
              opacity: day ? 1 : 0.2,
            }}
          >
            {day && <div className="hud-label">{day}</div>}
            {day &&
              eventsByDay[day]?.slice(0, 3).map((e, j) => (
                <div
                  key={j}
                  onClick={() => onSelectEvent(e)}
                  title={`${e.ticker}: ${e.detail}`}
                  style={{
                    fontSize: 10,
                    cursor: "pointer",
                    color: TYPE_DOT_COLOR[e.type] || "var(--text-dim)",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  ● {e.ticker}
                </div>
              ))}
            {day && eventsByDay[day]?.length > 3 && (
              <div className="hud-label">+{eventsByDay[day].length - 3} more</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
