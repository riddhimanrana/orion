"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import {
  getProfilePictureUrl,
  getDefaultProfilePictureSource,
  type ProfilePictureSource,
} from "@/app/account/actions";

interface UseProfilePictureReturn {
  imageUrl: string | undefined;
  isLoading: boolean;
  source: ProfilePictureSource;
  refresh: () => Promise<void>;
}

// Simple in-memory cache for profile pictures
const profilePictureCache = new Map<string, { url: string | undefined; timestamp: number }>();
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

export function useProfilePicture(
  user: {
    user_metadata?: {
      profile_picture_source?: ProfilePictureSource;
      full_name?: string;
    };
  } | null,
): UseProfilePictureReturn {
  const [imageUrl, setImageUrl] = useState<string | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(true);
  const [source, setSource] = useState<ProfilePictureSource>("monogram");

  // Create a stable cache key based on user ID and preferred source
  const cacheKey = useMemo(() => {
    if (!user) return null;
    const userId = (user as { id?: string })?.id || 'unknown';
    const preferredSource = user.user_metadata?.profile_picture_source || "auto";
    return `${userId}-${preferredSource}`;
  }, [user]);

  const loadProfilePicture = useCallback(async () => {
    if (!user || !cacheKey) {
      setImageUrl(undefined);
      setSource("monogram");
      setIsLoading(false);
      return;
    }

    // Get the user's preferred source or auto-detect
    const preferredSource =
      (user.user_metadata?.profile_picture_source as ProfilePictureSource) ||
      await getDefaultProfilePictureSource();
      
    setSource(preferredSource);

    // Check cache first
    const cached = profilePictureCache.get(cacheKey);
    const now = Date.now();
    
    if (cached && (now - cached.timestamp) < CACHE_DURATION) {
      setImageUrl(cached.url);
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);

      // Get the appropriate image URL
      const url = await getProfilePictureUrl(user);
      
      // Cache the result
      profilePictureCache.set(cacheKey, { url, timestamp: now });
      
      setImageUrl(url);
    } catch (error) {
      console.warn("Failed to load profile picture:", error);
      setImageUrl(undefined);
      setSource("monogram");
      
      // Cache the failure to prevent repeated attempts
      profilePictureCache.set(cacheKey, { url: undefined, timestamp: now });
    } finally {
      setIsLoading(false);
    }
  }, [user, cacheKey]);

  useEffect(() => {
    loadProfilePicture();
  }, [loadProfilePicture]);

  const refresh = async () => {
    // Clear cache for this user when refreshing
    if (cacheKey) {
      profilePictureCache.delete(cacheKey);
    }
    await loadProfilePicture();
  };

  return {
    imageUrl,
    isLoading,
    source,
    refresh,
  };
}
