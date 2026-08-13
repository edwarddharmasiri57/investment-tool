export function scoreColorClass(score) {
  if (score === null || score === undefined) return "score-na";
  if (score > 70) return "score-good";
  if (score >= 40) return "score-mid";
  return "score-bad";
}
