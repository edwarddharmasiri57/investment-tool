export default function Disclaimer({ text }) {
  if (!text) return null;
  return <p className="disclaimer">{text}</p>;
}
