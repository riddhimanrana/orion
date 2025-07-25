"use client";
import React from "react";
import { motion } from "motion/react";
import { cn } from "../../lib/utils";

interface FeatureCardProps {
  className?: string;
  title: string;
  description: string;
  icon?: React.ReactNode;
  glowColor?: string;
  gradient?: string;
  delay?: number;
  enableHover?: boolean;
  children?: React.ReactNode;
}

export const FeatureCard = ({
  className,
  title,
  description,
  icon,
  glowColor = "#3b82f6",
  gradient = "from-slate-900 to-slate-800",
  delay = 0,
  enableHover = true,
  children,
}: FeatureCardProps) => {
  return (
    <motion.div
      className={cn(
        "relative group p-6 rounded-xl border border-slate-700/50 bg-gradient-to-br",
        gradient,
        "backdrop-blur-sm overflow-hidden",
        className,
      )}
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5, delay }}
      whileHover={
        enableHover
          ? {
              scale: 1.02,
              y: -5,
            }
          : {}
      }
    >
      {/* Animated border glow */}
      <div className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300">
        <div
          className="absolute inset-0 rounded-xl border-2 animate-pulse"
          style={{
            borderColor: glowColor,
            boxShadow: `0 0 20px ${glowColor}40`,
          }}
        />
      </div>

      {/* Background glow effect */}
      <div
        className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-10 transition-opacity duration-300"
        style={{
          background: `radial-gradient(circle at center, ${glowColor} 0%, transparent 70%)`,
        }}
      />

      {/* Shimmer effect */}
      <div className="absolute inset-0 rounded-xl overflow-hidden">
        <motion.div
          className="absolute -inset-4 opacity-0 group-hover:opacity-20 transition-opacity duration-300"
          style={{
            background: `linear-gradient(45deg, transparent 30%, ${glowColor}20 50%, transparent 70%)`,
          }}
          animate={{
            x: ["-100%", "100%"],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: "linear",
          }}
        />
      </div>

      {/* Content */}
      <div className="relative z-10">
        {/* Icon */}
        {icon && (
          <motion.div
            className="mb-4 inline-flex items-center justify-center w-12 h-12 rounded-lg bg-slate-800/50 backdrop-blur-sm"
            style={{
              boxShadow: `0 4px 20px ${glowColor}20`,
            }}
            whileHover={{ rotate: 360 }}
            transition={{ duration: 0.5 }}
          >
            <div className="text-xl" style={{ color: glowColor }}>
              {icon}
            </div>
          </motion.div>
        )}

        {/* Title */}
        <motion.h3
          className="text-xl font-bold text-white mb-3 group-hover:text-opacity-90 transition-colors duration-300"
          style={{
            textShadow: `0 0 10px ${glowColor}30`,
          }}
        >
          {title}
        </motion.h3>

        {/* Description */}
        <motion.p className="text-slate-300 leading-relaxed mb-4 group-hover:text-slate-200 transition-colors duration-300">
          {description}
        </motion.p>

        {/* Additional content */}
        {children && <div className="mt-4">{children}</div>}
      </div>

      {/* Corner accents */}
      <div className="absolute top-2 right-2 w-8 h-8 opacity-20 group-hover:opacity-40 transition-opacity duration-300">
        <div
          className="absolute inset-0 rounded-full animate-pulse"
          style={{
            background: `radial-gradient(circle, ${glowColor} 0%, transparent 70%)`,
          }}
        />
      </div>

      <div className="absolute bottom-2 left-2 w-6 h-6 opacity-20 group-hover:opacity-40 transition-opacity duration-300">
        <div
          className="absolute inset-0 rounded-full animate-pulse"
          style={{
            background: `radial-gradient(circle, ${glowColor} 0%, transparent 70%)`,
            animationDelay: "0.5s",
          }}
        />
      </div>

      {/* Floating particles */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden rounded-xl">
        {Array.from({ length: 3 }).map((_, i) => (
          <motion.div
            key={i}
            className="absolute w-1 h-1 rounded-full opacity-0 group-hover:opacity-60"
            style={{
              backgroundColor: glowColor,
              left: `${20 + i * 30}%`,
              top: `${20 + i * 20}%`,
            }}
            animate={{
              y: [0, -20, 0],
              opacity: [0, 0.6, 0],
            }}
            transition={{
              duration: 3,
              repeat: Infinity,
              delay: i * 0.5,
              ease: "easeInOut",
            }}
          />
        ))}
      </div>
    </motion.div>
  );
};
