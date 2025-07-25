"use client";

import React from "react";
import { Avatar, AvatarFallback, AvatarImage } from "./ui/avatar";
import { cn } from "../lib/utils";

/**
 * Props for the MonogramAvatar component
 */
interface MonogramAvatarProps {
  /** The user's full name used to generate the monogram */
  name?: string;
  /** Optional image URL for the avatar */
  imageUrl?: string;
  /** Size preset for the avatar */
  size?: "sm" | "md" | "lg" | "xl";
  /** Additional CSS classes */
  className?: string;
  /** Force showing monogram even if imageUrl is provided */
  forceMonogram?: boolean;
}

const sizeClasses = {
  sm: "w-6 h-6 text-xs",
  md: "w-8 h-8 text-sm",
  lg: "w-10 h-10 text-base",
  xl: "w-12 h-12 text-lg",
};

/**
 * Generates a monogram from a user's name following these rules:
 * - Multiple words: First letter of first word + first letter of second word (e.g., "Bob Smith" → "BS")
 * - Single word: First 2 letters (e.g., "Jill" → "JI", "J" → "J")
 * - Empty/invalid: Returns "U" for User
 *
 * @param name - The user's full name
 * @returns A 1-2 character monogram in uppercase
 *
 * @example
 * generateMonogram("Bob Smith") // "BS"
 * generateMonogram("Jill") // "JI"
 * generateMonogram("J") // "J"
 * generateMonogram("") // "U"
 * generateMonogram("John Michael Smith") // "JM" (only first two words)
 */
function generateMonogram(name: string | undefined): string {
  if (!name || name.trim().length === 0) {
    return "U";
  }

  const trimmedName = name.trim();
  const words = trimmedName.split(/\s+/).filter((word) => word.length > 0);

  if (words.length === 0) {
    return "U";
  }

  if (words.length === 1) {
    // Single word: take first 2 letters
    const word = words[0];
    if (word.length === 1) {
      return word.toUpperCase();
    }
    return word.substring(0, 2).toUpperCase();
  }

  // Multiple words: take first letter of first word + first letter of second word
  const firstInitial = words[0].charAt(0);
  const secondInitial = words[1].charAt(0);

  return (firstInitial + secondInitial).toUpperCase();
}

/**
 * MonogramAvatar component that displays a user avatar with automatic monogram fallback
 *
 * @example
 * ```tsx
 * // Basic usage with name
 * <MonogramAvatar name="Bob Smith" />
 *
 * // With image URL and custom size
 * <MonogramAvatar
 *   name="Jane Doe"
 *   imageUrl="https://example.com/avatar.jpg"
 *   size="lg"
 * />
 *
 * // Single word name
 * <MonogramAvatar name="Jill" size="xl" />
 * ```
 */
export const MonogramAvatar: React.FC<MonogramAvatarProps> = ({
  name,
  imageUrl,
  size = "md",
  className,
  forceMonogram = false,
}) => {
  const monogram = generateMonogram(name);

  return (
    <Avatar className={cn(sizeClasses[size], className)}>
      {!forceMonogram && imageUrl && (
        <AvatarImage src={imageUrl} alt={name || "User"} />
      )}
      <AvatarFallback className="font-medium">{monogram}</AvatarFallback>
    </Avatar>
  );
};

export default MonogramAvatar;
