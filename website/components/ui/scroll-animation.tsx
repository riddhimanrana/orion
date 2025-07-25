"use client";
import React, { useEffect, useRef, useState } from "react";
import { motion, useInView, useAnimation } from "motion/react";
import { cn } from "../../lib/utils";

export interface ScrollAnimationProps {
  children: React.ReactNode;
  className?: string;
  animationType?:
    | "fadeIn"
    | "slideUp"
    | "slideDown"
    | "slideLeft"
    | "slideRight"
    | "scaleUp"
    | "rotateIn";
  duration?: number;
  delay?: number;
  threshold?: number;
  triggerOnce?: boolean;
  staggerChildren?: number;
  customAnimation?: {
    hidden: {
      opacity?: number;
      x?: number;
      y?: number;
      scale?: number;
      rotate?: number;
    };
    visible: {
      opacity?: number;
      x?: number;
      y?: number;
      scale?: number;
      rotate?: number;
    };
  };
  viewport?: {
    once?: boolean;
    amount?: number | "some" | "all";
  };
}

const animationVariants = {
  fadeIn: {
    hidden: { opacity: 0 },
    visible: { opacity: 1 },
  },
  slideUp: {
    hidden: { opacity: 0, y: 50 },
    visible: { opacity: 1, y: 0 },
  },
  slideDown: {
    hidden: { opacity: 0, y: -50 },
    visible: { opacity: 1, y: 0 },
  },
  slideLeft: {
    hidden: { opacity: 0, x: 50 },
    visible: { opacity: 1, x: 0 },
  },
  slideRight: {
    hidden: { opacity: 0, x: -50 },
    visible: { opacity: 1, x: 0 },
  },
  scaleUp: {
    hidden: { opacity: 0, scale: 0.8 },
    visible: { opacity: 1, scale: 1 },
  },
  rotateIn: {
    hidden: { opacity: 0, rotate: -10, scale: 0.8 },
    visible: { opacity: 1, rotate: 0, scale: 1 },
  },
};

export const ScrollAnimation = ({
  children,
  className,
  animationType = "fadeIn",
  duration = 0.6,
  delay = 0,

  triggerOnce = true,
  staggerChildren = 0,
  customAnimation,
  viewport = { once: true, amount: 0.3 },
}: ScrollAnimationProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const controls = useAnimation();
  const viewportOptions = {
    once: viewport?.once ?? true,
    amount: viewport?.amount ?? 0.3,
  };
  const isInView = useInView(ref, viewportOptions);

  const selectedAnimation =
    customAnimation ||
    animationVariants[animationType as keyof typeof animationVariants];

  useEffect(() => {
    if (isInView) {
      controls.start("visible");
    } else if (!triggerOnce) {
      controls.start("hidden");
    }
  }, [isInView, controls, triggerOnce]);

  return (
    <motion.div
      ref={ref}
      className={cn(className)}
      initial="hidden"
      animate={controls}
      variants={selectedAnimation}
      transition={{
        duration,
        delay,
        ease: "easeOut",
        staggerChildren,
      }}
    >
      {children}
    </motion.div>
  );
};

export const ScrollStagger = ({
  children,
  className,
  staggerDelay = 0.1,
  animationType = "slideUp",
  duration = 0.6,
  ...props
}: ScrollAnimationProps & { staggerDelay?: number }) => {
  const childrenArray = React.Children.toArray(children);

  return (
    <div className={cn(className)}>
      {childrenArray.map((child, index) => (
        <ScrollAnimation
          key={index}
          animationType={animationType}
          duration={duration}
          delay={index * staggerDelay}
          {...props}
        >
          {child}
        </ScrollAnimation>
      ))}
    </div>
  );
};

export const ScrollReveal = ({
  children,
  className,
  direction = "up",
  distance = 50,
  duration = 0.8,
  ...props
}: {
  children: React.ReactNode;
  className?: string;
  direction?: "up" | "down" | "left" | "right";
  distance?: number;
  duration?: number;
} & Omit<ScrollAnimationProps, "animationType" | "customAnimation">) => {
  const getDirectionAnimation = () => {
    switch (direction) {
      case "up":
        return {
          hidden: { opacity: 0, y: distance },
          visible: { opacity: 1, y: 0 },
        };
      case "down":
        return {
          hidden: { opacity: 0, y: -distance },
          visible: { opacity: 1, y: 0 },
        };
      case "left":
        return {
          hidden: { opacity: 0, x: distance },
          visible: { opacity: 1, x: 0 },
        };
      case "right":
        return {
          hidden: { opacity: 0, x: -distance },
          visible: { opacity: 1, x: 0 },
        };
      default:
        return {
          hidden: { opacity: 0, y: distance },
          visible: { opacity: 1, y: 0 },
        };
    }
  };

  return (
    <ScrollAnimation
      className={className}
      customAnimation={getDirectionAnimation()}
      duration={duration}
      {...props}
    >
      {children}
    </ScrollAnimation>
  );
};

