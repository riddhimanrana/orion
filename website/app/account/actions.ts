"use server";

import { createClient } from "@/utils/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

export async function getUserIdentities() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    throw new Error("User not authenticated");
  }

  const { data: identities, error } = await supabase.auth.getUserIdentities();

  if (error) {
    throw new Error(`Failed to fetch identities: ${error.message}`);
  }

  return identities?.identities || [];
}

export async function linkOAuthProvider(provider: "google" | "github") {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    throw new Error("User not authenticated");
  }

  const { data, error } = await supabase.auth.linkIdentity({
    provider: provider,
  });

  if (error) {
    throw new Error(`Failed to link ${provider}: ${error.message}`);
  }

  // The user will be redirected to the OAuth provider
  if (data?.url) {
    redirect(data.url);
  }

  return { success: true };
}

export async function unlinkOAuthProvider(provider: "google" | "github") {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    throw new Error("User not authenticated");
  }

  // Get all identities first
  const { data: identities, error: identitiesError } =
    await supabase.auth.getUserIdentities();

  if (identitiesError) {
    throw new Error(`Failed to fetch identities: ${identitiesError.message}`);
  }

  // Find the specific provider identity
  const providerIdentity = identities?.identities?.find(
    (identity) => identity.provider === provider,
  );

  if (!providerIdentity) {
    throw new Error(`${provider} identity not found`);
  }

  // Check if user has at least 2 identities (requirement for unlinking)
  if ((identities?.identities?.length || 0) < 2) {
    throw new Error(
      "Cannot unlink - you must have at least one other login method",
    );
  }

  const { error } = await supabase.auth.unlinkIdentity(providerIdentity);

  if (error) {
    throw new Error(`Failed to unlink ${provider}: ${error.message}`);
  }

  revalidatePath("/account");
  return { success: true };
}

export async function changeUserEmail(newEmail: string) {
  const supabase = await createClient();

  // Get current user
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    throw new Error("User not authenticated");
  }

  // Validate email format
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(newEmail)) {
    throw new Error("Invalid email format");
  }

  // Normalize email
  const normalizedEmail = newEmail.toLowerCase().trim();

  // Check if it's the same as current email
  if (user.email === normalizedEmail) {
    throw new Error("This is already your current email address");
  }

  // Note: We'll let Supabase handle duplicate email checking during the update
  // for better security and to avoid permission issues with auth.users table

  // Attempt to update the email
  const { error } = await supabase.auth.updateUser(
    { email: normalizedEmail },
    {
      emailRedirectTo: `${process.env.NEXT_PUBLIC_SITE_URL}/auth/confirm-email-change`,
    },
  );

  if (error) {
    // Handle specific Supabase errors
    if (
      error.message.includes("already registered") ||
      error.message.includes("already exists")
    ) {
      throw new Error("An account with this email address already exists");
    } else if (error.message.includes("invalid email")) {
      throw new Error("Invalid email format");
    } else if (error.message.includes("rate limit")) {
      throw new Error(
        "Too many requests. Please wait a few minutes before trying again",
      );
    } else {
      throw new Error(`Failed to update email: ${error.message}`);
    }
  }

  revalidatePath("/account");
  return {
    success: true,
    message:
      "Email change initiated. Please check both your old and new email addresses for confirmation links.",
  };
}

export async function updateUserProfile(formData: FormData) {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    throw new Error("User not authenticated");
  }

  const fullName = formData.get("fullName") as string;

  const updates: {
    data?: { full_name: string };
  } = {};

  if (fullName && fullName.trim() !== "") {
    updates.data = { full_name: fullName.trim() };
  }

  if (Object.keys(updates).length === 0) {
    return { success: true, message: "No changes to update" };
  }

  const { error } = await supabase.auth.updateUser(updates);

  if (error) {
    throw new Error(`Failed to update profile: ${error.message}`);
  }

  revalidatePath("/account");
  return { success: true, message: "Profile updated successfully" };
}

export async function deleteUserAccount(confirmationText: string) {
  const supabase = await createClient();

  if (confirmationText !== "DELETE") {
    throw new Error("Invalid confirmation text");
  }

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    throw new Error("User not authenticated");
  }

  try {
    // Check for required environment variables
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

    if (!supabaseUrl) {
      throw new Error("Supabase URL not configured");
    }

    if (!serviceRoleKey) {
      throw new Error(
        "Service role key not configured. Account deletion requires admin privileges.",
      );
    }

    // Create admin client with service role key
    const adminClient = createAdminClient(supabaseUrl, serviceRoleKey);

    // First sign out to clear session cookies before deletion
    await supabase.auth.signOut();

    // Delete the user using admin API
    const { error } = await adminClient.auth.admin.deleteUser(user.id);

    if (error) {
      throw new Error(`Failed to delete account: ${error.message}`);
    }

    // Redirect to home page after successful deletion
    // Note: User session is automatically invalidated by deleteUser
    redirect("/");
  } catch (error) {
    // If it's already an Error instance, throw it as is to preserve the message
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("An unexpected error occurred while deleting the account");
  }
}

