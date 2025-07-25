"use server";

import { z } from "zod";
import { createClient } from "@/utils/supabase/server";
import type {
  PasswordResetRequestFormData,
  PasswordResetConfirmFormData,
} from "@/lib/auth-schemas";

type ErrorResponse = {
  server?: string[];
  email?: string[];
  password?: string[];
};

const resetPasswordRequestSchema = z.object({
  email: z.string().email("Please enter a valid email address"),
});

const resetPasswordConfirmSchema = z
  .object({
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirmPassword: z.string(),
    token: z.string().min(1, "Reset token is required"),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords don't match",
    path: ["confirmPassword"],
  });

export async function requestPasswordReset(
  formData: PasswordResetRequestFormData,
) {
  const validatedFields = resetPasswordRequestSchema.safeParse({
    email: formData.email,
  });

  if (!validatedFields.success) {
    return {
      error: validatedFields.error.flatten().fieldErrors as ErrorResponse,
    };
  }

  const supabase = await createClient();

  try {
    const { error } = await supabase.auth.resetPasswordForEmail(
      validatedFields.data.email,
      {
        redirectTo: `${process.env.NEXT_PUBLIC_SITE_URL}/auth/callback?type=recovery`,
      },
    );

    if (error) {
      console.error("Password reset error:", error);
      // Don't expose if email exists or not for security
      // Just return success even if email doesn't exist
    }

    // Always return success to not leak email existence
    return { success: true };
  } catch (error) {
    console.error("Password reset error:", error);
    // Still return success to not leak email existence
    return { success: true };
  }
}

export async function confirmPasswordReset(
  formData: PasswordResetConfirmFormData,
  token: string,
) {
  const validatedFields = resetPasswordConfirmSchema.safeParse({
    password: formData.password,
    confirmPassword: formData.confirmPassword,
    token: token,
  });

  if (!validatedFields.success) {
    return {
      error: validatedFields.error.flatten().fieldErrors as ErrorResponse,
    };
  }

  const supabase = await createClient();

  try {
    // First exchange the code for a session
    const { error: sessionError } = await supabase.auth.exchangeCodeForSession(
      validatedFields.data.token,
    );

    if (sessionError) {
      console.error("Error exchanging token for session:", sessionError);
      return {
        error:
          "Invalid or expired reset link. Please request a new password reset.",
      };
    }

    // Use the session to update the password
    const { error: updateError } = await supabase.auth.updateUser({
      password: validatedFields.data.password,
    });

    if (updateError) {
      console.error("Error updating password:", updateError);

      if (updateError.message.includes("New password should be different")) {
        return {
          error: "New password must be different from your current password.",
        };
      }

      if (updateError.message.includes("weak password")) {
        return {
          error:
            "Password is too weak. Please choose a stronger password with at least 8 characters, including uppercase, lowercase, and numbers.",
        };
      }

      return {
        error: updateError.message,
      };
    }

    // Ensure user is logged out after password reset
    await supabase.auth.signOut();

    return { success: true };
  } catch (error) {
    console.error("Password reset error:", error);
    return {
      error: "An unexpected error occurred. Please try again.",
    };
  }
}
