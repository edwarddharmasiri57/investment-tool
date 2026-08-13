import { motion, useAnimation } from "framer-motion";
import { useEffect, useRef } from "react";

/* Wraps a value; flashes a brief glow+scale pulse only when the value
   actually changes between renders (not continuous). */
export default function PulseValue({ value, className, children }) {
  const controls = useAnimation();
  const prevValue = useRef(value);

  useEffect(() => {
    if (prevValue.current !== undefined && prevValue.current !== value) {
      controls.start({
        scale: [1, 1.06, 1],
        textShadow: [
          "0 0 0px rgba(79,216,255,0)",
          "0 0 10px rgba(79,216,255,0.85)",
          "0 0 0px rgba(79,216,255,0)",
        ],
        transition: { duration: 0.4 },
      });
    }
    prevValue.current = value;
  }, [value, controls]);

  return (
    <motion.span animate={controls} className={className}>
      {children}
    </motion.span>
  );
}