export const ScrollCounter = ({
  from = 0,
  to,
  duration = 2,
  className,
  suffix = "",
  prefix = "",
  decimals = 0,
}: {
  from?: number;
  to: number;
  duration?: number;
  className?: string;
  suffix?: string;
  prefix?: string;
  decimals?: number;
}) => {
  const [count, setCount] = useState(from);
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true });

  useEffect(() => {
    if (isInView) {
      const startTime = Date.now();
      const endTime = startTime + duration * 1000;

      const timer = setInterval(() => {
        const now = Date.now();
        const remaining = endTime - now;
        const progress = Math.min(1, 1 - remaining / (duration * 1000));

        if (progress >= 1) {
          setCount(to);
          clearInterval(timer);
        } else {
          const easedProgress = 1 - Math.pow(1 - progress, 3); // Ease out cubic
          setCount(Math.floor(from + (to - from) * easedProgress));
        }
      }, 16);

      return () => clearInterval(timer);
    }
  }, [isInView, from, to, duration]);

  return (
    <span ref={ref} className={className}>
      {prefix}
      {count.toFixed(decimals)}
      {suffix}
    </span>
  );
};

export const ScrollProgress = ({
  className,
  color = "#3b82f6",
  height = 4,
  showPercentage = false,
}: {
  className?: string;
  color?: string;
  height?: number;
  showPercentage?: boolean;
}) => {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const updateProgress = () => {
      const scrollHeight =
        document.documentElement.scrollHeight - window.innerHeight;
      const scrollTop = window.scrollY;
      const progress = (scrollTop / scrollHeight) * 100;
      setProgress(Math.min(100, Math.max(0, progress)));
    };

    window.addEventListener("scroll", updateProgress);
    updateProgress();

    return () => window.removeEventListener("scroll", updateProgress);
  }, []);

  return (
    <div className={cn("fixed top-0 left-0 w-full z-50", className)}>
      <div
        className="h-full bg-gray-200 dark:bg-gray-800"
        style={{ height: `${height}px` }}
      >
        <motion.div
          className="h-full"
          style={{
            backgroundColor: color,
            height: `${height}px`,
          }}
          initial={{ width: "0%" }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.1 }}
        />
      </div>
      {showPercentage && (
        <div className="absolute top-2 right-4 text-sm font-medium text-gray-600 dark:text-gray-400">
          {Math.round(progress)}%
        </div>
      )}
    </div>
  );
};

export const ScrollIndicator = ({
  className,
  color = "#3b82f6",
  size = 40,
  strokeWidth = 3,
}: {
  className?: string;
  color?: string;
  size?: number;
  strokeWidth?: number;
}) => {
  const [progress, setProgress] = useState(0);
  const circumference = 2 * Math.PI * (size / 2 - strokeWidth);

  useEffect(() => {
    const updateProgress = () => {
      const scrollHeight =
        document.documentElement.scrollHeight - window.innerHeight;
      const scrollTop = window.scrollY;
      const progress = (scrollTop / scrollHeight) * 100;
      setProgress(Math.min(100, Math.max(0, progress)));
    };

    window.addEventListener("scroll", updateProgress);
    updateProgress();

    return () => window.removeEventListener("scroll", updateProgress);
  }, []);

  return (
    <div className={cn("fixed bottom-8 right-8 z-50", className)}>
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={size / 2 - strokeWidth}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-gray-300 dark:text-gray-700"
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={size / 2 - strokeWidth}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={circumference - (progress / 100) * circumference}
          strokeLinecap="round"
          initial={{ strokeDashoffset: circumference }}
          animate={{
            strokeDashoffset: circumference - (progress / 100) * circumference,
          }}
          transition={{ duration: 0.1 }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-xs font-medium" style={{ color }}>
          {Math.round(progress)}%
        </span>
      </div>
    </div>
  );
};
