"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Card, CardContent } from "./ui/card";

import { Check, User } from "lucide-react";
import { SiGithub } from "react-icons/si";
import { MonogramAvatar } from "./MonogramAvatar";
import { cn } from "../lib/utils";
import { toast } from "sonner";
import {
  getAvailableProfilePictures,
  getDefaultProfilePictureSource,
  updateProfilePicturePreference,
  type ProfilePictureSource,
} from "@/app/account/actions";

interface ProfilePictureSelectorProps {
  user: {
    user_metadata?: {
      full_name?: string;
      profile_picture_source?: ProfilePictureSource;
    };
  } | null;
  currentSource?: ProfilePictureSource;
  onSourceChange?: (source: ProfilePictureSource) => void;
}

interface ProfilePictureOption {
  source: ProfilePictureSource;
  available: boolean;
  imageUrl?: string;
  label: string;
}

const GoogleIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24">
    <path
      fill="currentColor"
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
    />
    <path
      fill="currentColor"
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
    />
    <path
      fill="currentColor"
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
    />
    <path
      fill="currentColor"
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
    />
  </svg>
);

export const ProfilePictureSelector: React.FC<ProfilePictureSelectorProps> = ({
  user,
  currentSource,
  onSourceChange,
}) => {
  const [availableOptions, setAvailableOptions] = useState<
    ProfilePictureOption[]
  >([]);
  const [selectedSource, setSelectedSource] = useState<ProfilePictureSource>(
    currentSource || "monogram",
  );
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);

  const loadAvailableOptions = useCallback(async () => {
    try {
      setLoading(true);
      const options = await getAvailableProfilePictures();
      setAvailableOptions(options);

      // Get the default/current profile picture source
      const defaultSource = await getDefaultProfilePictureSource();
      
      // Verify that the default source is actually available
      const isDefaultAvailable = options.find((opt) => opt.source === defaultSource)?.available;
      
      if (isDefaultAvailable) {
        setSelectedSource(defaultSource);
      } else {
        // Fall back to monogram if the default source is not available
        setSelectedSource("monogram");
      }
    } catch (error) {
      toast.error("Failed to load profile picture options", {
        description: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAvailableOptions();
  }, [loadAvailableOptions]);

  const handleSourceChange = async (source: ProfilePictureSource) => {
    if (source === selectedSource) return;

    try {
      setUpdating(true);
      await updateProfilePicturePreference(source);
      setSelectedSource(source);
      onSourceChange?.(source);
      toast.success("Profile picture updated successfully");
    } catch (error) {
      toast.error("Failed to update profile picture", {
        description: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setUpdating(false);
    }
  };

  const getPreviewImageUrl = (option: ProfilePictureOption) => {
    if (option.source === "monogram") return undefined;
    return option.imageUrl;
  };

  const getOptionIcon = (source: ProfilePictureSource) => {
    switch (source) {
      case "monogram":
        return <User className="w-4 h-4" />;
      case "google":
        return <GoogleIcon />;
      case "github":
        return <SiGithub className="w-4 h-4" />;
      default:
        return <User className="w-4 h-4" />;
    }
  };

  const getShortLabel = (source: ProfilePictureSource) => {
    switch (source) {
      case "monogram":
        return "Default";
      case "google":
        return "Google";
      case "github":
        return "GitHub";
      default:
        return "Default";
    }
  };

  const getFullLabel = (option: ProfilePictureOption) => {
    return option.label;
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center space-x-2">
          <div className="w-16 h-16 rounded-full bg-muted animate-pulse" />
          <div>
            <div className="h-4 w-32 bg-muted rounded animate-pulse mb-2" />
            <div className="h-3 w-48 bg-muted rounded animate-pulse" />
          </div>
        </div>
        <div className="grid grid-cols-3 sm:grid-cols-2 lg:grid-cols-3 gap-2 sm:gap-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 sm:h-32 bg-muted rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Current Selection Preview */}
      <div className="flex items-center space-x-4">
        <MonogramAvatar
          name={user?.user_metadata?.full_name}
          imageUrl={getPreviewImageUrl(
            availableOptions.find((opt) => opt.source === selectedSource) ||
              availableOptions[0],
          )}
          size="xl"
          className="w-16 h-16 text-xl"
          forceMonogram={selectedSource === "monogram"}
        />
        <div>
          <p className="font-medium text-sm text-muted-foreground mb-1">
            Profile Picture
          </p>
          <p className="text-xs text-muted-foreground">
            <span className="sm:hidden">{getShortLabel(selectedSource)} Profile Picture</span>
            <span className="hidden sm:inline">
              {availableOptions.find((opt) => opt.source === selectedSource)?.label || "Default Monogram"}
            </span>
          </p>
        </div>
      </div>

      {/* Source Selection */}
      <div 
        className={cn(
          "grid gap-2 sm:gap-3",
          // Mobile: Responsive grid based on available options
          availableOptions.length === 1 ? "grid-cols-1" :
          availableOptions.length === 2 ? "grid-cols-2" : 
          "grid-cols-3",
          // Desktop: Always show all in a row or 2x2 grid if more than 3
          "sm:grid-cols-2 lg:grid-cols-3"
        )}
      >
        {availableOptions.map((option) => (
          <Card
            key={option.source}
            className={cn(
              "cursor-pointer transition-all hover:shadow-md",
              selectedSource === option.source
                ? "ring-2 ring-primary border-primary"
                : "hover:border-muted-foreground/50",
              !option.available && "opacity-50 cursor-not-allowed",
            )}
            onClick={() =>
              option.available && !updating && handleSourceChange(option.source)
            }
          >
            <CardContent className="p-3 sm:p-4 space-y-2 sm:space-y-3">
              {/* Mobile Layout */}
              <div className="sm:hidden flex flex-col items-center space-y-2">
                <div className="relative flex items-center justify-center">
                  <MonogramAvatar
                    name={user?.user_metadata?.full_name}
                    imageUrl={getPreviewImageUrl(option)}
                    size="md"
                    className="w-10 h-10"
                    forceMonogram={option.source === "monogram"}
                  />
                  {selectedSource === option.source && (
                    <Check className="w-3 h-3 text-primary absolute translate-x-2 -translate-y-2" />
                  )}
                </div>
                
                <div className="flex items-center space-x-1">
                  {getOptionIcon(option.source)}
                  <span className="font-medium text-xs text-center">
                    {getShortLabel(option.source)}
                  </span>
                </div>

                {!option.available && (
                  <p className="text-xs text-muted-foreground text-center leading-tight">
                    Connect account
                  </p>
                )}
              </div>

              {/* Desktop Layout */}
              <div className="hidden sm:block space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    {getOptionIcon(option.source)}
                    <span className="font-medium text-sm">{getFullLabel(option)}</span>
                  </div>
                  {selectedSource === option.source && (
                    <Check className="w-4 h-4 text-primary" />
                  )}
                </div>

                <div className="flex justify-center">
                  <MonogramAvatar
                    name={user?.user_metadata?.full_name}
                    imageUrl={getPreviewImageUrl(option)}
                    size="lg"
                    className="w-12 h-12"
                    forceMonogram={option.source === "monogram"}
                  />
                </div>

                {!option.available && (
                  <p className="text-xs text-muted-foreground text-center">
                    Connect your {option.source} account to use this option
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {updating && (
        <div className="text-center">
          <p className="text-sm text-muted-foreground">
            Updating profile picture...
          </p>
        </div>
      )}
    </div>
  );
};

export default ProfilePictureSelector;
