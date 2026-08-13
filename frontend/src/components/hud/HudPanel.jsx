import { motion } from "framer-motion";

export default function HudPanel({ title, children, className = "", delay = 0, ...props }) {
  return (
    <motion.div
      className={`hud-panel ${className}`}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: "easeOut" }}
      {...props}
    >
      {title && <div className="hud-panel-title">{title}</div>}
      {children}
    </motion.div>
  );
}
