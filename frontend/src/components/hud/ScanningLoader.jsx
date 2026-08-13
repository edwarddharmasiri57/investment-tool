import { motion } from "framer-motion";

export default function ScanningLoader({ text = "SCANNING" }) {
  return (
    <div className="scanning-loader">
      <span className="hud-label">{text}</span>
      <motion.span
        animate={{ opacity: [0.2, 1, 0.2] }}
        transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
        style={{ fontFamily: "var(--font-mono)", color: "var(--accent-cyan)" }}
      >
        ...
      </motion.span>
    </div>
  );
}