// Alternative safer approach for account deletion using a database function
export async function requestAccountDeletion(confirmationText: string) {
  // This function is kept for backward compatibility
  // Use deleteUserAccount instead for direct admin API deletion
  return deleteUserAccount(confirmationText);
}

function validatePassword(password: string): {
  isValid: boolean;
  errors: string[];
} {
  const errors: string[] = [];

  if (password.length < 8) {
    errors.push("Password must be at least 8 characters long");
  }

  if (!/[A-Z]/.test(password)) {
    errors.push("Password must contain at least one uppercase letter");
  }

  if (!/[a-z]/.test(password)) {
    errors.push("Password must contain at least one lowercase letter");
  }

  if (!/\d/.test(password)) {
    errors.push("Password must contain at least one number");
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}

export async function hasPassword() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    throw new Error("User not authenticated");
  }

  const { data: identities, error } = await supabase.auth.getUserIdentities();

  if (error) {
    throw new Error(`Failed to fetch identities: ${error.message}`);
  }

  // Check if user has email identity (password-based login)
  const hasEmailIdentity = identities?.identities?.some(
    (identity) => identity.provider === "email",
  );

  // Additional check: if user has email and email_confirmed_at, they likely can use password auth
  // This helps catch cases where password was set but email identity wasn't properly linked
  const hasEmailAndConfirmed = user.email && user.email_confirmed_at;

  // Check if user has password flag in user metadata (indicates password is set)
  const hasPasswordFlag = user.user_metadata?.has_password;

  return !!(hasEmailIdentity || (hasEmailAndConfirmed && hasPasswordFlag));
}

export async function setUserPassword(password: string) {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user || !user.email) {
    throw new Error("User not authenticated or email not available");
  }

  // Check if user already has a password
  const hasPasswordAuth = await hasPassword();

  if (hasPasswordAuth) {
    throw new Error("User already has password authentication enabled");
  }

  const validation = validatePassword(password);
  if (!validation.isValid) {
    throw new Error(validation.errors.join(". "));
  }

  const { error } = await supabase.auth.updateUser({
    password: password,
    data: {
      ...user.user_metadata,
      has_password: true,
    },
  });

  if (error) {
    throw new Error(`Failed to set password: ${error.message}`);
  }

  // Force refresh user session to ensure changes are reflected
  const { error: refreshError } = await supabase.auth.refreshSession();
  if (refreshError) {
    console.warn("Could not refresh session:", refreshError.message);
  }

  revalidatePath("/account");
  return { success: true, message: "Password set successfully" };
}

export async function changeUserPassword(
  currentPassword: string,
  newPassword: string,
) {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user || !user.email) {
    throw new Error("User not authenticated");
  }

  // Check if user has password authentication
  const hasPasswordAuth = await hasPassword();

  if (!hasPasswordAuth) {
    throw new Error("User does not have password authentication enabled");
  }

  // Verify current password by attempting to sign in
  const { error: signInError } = await supabase.auth.signInWithPassword({
    email: user.email,
    password: currentPassword,
  });

  if (signInError) {
    if (
      signInError.message.includes("Invalid login credentials") ||
      signInError.message.includes("Invalid email or password")
    ) {
      throw new Error("Current password is incorrect");
    }
    throw new Error(
      `Failed to verify current password: ${signInError.message}`,
    );
  }

  const validation = validatePassword(newPassword);
  if (!validation.isValid) {
    throw new Error(validation.errors.join(". "));
  }

  // Check that new password is different from current
  if (currentPassword === newPassword) {
    throw new Error("New password must be different from current password");
  }

  // Update to new password
  const { error } = await supabase.auth.updateUser({
    password: newPassword,
    data: {
      ...user.user_metadata,
      has_password: true,
    },
  });

  if (error) {
    if (
      error.message.includes("reauthenticate") ||
      error.message.includes("recent") ||
      error.message.includes("session")
    ) {
      throw new Error(
        "For security reasons, please sign out and sign back in, then try changing your password again",
      );
    }
    throw new Error(`Failed to update password: ${error.message}`);
  }

  revalidatePath("/account");
  return { success: true, message: "Password updated successfully" };
}

export type ProfilePictureSource = "monogram" | "google" | "github";

