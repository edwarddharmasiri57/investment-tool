import { animate } from "framer-motion";
import { useEffect, useRef, useState } from "react";

/* Animates on mount (from 0) and again whenever `value` actually changes
   (from the previous displayed value) - not a continuous animation. */
export default function CountUp({ value, decimals = 0, prefix = "", suffix = "", className }) {
  const [display, setDisplay] = useState(0);
  const fromRef = useRef(0);

  useEffect(() => {
    if (value === null || value === undefined || Number.isNaN(value)) return;
    const controls = animate(fromRef.current, value, {
      duration: 0.8,
      ease: "easeOut",
      onUpdate: (v) => setDisplay(v),
    });
    fromRef.current = value;
    return () => controls.stop();
  }, [value]);

  if (value === null || value === undefined || Number.isNaN(value)) {
    return <span className={className}>—</span>;
  }

  return (
    <span className={className}>
      {prefix}
      {display.toFixed(decimals)}
      {suffix}
    </span>
  );
}
