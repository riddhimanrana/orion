"use client";
import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronUp } from "lucide-react";
import { cn } from "../../lib/utils";

interface ScrollToTopProps {
  className?: string;
  showAfter?: number;
  color?: string;
  size?: number;
  bottom?: string;
  right?: string;
}

export const ScrollToTop = ({
  className,
  showAfter = 300,
  color = "#3b82f6",
  size = 48,
  bottom = "2rem",
  right = "2rem",
}: ScrollToTopProps) => {
  const [isVisible, setIsVisible] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      const scrollPercent = (scrollTop / docHeight) * 100;

      setScrollProgress(scrollPercent);
      setIsVisible(scrollTop > showAfter);
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, [showAfter]);

  const scrollToTop = () => {
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  const circumference = 2 * Math.PI * 20; // radius of 20
  const strokeDashoffset = circumference - (scrollProgress / 100) * circumference;

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          className={cn(
            "fixed z-50 cursor-pointer group",
            className
          )}
          style={{
            bottom,
            right,
            width: `${size}px`,
            height: `${size}px`,
          }}
          initial={{
            opacity: 0,
            scale: 0,
            rotate: -180,
          }}
          animate={{
            opacity: 1,
            scale: 1,
            rotate: 0,
          }}
          exit={{
            opacity: 0,
            scale: 0,
            rotate: 180,
          }}
          transition={{
            type: "spring",
            stiffness: 300,
            damping: 30,
          }}
          whileHover={{
            scale: 1.1,
            rotate: 5,
          }}
          whileTap={{
            scale: 0.9,
          }}
          onClick={scrollToTop}
        >
          {/* Glow effect */}
          <div
            className="absolute inset-0 rounded-full opacity-20 group-hover:opacity-30 transition-opacity duration-300"
            style={{
              background: `radial-gradient(circle, ${color} 0%, transparent 70%)`,
              filter: "blur(8px)",
              transform: "scale(1.5)",
            }}
          />

          {/* Background */}
          <div
            className="absolute inset-0 rounded-full backdrop-blur-sm border transition-all duration-300"
            style={{
              background: `linear-gradient(135deg, rgba(15, 23, 42, 0.8) 0%, rgba(30, 41, 59, 0.9) 100%)`,
              borderColor: `${color}40`,
              boxShadow: `
                0 4px 20px rgba(0, 0, 0, 0.3),
                0 0 20px ${color}20,
                inset 0 1px 0 rgba(255, 255, 255, 0.1)
              `,
            }}
          />

          {/* Progress ring */}
          <svg
            className="absolute inset-0 w-full h-full transform -rotate-90"
            style={{ zIndex: 1 }}
          >
            <circle
              cx="50%"
              cy="50%"
              r="20"
              fill="none"
              stroke="rgba(255, 255, 255, 0.1)"
              strokeWidth="2"
            />
            <motion.circle
              cx="50%"
              cy="50%"
              r="20"
              fill="none"
              stroke={color}
              strokeWidth="2"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              initial={{ strokeDashoffset: circumference }}
              animate={{ strokeDashoffset }}
              transition={{ duration: 0.1 }}
              style={{
                filter: `drop-shadow(0 0 4px ${color}40)`,
              }}
            />
          </svg>

          {/* Icon */}
          <div className="absolute inset-0 flex items-center justify-center" style={{ zIndex: 2 }}>
            <motion.div
              animate={{
                y: [0, -2, 0],
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            >
              <ChevronUp
                className="w-6 h-6 text-white group-hover:text-opacity-90 transition-colors duration-300"
                style={{
                  filter: `drop-shadow(0 0 4px ${color}60)`,
                }}
              />
            </motion.div>
          </div>

          {/* Pulse effect */}
          <motion.div
            className="absolute inset-0 rounded-full border-2 opacity-0 group-hover:opacity-40"
            style={{
              borderColor: color,
            }}
            animate={{
              scale: [1, 1.5, 1],
              opacity: [0, 0.4, 0],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />

          {/* Sparkle effects */}
          <div className="absolute inset-0 pointer-events-none">
            {Array.from({ length: 4 }).map((_, i) => (
              <motion.div
                key={i}
                className="absolute w-1 h-1 rounded-full opacity-0 group-hover:opacity-60"
                style={{
                  backgroundColor: color,
                  left: `${50 + Math.cos((i * Math.PI * 2) / 4) * 25}%`,
                  top: `${50 + Math.sin((i * Math.PI * 2) / 4) * 25}%`,
                }}
                animate={{
                  scale: [0, 1, 0],
                  opacity: [0, 0.6, 0],
                }}
                transition={{
                  duration: 1.5,
                  repeat: Infinity,
                  delay: i * 0.2,
                  ease: "easeInOut",
                }}
              />
            ))}
          </div>

          {/* Tooltip */}
          <div className="absolute right-full mr-3 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">
            <div className="bg-slate-800 text-white px-3 py-1 rounded-lg text-sm font-medium whitespace-nowrap border border-slate-700">
              Back to top
              <div className="absolute left-full top-1/2 -translate-y-1/2 border-4 border-transparent border-l-slate-800"></div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default ScrollToTop;
