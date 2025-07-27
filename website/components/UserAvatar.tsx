"use client";

import React from "react";
import { MonogramAvatar } from "./MonogramAvatar";
import { useProfilePicture } from "@/hooks/use-profile-picture";

interface UserAvatarProps {
  /** The user object */
  user: {
    user_metadata?: {
      full_name?: string;
      profile_picture_source?: "monogram" | "google" | "github";
    };
  } | null;
  /** Size preset for the avatar */
  size?: "sm" | "md" | "lg" | "xl";
  /** Additional CSS classes */
  className?: string;
  /** Force showing monogram even if imageUrl is available */
  forceMonogram?: boolean;
}

/**
 * UserAvatar component that automatically handles profile picture preferences
 * and displays the correct image source based on user settings.
 *
 * @example
 * ```tsx
 * // Basic usage
 * <UserAvatar user={user} />
 *
 * // With custom size and styling
 * <UserAvatar
 *   user={user}
 *   size="lg"
 *   className="border-2 border-primary"
 * />
 *
 * // Force monogram display
 * <UserAvatar user={user} forceMonogram />
 * ```
 */
export const UserAvatar: React.FC<UserAvatarProps> = ({
  user,
  size = "md",
  className,
  forceMonogram = false,
}) => {
  const { imageUrl, isLoading } = useProfilePicture(user);

  // Show a loading placeholder if still loading
  if (isLoading) {
    return (
      <div
        className={`animate-pulse bg-muted rounded-full ${className || ""}`}
        style={{
          width:
            size === "sm"
              ? "1.5rem"
              : size === "md"
                ? "2rem"
                : size === "lg"
                  ? "2.5rem"
                  : "3rem",
          height:
            size === "sm"
              ? "1.5rem"
              : size === "md"
                ? "2rem"
                : size === "lg"
                  ? "2.5rem"
                  : "3rem",
        }}
      />
    );
  }

  return (
    <MonogramAvatar
      name={user?.user_metadata?.full_name}
      imageUrl={forceMonogram ? undefined : imageUrl}
      size={size}
      className={className}
      forceMonogram={forceMonogram}
    />
  );
};

export default UserAvatar;
