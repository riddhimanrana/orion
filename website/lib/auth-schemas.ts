import { z } from "zod";

// Base email schema
const emailSchema = z
  .string()
  .min(1, "Email is required")
  .email("Please enter a valid email address")
  .max(255, "Email is too long");

// Base password schema
const passwordSchema = z
  .string()
  .min(8, "Password must be at least 8 characters long")
  .max(128, "Password is too long")
  .regex(
    /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/,
    "Password must contain at least one lowercase letter, one uppercase letter, and one number",
  );

// Sign up schema with password confirmation
export const signUpSchema = z
  .object({
    fullName: z
      .string()
      .min(1, "Full name is required")
      .max(100, "Full name is too long")
      .regex(
        /^[a-zA-Z\s'-]+$/,
        "Full name can only contain letters, spaces, hyphens, and apostrophes",
      ),
    email: emailSchema,
    password: passwordSchema,
    confirmPassword: z.string().min(1, "Please confirm your password"),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords don't match",
    path: ["confirmPassword"],
  });

// Sign in schema
export const signInSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, "Password is required"),
});

// Password reset request schema
export const passwordResetRequestSchema = z.object({
  email: emailSchema,
});

// Password reset confirmation schema
export const passwordResetConfirmSchema = z
  .object({
    password: passwordSchema,
    confirmPassword: z.string().min(1, "Please confirm your password"),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords don't match",
    path: ["confirmPassword"],
  });

// Type exports
export type SignUpFormData = z.infer<typeof signUpSchema>;
export type SignInFormData = z.infer<typeof signInSchema>;
export type PasswordResetRequestFormData = z.infer<
  typeof passwordResetRequestSchema
>;
export type PasswordResetConfirmFormData = z.infer<
  typeof passwordResetConfirmSchema
>;

// Authentication response types
export type OAuthAuthResponse =
  | {
      success: true;
      url: string;
    }
  | {
      error: string;
    };

export type EmailSignInResponse =
  | {
      success: true;
      redirectTo: string;
    }
  | {
      error: string;
    };

export type EmailSignUpResponse =
  | {
      success: true;
      message?: string;
      needsConfirmation?: boolean;
    }
  | {
      error: string;
    };
