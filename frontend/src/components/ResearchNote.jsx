function List({ items }) {
  if (!items || !items.length) return <p className="hint-text">None reported.</p>;
  return (
    <ul>
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

export default function ResearchNote({ note }) {
  return (
    <div className="detail-section research-note">
      <h3>Research note</h3>
      <p>{note.summary}</p>

      <h4>Thesis points</h4>
      <List items={note.thesis_points} />

      <h4>Risk points</h4>
      <List items={note.risk_points} />

      <h4>Recent catalysts</h4>
      <List items={note.recent_catalysts} />

      <h4>Questions to investigate</h4>
      <List items={note.questions_to_investigate} />

      <h4>Sources</h4>
      {note.sources && note.sources.length > 0 ? (
        <ul>
          {note.sources.map((s, i) => (
            <li key={i}>
              <a href={s.url} target="_blank" rel="noreferrer">
                {s.title || s.url}
              </a>
            </li>
          ))}
        </ul>
      ) : (
        <p className="hint-text">No sources returned.</p>
      )}
    </div>
  );
}