export async function getAvailableProfilePictures() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    throw new Error("User not authenticated");
  }

  const { data: identities, error } = await supabase.auth.getUserIdentities();

  if (error) {
    throw new Error(`Failed to fetch identities: ${error.message}`);
  }

  const availableSources: {
    source: ProfilePictureSource;
    available: boolean;
    imageUrl?: string;
    label: string;
  }[] = [
    {
      source: "monogram",
      available: true,
      label: "Default Monogram",
    },
  ];

  // Check for Google identity
  const googleIdentity = identities?.identities?.find(
    (identity) => identity.provider === "google",
  );
  if (googleIdentity) {
    availableSources.push({
      source: "google",
      available: true,
      imageUrl: googleIdentity.identity_data?.avatar_url,
      label: "Google Profile Picture",
    });
  }

  // Check for GitHub identity
  const githubIdentity = identities?.identities?.find(
    (identity) => identity.provider === "github",
  );
  if (githubIdentity) {
    availableSources.push({
      source: "github",
      available: true,
      imageUrl: githubIdentity.identity_data?.avatar_url,
      label: "GitHub Profile Picture",
    });
  }

  return availableSources;
}

export async function getDefaultProfilePictureSource(): Promise<ProfilePictureSource> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return "monogram";
  }

  // If user has already set a preference, use it
  const userPreference = user.user_metadata?.profile_picture_source as ProfilePictureSource;
  if (userPreference) {
    return userPreference;
  }

  // If no preference is set, auto-detect based on OAuth identities
  const { data: identities } = await supabase.auth.getUserIdentities();

  if (identities?.identities) {
    // Prioritize Google over GitHub if both are available
    const googleIdentity = identities.identities.find(
      (identity) => identity.provider === "google",
    );
    if (googleIdentity?.identity_data?.avatar_url) {
      return "google";
    }

    const githubIdentity = identities.identities.find(
      (identity) => identity.provider === "github",
    );
    if (githubIdentity?.identity_data?.avatar_url) {
      return "github";
    }
  }

  return "monogram";
}

export async function updateProfilePicturePreference(
  source: ProfilePictureSource,
) {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    throw new Error("User not authenticated");
  }

  // Get available sources to validate the selection
  const availableSources = await getAvailableProfilePictures();
  const selectedSource = availableSources.find((s) => s.source === source);

  if (!selectedSource?.available) {
    throw new Error(`${source} profile picture is not available`);
  }

  // Update user metadata with the preferred source
  const { error } = await supabase.auth.updateUser({
    data: {
      ...user.user_metadata,
      profile_picture_source: source,
    },
  });

  if (error) {
    throw new Error(
      `Failed to update profile picture preference: ${error.message}`,
    );
  }

  revalidatePath("/account");
  return { success: true, message: "Profile picture preference updated" };
}

export async function getProfilePictureUrl(
  user: {
    user_metadata?: {
      profile_picture_source?: ProfilePictureSource;
      avatar_url?: string;
    };
  } | null,
): Promise<string | undefined> {
  if (!user) return undefined;

  let preferredSource = user.user_metadata
    ?.profile_picture_source as ProfilePictureSource;

  // If no preference is set, use the default detection logic
  if (!preferredSource) {
    preferredSource = await getDefaultProfilePictureSource();
  }

  if (preferredSource === "monogram") {
    return undefined; // Will show monogram
  }

  // For OAuth providers, we need to get the identity data
  try {
    const supabase = await createClient();
    const { data: identities } = await supabase.auth.getUserIdentities();

    if (preferredSource === "google") {
      const googleIdentity = identities?.identities?.find(
        (identity) => identity.provider === "google",
      );
      return googleIdentity?.identity_data?.avatar_url;
    }

    if (preferredSource === "github") {
      const githubIdentity = identities?.identities?.find(
        (identity) => identity.provider === "github",
      );
      return githubIdentity?.identity_data?.avatar_url;
    }
  } catch (error) {
    console.warn("Failed to fetch identity data for profile picture:", error);
  }

  return undefined; // Fall back to monogram
}

export type SubscriptionTier = "free" | "pro";

export async function getUserSubscriptionTier(): Promise<SubscriptionTier> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    throw new Error("User not authenticated");
  }

  // Check user metadata for subscription tier, default to "free"
  const tier = user.user_metadata?.subscription_tier as SubscriptionTier;
  return tier || "free";
}

export async function toggleSubscriptionTier(): Promise<{
  success: boolean;
  tier: SubscriptionTier;
  message: string;
}> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    throw new Error("User not authenticated");
  }

  // Get current tier
  const currentTier = await getUserSubscriptionTier();
  const newTier: SubscriptionTier = currentTier === "free" ? "pro" : "free";

  // Update user metadata with new tier
  const { error } = await supabase.auth.updateUser({
    data: {
      ...user.user_metadata,
      subscription_tier: newTier,
    },
  });

  if (error) {
    throw new Error(`Failed to update subscription: ${error.message}`);
  }

  revalidatePath("/account");
  revalidatePath("/dashboard");

  return {
    success: true,
    tier: newTier,
    message: `Successfully ${newTier === "pro" ? "upgraded to" : "downgraded from"} Orion Pro`,
  };
}
