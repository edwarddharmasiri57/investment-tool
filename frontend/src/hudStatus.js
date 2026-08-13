export function hudStatusClass(score) {
  if (score === null || score === undefined) return "status-na";
  if (score > 66) return "status-good";
  if (score >= 33) return "status-warn";
  return "status-bad";
}
