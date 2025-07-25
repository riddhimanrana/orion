"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const loadingVariants = cva(
  "flex items-center justify-center",
  {
    variants: {
      variant: {
        default: "text-primary",
        secondary: "text-muted-foreground",
        destructive: "text-destructive",
      },
      size: {
        sm: "h-4 w-4",
        default: "h-6 w-6",
        lg: "h-8 w-8",
        xl: "h-12 w-12",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

interface LoadingProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof loadingVariants> {
  text?: string;
  fullScreen?: boolean;
}

function Loading({
  className,
  variant,
  size,
  text,
  fullScreen = false,
  ...props
}: LoadingProps) {
  if (fullScreen) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
        <div className="flex flex-col items-center space-y-4">
          <Loader2 className={cn(loadingVariants({ variant, size }), "animate-spin")} />
          {text && (
            <p className="text-sm text-muted-foreground animate-pulse">{text}</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex items-center space-x-2", className)} {...props}>
      <Loader2 className={cn(loadingVariants({ variant, size }), "animate-spin")} />
      {text && (
        <span className="text-sm text-muted-foreground animate-pulse">{text}</span>
      )}
    </div>
  );
}

// Skeleton loading component
interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  width?: string | number;
  height?: string | number;
}

function Skeleton({ className, width, height, style, ...props }: SkeletonProps) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-md bg-muted",
        className
      )}
      style={{
        width,
        height,
        ...style,
      }}
      {...props}
    />
  );
}

// Card skeleton for loading states
function CardSkeleton() {
  return (
    <div className="space-y-3">
      <Skeleton height={20} width="60%" />
      <div className="space-y-2">
        <Skeleton height={16} width="100%" />
        <Skeleton height={16} width="80%" />
        <Skeleton height={16} width="90%" />
      </div>
    </div>
  );
}

// Table skeleton for loading states
function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      <div className="flex space-x-4">
        <Skeleton height={16} width="20%" />
        <Skeleton height={16} width="30%" />
        <Skeleton height={16} width="25%" />
        <Skeleton height={16} width="25%" />
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex space-x-4">
          <Skeleton height={14} width="20%" />
          <Skeleton height={14} width="30%" />
          <Skeleton height={14} width="25%" />
          <Skeleton height={14} width="25%" />
        </div>
      ))}
    </div>
  );
}

export { Loading, Skeleton, CardSkeleton, TableSkeleton, loadingVariants };
