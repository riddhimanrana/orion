"use client";
import React, { useEffect, useState, useRef, useCallback } from "react";
import { useTheme } from "next-themes";
import { cn } from "../../lib/utils";

interface Node {
  id: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
}

interface SimpleNodesProps {
  className?: string;
  baseNodeDensity?: number; // nodes per 100k pixels
  speed?: number;
  jitter?: number;
  maxSpeed?: number;
  baseNodeSize?: number;
  baseConnectionDistance?: number;
  enableConnections?: boolean;
}

export const SimpleNodes = ({
  className,
  baseNodeDensity = 3.5, // nodes per 100k pixels
  speed = 2.0,
  jitter = 0.1,
  maxSpeed = 2.5,
  baseNodeSize = 3,
  baseConnectionDistance = 180,
  enableConnections = true,
}: SimpleNodesProps) => {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [actualTheme, setActualTheme] = useState<"light" | "dark">("dark");
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | null>(null);
  const { theme, systemTheme } = useTheme();

  // Calculate responsive values based on screen size
  const getResponsiveValues = useCallback(
    (width: number, height: number) => {
      const area = width * height;
      const nodeCount = Math.floor((area / 100000) * baseNodeDensity);
      const scaleFactor = Math.min(width, height) / 1000; // scale based on smaller dimension

      return {
        nodeCount: Math.max(50, Math.min(400, nodeCount)), // clamp between 50-400
        nodeSize: Math.max(1, baseNodeSize * scaleFactor),
        connectionDistance: Math.max(
          80,
          Math.min(250, baseConnectionDistance * scaleFactor),
        ),
      };
    },
    [baseNodeDensity, baseNodeSize, baseConnectionDistance],
  );

  // Determine actual theme (handle system theme properly)
  useEffect(() => {
    const determineTheme = () => {
      if (theme === "system") {
        // Use systemTheme from next-themes if available, otherwise detect manually
        if (systemTheme) {
          setActualTheme(systemTheme as "light" | "dark");
        } else {
          // Fallback: manually check system preference
          const isDark = window.matchMedia(
            "(prefers-color-scheme: dark)",
          ).matches;
          setActualTheme(isDark ? "dark" : "light");
        }
      } else {
        setActualTheme((theme as "light" | "dark") || "dark");
      }
    };

    determineTheme();

    // Listen for system theme changes
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = () => {
      if (theme === "system") {
        setActualTheme(mediaQuery.matches ? "dark" : "light");
      }
    };

    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, [theme, systemTheme]);

  // Initialize dimensions with debounced resize
  useEffect(() => {
    let resizeTimeout: NodeJS.Timeout;

    const updateDimensions = () => {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(() => {
        if (containerRef.current) {
          const { clientWidth, clientHeight } = containerRef.current;
          setDimensions({ width: clientWidth, height: clientHeight });
        }
      }, 100);
    };

    updateDimensions();
    window.addEventListener("resize", updateDimensions);
    return () => {
      window.removeEventListener("resize", updateDimensions);
      clearTimeout(resizeTimeout);
    };
  }, []);

  // Initialize nodes with responsive values
  useEffect(() => {
    if (dimensions.width === 0 || dimensions.height === 0) return;

    const { nodeCount, nodeSize } = getResponsiveValues(
      dimensions.width,
      dimensions.height,
    );
    const margin = nodeSize * 2;

    const newNodes: Node[] = Array.from({ length: nodeCount }, (_, i) => ({
      id: i,
      x: Math.random() * (dimensions.width - margin * 2) + margin,
      y: Math.random() * (dimensions.height - margin * 2) + margin,
      vx: (Math.random() - 0.5) * speed * (0.5 + Math.random()),
      vy: (Math.random() - 0.5) * speed * (0.5 + Math.random()),
      size: nodeSize + Math.random() * nodeSize * 0.5,
    }));

    setNodes(newNodes);
  }, [dimensions, getResponsiveValues, speed]);

  // Canvas rendering function
  const render = useCallback(
    (ctx: CanvasRenderingContext2D, currentNodes: Node[]) => {
      const { width, height } = dimensions;
      const { connectionDistance } = getResponsiveValues(width, height);

      // Clear canvas
      ctx.clearRect(0, 0, width, height);

      // Set colors based on theme
      const isDark = actualTheme === "dark";
      const nodeColor = isDark ? "#ffffff" : "#000000";
      const connectionColor = isDark ? "#ffffff" : "#000000";

      // Draw connections (if enabled)
      if (enableConnections) {
        ctx.strokeStyle = connectionColor;
        ctx.lineWidth = 1;

        for (let i = 0; i < currentNodes.length; i++) {
          const node = currentNodes[i];
          for (let j = i + 1; j < currentNodes.length; j++) {
            const otherNode = currentNodes[j];
            const dx = node.x - otherNode.x;
            const dy = node.y - otherNode.y;
            const distance = Math.sqrt(dx * dx + dy * dy);

            if (distance < connectionDistance) {
              const opacity =
                Math.max(0, 1 - distance / connectionDistance) * 0.1;
              ctx.globalAlpha = opacity;
              ctx.beginPath();
              ctx.moveTo(node.x, node.y);
              ctx.lineTo(otherNode.x, otherNode.y);
              ctx.stroke();
            }
          }
        }
      }

      // Draw nodes
      ctx.fillStyle = nodeColor;
      ctx.globalAlpha = 0.6;

      currentNodes.forEach((node) => {
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.size, 0, Math.PI * 2);
        ctx.fill();
      });

      ctx.globalAlpha = 1;
    },
    [dimensions, getResponsiveValues, enableConnections, actualTheme],
  );

  // Optimized animation loop
  useEffect(() => {
    if (nodes.length === 0 || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Set canvas size
    canvas.width = dimensions.width;
    canvas.height = dimensions.height;

    let lastTime = 0;
    const targetFPS = 60;
    const frameInterval = 1000 / targetFPS;

    const animate = (currentTime: number) => {
      // Throttle to target FPS
      if (currentTime - lastTime < frameInterval) {
        animationRef.current = requestAnimationFrame(animate);
        return;
      }
      lastTime = currentTime;

      setNodes((prevNodes) => {
        const updatedNodes = prevNodes.map((node) => {
          let newX = node.x + node.vx;
          let newY = node.y + node.vy;
          let newVx = node.vx;
          let newVy = node.vy;

          // Bounce off edges with some padding
          const padding = node.size;
          if (newX <= padding || newX >= dimensions.width - padding) {
            newVx = -newVx;
            newX = Math.max(
              padding,
              Math.min(dimensions.width - padding, newX),
            );
          }
          if (newY <= padding || newY >= dimensions.height - padding) {
            newVy = -newVy;
            newY = Math.max(
              padding,
              Math.min(dimensions.height - padding, newY),
            );
          }

          // Apply Brownian jitter
          newVx += (Math.random() - 0.5) * jitter;
          newVy += (Math.random() - 0.5) * jitter;

          // Cap to maxSpeed
          const speedMag = Math.sqrt(newVx * newVx + newVy * newVy);
          if (speedMag > maxSpeed) {
            newVx = (newVx / speedMag) * maxSpeed;
            newVy = (newVy / speedMag) * maxSpeed;
          }

          return {
            ...node,
            x: newX,
            y: newY,
            vx: newVx,
            vy: newVy,
          };
        });

        // Render on next frame to avoid blocking
        requestAnimationFrame(() => render(ctx, updatedNodes));

        return updatedNodes;
      });

      animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [nodes.length, dimensions, jitter, maxSpeed, render]);

  return (
    <div
      ref={containerRef}
      className={cn(
        "absolute inset-0 overflow-hidden pointer-events-none",
        className,
      )}
    >
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full"
        style={{ imageRendering: "crisp-edges" }}
      />
    </div>
  );
};
