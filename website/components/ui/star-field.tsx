"use client";
import React, { useEffect, useState } from "react";
import { motion } from "motion/react";
import { cn } from "../../lib/utils";

interface Star {
  id: number;
  x: number;
  y: number;
  size: number;
  opacity: number;
  twinkleDelay: number;
  twinkleDuration: number;
  color: string;
}

interface StarFieldProps {
  className?: string;
  density?: number;
  colors?: string[];
  minSize?: number;
  maxSize?: number;
  minOpacity?: number;
  maxOpacity?: number;
  enableTwinkling?: boolean;
  enableShooting?: boolean;
}

export const StarField = ({
  className,
  density = 200,
  colors = ["#ffffff", "#e0e7ff", "#dbeafe", "#fef3c7", "#fed7d7"],
  minSize = 1,
  maxSize = 3,
  minOpacity = 0.3,
  maxOpacity = 1,
  enableTwinkling = true,
  enableShooting = true,
}: StarFieldProps) => {
  const [stars, setStars] = useState<Star[]>([]);
  const [shootingStars, setShootingStars] = useState<number[]>([]);

  useEffect(() => {
    const generateStars = () => {
      const newStars: Star[] = [];
      for (let i = 0; i < density; i++) {
        newStars.push({
          id: i,
          x: Math.random() * 100,
          y: Math.random() * 100,
          size: Math.random() * (maxSize - minSize) + minSize,
          opacity: Math.random() * (maxOpacity - minOpacity) + minOpacity,
          twinkleDelay: Math.random() * 5,
          twinkleDuration: Math.random() * 3 + 2,
          color: colors[Math.floor(Math.random() * colors.length)],
        });
      }
      setStars(newStars);
    };

    generateStars();
  }, [density, colors, minSize, maxSize, minOpacity, maxOpacity]);

  useEffect(() => {
    if (!enableShooting) return;

    const shootingInterval = setInterval(
      () => {
        const newShootingStar = Date.now();
        setShootingStars((prev) => [...prev, newShootingStar]);

        // Remove shooting star after animation
        setTimeout(() => {
          setShootingStars((prev) =>
            prev.filter((star) => star !== newShootingStar),
          );
        }, 3000);
      },
      Math.random() * 5000 + 2000,
    );

    return () => clearInterval(shootingInterval);
  }, [enableShooting]);

  return (
    <div className={cn("absolute inset-0 overflow-hidden", className)}>
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900" />

      {/* Stars */}
      {stars.map((star) => (
        <motion.div
          key={star.id}
          className="absolute rounded-full"
          style={{
            left: `${star.x}%`,
            top: `${star.y}%`,
            width: `${star.size}px`,
            height: `${star.size}px`,
            backgroundColor: star.color,
            boxShadow: `0 0 ${star.size * 2}px ${star.color}`,
          }}
          initial={{ opacity: star.opacity }}
          animate={
            enableTwinkling
              ? {
                  opacity: [star.opacity, star.opacity * 0.3, star.opacity],
                  scale: [1, 1.2, 1],
                }
              : { opacity: star.opacity }
          }
          transition={
            enableTwinkling
              ? {
                  duration: star.twinkleDuration,
                  repeat: Infinity,
                  delay: star.twinkleDelay,
                  ease: "easeInOut",
                }
              : {}
          }
        />
      ))}

      {/* Shooting stars */}
      {enableShooting &&
        shootingStars.map((shootingStar) => (
          <motion.div
            key={shootingStar}
            className="absolute h-0.5 bg-gradient-to-r from-white to-transparent rounded-full"
            style={{
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
              width: "100px",
              transformOrigin: "left center",
              rotate: `${Math.random() * 45 - 22.5}deg`,
            }}
            initial={{
              opacity: 0,
              scaleX: 0,
              x: -100,
            }}
            animate={{
              opacity: [0, 1, 0],
              scaleX: [0, 1, 0],
              x: [0, 200],
            }}
            transition={{
              duration: 2,
              ease: "easeOut",
            }}
          />
        ))}

      {/* Constellation lines (subtle) */}
      <svg className="absolute inset-0 w-full h-full" style={{ zIndex: 1 }}>
        <defs>
          <linearGradient
            id="constellation-gradient"
            x1="0%"
            y1="0%"
            x2="100%"
            y2="100%"
          >
            <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.1" />
            <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.05" />
          </linearGradient>
        </defs>
        {stars.slice(0, 20).map((star, index) => {
          const nextStar = stars[index + 1];
          if (!nextStar) return null;

          return (
            <motion.line
              key={`line-${star.id}`}
              x1={`${star.x}%`}
              y1={`${star.y}%`}
              x2={`${nextStar.x}%`}
              y2={`${nextStar.y}%`}
              stroke="url(#constellation-gradient)"
              strokeWidth="0.5"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 0.3 }}
              transition={{
                duration: 3,
                delay: index * 0.2,
                ease: "easeInOut",
              }}
            />
          );
        })}
      </svg>
    </div>
  );
};
