"use client";

import { useState, useEffect } from "react";
import { useUser } from "@/hooks/use-user";
import { Loading } from "@/components/ui/loading";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { ProfilePictureSelector } from "@/components/ProfilePictureSelector";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

import {
  User,
  Mail,
  Calendar,
  Crown,
  DollarSign,
  Check,
  Plus,
  Edit,
  Link,
  Unlink,
  AlertTriangle,
  UserX,
  Lock,
  CheckCircle,
  XCircle,
  Wrench,
} from "lucide-react";
import { SiGithub } from "react-icons/si";
import { toast } from "sonner";
import {
  getUserIdentities,
  linkOAuthProvider,
  unlinkOAuthProvider,
  updateUserProfile,
  requestAccountDeletion,
  hasPassword,
  setUserPassword,
  changeUserPassword,
  toggleSubscriptionTier,
} from "./actions";
import EmailChangeForm from "@/components/account/email-change-form";
import { DeviceManagement } from "@/components/account/device-management";
import { useSubscription } from "@/hooks/use-subscription";

import type { UserIdentity } from "@supabase/supabase-js";

export default function AccountPage() {
  const { user, loading } = useUser();
  const { subscriptionTier, refreshSubscription } = useSubscription();
  const [identities, setIdentities] = useState<UserIdentity[]>([]);
  const [loadingIdentities, setLoadingIdentities] = useState(true);
  const [linkingProvider, setLinkingProvider] = useState<string | null>(null);
  const [unlinkingProvider, setUnlinkingProvider] = useState<string | null>(
    null,
  );
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [deletingAccount, setDeletingAccount] = useState(false);
  const [updatingProfile, setUpdatingProfile] = useState(false);
  const [userHasPassword, setUserHasPassword] = useState(false);
  const [checkingPassword, setCheckingPassword] = useState(true);
  const [showSetPasswordDialog, setShowSetPasswordDialog] = useState(false);
  const [showChangePasswordDialog, setShowChangePasswordDialog] =
    useState(false);
  const [settingPassword, setSettingPassword] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [togglingSubscription, setTogglingSubscription] = useState(false);

  const [passwordValidation, setPasswordValidation] = useState({
    length: false,
    uppercase: false,
    lowercase: false,
    number: false,
  });
  const [confirmPasswordMatch, setConfirmPasswordMatch] = useState(true);

  // Load user identities and check password status
  useEffect(() => {
    if (user) {
      loadIdentities();
      checkPasswordStatus();
    }
  }, [user]);

  const validatePassword = (password: string) => {
    return {
      length: password.length >= 8,
      uppercase: /[A-Z]/.test(password),
      lowercase: /[a-z]/.test(password),
      number: /\d/.test(password),
    };
  };

  const isPasswordValid = (validation: typeof passwordValidation) => {
    return (
      validation.length &&
      validation.uppercase &&
      validation.lowercase &&
      validation.number
    );
  };

  const resetPasswordValidation = () => {
    setPasswordValidation({
      length: false,
      uppercase: false,
      lowercase: false,
      number: false,
    });
    setConfirmPasswordMatch(true);
  };

  const loadIdentities = async () => {
    try {
      setLoadingIdentities(true);
      const userIdentities = await getUserIdentities();
      setIdentities(userIdentities as UserIdentity[]);
    } catch (error) {
      toast.error("Failed to load connected accounts", {
        description: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setLoadingIdentities(false);
    }
  };

  const checkPasswordStatus = async () => {
    try {
      setCheckingPassword(true);
      const hasPasswordAuth = await hasPassword();
      setUserHasPassword(hasPasswordAuth);
    } catch (error) {
      toast.error("Failed to check password status", {
        description: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setCheckingPassword(false);
    }
  };

  const handleLinkProvider = async (provider: "google" | "github") => {
    try {
      setLinkingProvider(provider);
      await linkOAuthProvider(provider);
      toast.success(`Linking ${getProviderDisplayName(provider)} account...`, {
        description: "You will be redirected to complete the connection.",
      });
    } catch (error) {
      toast.error(`Failed to link ${getProviderDisplayName(provider)}`, {
        description: error instanceof Error ? error.message : "Unknown error",
      });
      setLinkingProvider(null);
    }
  };

  const handleUnlinkProvider = async (provider: "google" | "github") => {
    try {
      setUnlinkingProvider(provider);
      await unlinkOAuthProvider(provider);
      toast.success(`${getProviderDisplayName(provider)} account unlinked successfully`);
      await loadIdentities(); // Refresh the list
    } catch (error) {
      toast.error(`Failed to unlink ${getProviderDisplayName(provider)}`, {
        description: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setUnlinkingProvider(null);
    }
  };

  const handleToggleSubscription = async () => {
    try {
      setTogglingSubscription(true);
      const result = await toggleSubscriptionTier();
      refreshSubscription(); // Refresh the subscription state
      toast.success(result.message);
    } catch (error) {
      toast.error("Failed to update subscription", {
        description: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setTogglingSubscription(false);
    }
  };

  const handleUpdateProfile = async (
    event: React.FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);

    try {
      setUpdatingProfile(true);
      await updateUserProfile(formData);
      toast.success("Profile updated successfully");
    } catch (error) {
      toast.error("Failed to update profile", {
        description: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setUpdatingProfile(false);
    }
  };

  const handleSetPassword = async (formData: FormData) => {
    const password = formData.get("password") as string;
    const confirmPassword = formData.get("confirmPassword") as string;

    if (password !== confirmPassword) {
      toast.error("Passwords do not match");
      return;
    }

    const validation = validatePassword(password);
    if (!isPasswordValid(validation)) {
      toast.error("Password does not meet requirements");
      return;
    }

    try {
      setSettingPassword(true);
      await setUserPassword(password);
      toast.success("Password set successfully", {
        description: "You can now sign in using your email and password.",
      });
      setShowSetPasswordDialog(false);
      resetPasswordValidation();
      await checkPasswordStatus();
    } catch (error) {
      toast.error("Failed to set password", {
        description: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setSettingPassword(false);
    }
  };

  const handleChangePassword = async (formData: FormData) => {
    const currentPassword = formData.get("currentPassword") as string;
    const newPassword = formData.get("newPassword") as string;
    const confirmNewPassword = formData.get("confirmNewPassword") as string;

    if (!currentPassword) {
      toast.error("Current password is required");
      return;
    }

    if (newPassword !== confirmNewPassword) {
      toast.error("New passwords do not match");
      return;
    }

    const validation = validatePassword(newPassword);
    if (!isPasswordValid(validation)) {
      toast.error("Password does not meet requirements");
      return;
    }

    try {
      setChangingPassword(true);
      await changeUserPassword(currentPassword, newPassword);
      toast.success("Password changed successfully");
      setShowChangePasswordDialog(false);
      resetPasswordValidation();
    } catch (error) {
      toast.error("Failed to change password", {
        description: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setChangingPassword(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (deleteConfirmation !== "DELETE") {
      toast.error("Please type 'DELETE' to confirm");
      return;
    }

    try {
      setDeletingAccount(true);
      await requestAccountDeletion(deleteConfirmation);
      toast.success("Account deleted successfully", {
        description: "Your account has been permanently deleted.",
      });
    } catch (error) {
      // Check if this is a redirect error (which means deletion succeeded)
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error";

      if (
        errorMessage.includes("NEXT_REDIRECT") ||
        errorMessage.includes("redirect")
      ) {
        // This is actually a successful deletion with redirect
        toast.success("Account deleted successfully", {
          description: "Your account has been permanently deleted.",
        });
        return; // Don't show error, let the redirect happen
      }

      // Only show error for actual failures
      toast.error("Failed to delete account", {
        description: errorMessage,
      });
    } finally {
      setDeletingAccount(false);
      setShowDeleteDialog(false);
      setDeleteConfirmation("");
    }
  };

  const isProviderConnected = (provider: string) => {
    return identities.some((identity) => identity.provider === provider);
  };

  const getProviderEmail = (provider: string) => {
    const identity = identities.find(
      (identity) => identity.provider === provider,
    );
    return identity?.identity_data?.email || null;
  };

  const getProviderDisplayName = (provider: string) => {
    switch (provider) {
      case "google":
        return "Google";
      case "github":
        return "GitHub";
      default:
        return provider.charAt(0).toUpperCase() + provider.slice(1);
    }
  };

  if (loading) {
    return <Loading fullScreen size="xl" text="Loading your account..." />;
  }

  const memberSince = new Date(user?.created_at || "").toLocaleDateString();

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20 pt-4 sm:pt-8">
      <div className="container mx-auto px-4 py-4 sm:py-8 max-w-6xl">
        {/* Header */}
        <div className="mb-6 sm:mb-8">
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold mb-2">Account Settings</h1>
          <p className="text-base sm:text-lg lg:text-xl text-muted-foreground">
            Manage your visual perception platform account and preferences
          </p>
        </div>

        <Tabs defaultValue="general" className="space-y-4 sm:space-y-6">
          <TabsList className="grid w-full grid-cols-4 h-auto">
            <TabsTrigger value="general" className="text-xs sm:text-sm">General</TabsTrigger>
            <TabsTrigger value="security" className="text-xs sm:text-sm">Security</TabsTrigger>
            <TabsTrigger value="devices" className="text-xs sm:text-sm">Devices</TabsTrigger>
            <TabsTrigger value="subscription" className="text-xs sm:text-sm">Subscription</TabsTrigger>
          </TabsList>

          <TabsContent value="general" className="space-y-4 sm:space-y-6">
            {/* Profile Section */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center text-lg sm:text-xl">
                  <User className="w-4 h-4 sm:w-5 sm:h-5 mr-2" />
                  Profile Information
                </CardTitle>
                <CardDescription className="text-sm">
                  Update your personal information and preferences
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 sm:space-y-6">
                {/* Profile Picture Section */}
                <div className="space-y-4">
                  <ProfilePictureSelector
                    user={user}
                    currentSource={user?.user_metadata?.profile_picture_source}
                  />
                </div>

                {/* Profile Update Form */}
                <form onSubmit={handleUpdateProfile} className="space-y-4">
                  <div className="grid grid-cols-1 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="fullName">Full Name</Label>
                      <Input
                        id="fullName"
                        name="fullName"
                        defaultValue={user?.user_metadata?.full_name || ""}
                        placeholder="Enter your full name"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="email">Email Address</Label>
                      <Input
                        id="email"
                        name="email"
                        type="email"
                        value={user?.email || ""}
                        disabled
                        className="bg-muted"
                      />
                      <p className="text-xs text-muted-foreground">
                        You can change your email on the Security tab
                      </p>
                    </div>
                  </div>
                  <Button type="submit" disabled={updatingProfile} className="w-full sm:w-auto">
                    {updatingProfile ? "Updating..." : "Update Profile"}
                  </Button>
                </form>
              </CardContent>
            </Card>

            {/* Account Details */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg sm:text-xl">Account Details</CardTitle>
                <CardDescription className="text-sm">
                  View your account information and manage your subscription
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 sm:space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-1 sm:space-y-0">
                  <div className="flex items-center space-x-2">
                    <Mail className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm font-medium">Email</span>
                  </div>
                  <span className="text-sm break-all sm:break-normal">{user?.email}</span>
                </div>
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-1 sm:space-y-0">
                  <div className="flex items-center space-x-2">
                    <Calendar className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm font-medium">Member since</span>
                  </div>
                  <span className="text-sm">{memberSince}</span>
                </div>
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-1 sm:space-y-0">
                  <div className="flex items-center space-x-2">
                    <Crown className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm font-medium">Plan</span>
                  </div>
                  <Badge
                    variant={
                      subscriptionTier === "free" ? "secondary" : "default"
                    }
                    className="w-fit"
                  >
                    {subscriptionTier === "free" ? "Free" : "Cloud Pro"}
                    {subscriptionTier === "pro" && (
                      <Crown className="w-3 h-3 ml-1" />
                    )}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="security" className="space-y-4 sm:space-y-6">
            {/* Email Management */}
            <EmailChangeForm currentEmail={user?.email || ""} />

            {/* Password Management */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center text-lg sm:text-xl">
                  <Lock className="w-4 h-4 sm:w-5 sm:h-5 mr-2" />
                  Password Authentication
                </CardTitle>
                <CardDescription className="text-sm">
                  {userHasPassword
                    ? "Manage your password for email authentication"
                    : "Set up password authentication to enable email login"}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {checkingPassword ? (
                  <div className="flex items-center justify-center py-8">
                    <Loading size="sm" text="Checking password status..." />
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-4 border rounded-lg space-y-3 sm:space-y-0">
                      <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-neutral-700 flex items-center justify-center">
                          <Mail className="w-5 h-5" />
                        </div>
                        <div>
                          <p className="font-medium">Email & Password</p>
                          <p className="text-sm text-muted-foreground">
                            {userHasPassword
                              ? "Password authentication enabled"
                              : "No password set"}
                          </p>
                        </div>
                      </div>
                      <div className="flex flex-col sm:flex-row items-start sm:items-center space-y-2 sm:space-y-0 sm:space-x-2">
                        {userHasPassword ? (
                          <>
                            <Badge
                              variant="outline"
                              className="text-green-600 border-green-600 w-fit"
                            >
                              Enabled
                            </Badge>
                            <Dialog
                              open={showChangePasswordDialog}
                              onOpenChange={(open) => {
                                setShowChangePasswordDialog(open);
                                if (!open) resetPasswordValidation();
                              }}
                            >
                              <DialogTrigger asChild>
                                <Button variant="outline" size="sm" className="w-full sm:w-auto">
                                  <Edit className="w-4 h-4 mr-2" />
                                  Change Password
                                </Button>
                              </DialogTrigger>
                              <DialogContent>
                                <DialogHeader>
                                  <DialogTitle>Change Password</DialogTitle>
                                  <DialogDescription>
                                    Enter your current password and choose a new
                                    password for your account.
                                  </DialogDescription>
                                </DialogHeader>
                                <form
                                  onSubmit={(e) => {
                                    e.preventDefault();
                                    const formData = new FormData(
                                      e.currentTarget,
                                    );
                                    handleChangePassword(formData);
                                  }}
                                  className="space-y-4"
                                >
                                  <div className="space-y-2">
                                    <Label htmlFor="currentPassword">
                                      Current Password
                                    </Label>
                                    <Input
                                      id="currentPassword"
                                      name="currentPassword"
                                      type="password"
                                      required
                                      placeholder="Enter your current password"
                                    />
                                  </div>
                                  <div className="space-y-2">
                                    <Label htmlFor="newPassword">
                                      New Password
                                    </Label>
                                    <Input
                                      id="newPassword"
                                      name="newPassword"
                                      type="password"
                                      required
                                      placeholder="Enter your new password"
                                      onChange={(e) => {
                                        const validation = validatePassword(
                                          e.target.value,
                                        );
                                        setPasswordValidation(validation);
                                      }}
                                    />
                                    <div className="space-y-1">
                                      <div className="flex items-center space-x-2 text-xs">
                                        {passwordValidation.length ? (
                                          <CheckCircle className="w-3 h-3 text-green-500" />
                                        ) : (
                                          <XCircle className="w-3 h-3 text-red-500" />
                                        )}
                                        <span
                                          className={
                                            passwordValidation.length
                                              ? "text-green-600"
                                              : "text-red-600"
                                          }
                                        >
                                          At least 8 characters
                                        </span>
                                      </div>
                                      <div className="flex items-center space-x-2 text-xs">
                                        {passwordValidation.uppercase ? (
                                          <CheckCircle className="w-3 h-3 text-green-500" />
                                        ) : (
                                          <XCircle className="w-3 h-3 text-red-500" />
                                        )}
                                        <span
                                          className={
                                            passwordValidation.uppercase
                                              ? "text-green-600"
                                              : "text-red-600"
                                          }
                                        >
                                          One uppercase letter
                                        </span>
                                      </div>
                                      <div className="flex items-center space-x-2 text-xs">
                                        {passwordValidation.lowercase ? (
                                          <CheckCircle className="w-3 h-3 text-green-500" />
                                        ) : (
                                          <XCircle className="w-3 h-3 text-red-500" />
                                        )}
                                        <span
                                          className={
                                            passwordValidation.lowercase
                                              ? "text-green-600"
                                              : "text-red-600"
                                          }
                                        >
                                          One lowercase letter
                                        </span>
                                      </div>
                                      <div className="flex items-center space-x-2 text-xs">
                                        {passwordValidation.number ? (
                                          <CheckCircle className="w-3 h-3 text-green-500" />
                                        ) : (
                                          <XCircle className="w-3 h-3 text-red-500" />
                                        )}
                                        <span
                                          className={
                                            passwordValidation.number
                                              ? "text-green-600"
                                              : "text-red-600"
                                          }
                                        >
                                          One number
                                        </span>
                                      </div>
                                    </div>
                                  </div>
                                  <div className="space-y-2">
                                    <Label htmlFor="confirmNewPassword">
                                      Confirm New Password
                                    </Label>
                                    <Input
                                      id="confirmNewPassword"
                                      name="confirmNewPassword"
                                      type="password"
                                      required
                                      placeholder="Confirm your new password"
                                      onChange={(e) => {
                                        const newPassword =
                                          (
                                            document.getElementById(
                                              "newPassword",
                                            ) as HTMLInputElement
                                          )?.value || "";
                                        setConfirmPasswordMatch(
                                          newPassword === e.target.value,
                                        );
                                      }}
                                      className={
                                        !confirmPasswordMatch
                                          ? "border-red-500"
                                          : ""
                                      }
                                    />
                                    {!confirmPasswordMatch && (
                                      <p className="text-xs text-red-600">
                                        Passwords do not match
                                      </p>
                                    )}
                                  </div>
                                  <DialogFooter>
                                    <Button
                                      type="button"
                                      variant="outline"
                                      onClick={() => {
                                        setShowChangePasswordDialog(false);
                                        resetPasswordValidation();
                                      }}
                                    >
                                      Cancel
                                    </Button>
                                    <Button
                                      type="submit"
                                      disabled={
                                        changingPassword ||
                                        !isPasswordValid(passwordValidation) ||
                                        !confirmPasswordMatch
                                      }
                                    >
                                      {changingPassword
                                        ? "Changing..."
                                        : "Change Password"}
                                    </Button>
                                  </DialogFooter>
                                </form>
                              </DialogContent>
                            </Dialog>
                          </>
                        ) : (
                          <Dialog
                            open={showSetPasswordDialog}
                            onOpenChange={(open) => {
                              setShowSetPasswordDialog(open);
                              if (!open) resetPasswordValidation();
                            }}
                          >
                            <DialogTrigger asChild>
                              <Button variant="outline" size="sm" className="w-full sm:w-auto">
                                <Plus className="w-4 h-4 mr-2" />
                                Set Password
                              </Button>
                            </DialogTrigger>
                            <DialogContent>
                              <DialogHeader>
                                <DialogTitle>Set Password</DialogTitle>
                                <DialogDescription>
                                  Create a password to enable email
                                  authentication. This will allow you to sign in
                                  using your email and password.
                                </DialogDescription>
                              </DialogHeader>
                              <form
                                onSubmit={(e) => {
                                  e.preventDefault();
                                  const formData = new FormData(
                                    e.currentTarget,
                                  );
                                  handleSetPassword(formData);
                                }}
                                className="space-y-4"
                              >
                                <div className="space-y-2">
                                  <Label htmlFor="password">Password</Label>
                                  <Input
                                    id="password"
                                    name="password"
                                    type="password"
                                    required
                                    placeholder="Enter your password"
                                    onChange={(e) => {
                                      const validation = validatePassword(
                                        e.target.value,
                                      );
                                      setPasswordValidation(validation);
                                    }}
                                  />
                                  <div className="space-y-1">
                                    <div className="flex items-center space-x-2 text-xs">
                                      {passwordValidation.length ? (
                                        <CheckCircle className="w-3 h-3 text-green-500" />
                                      ) : (
                                        <XCircle className="w-3 h-3 text-red-500" />
                                      )}
                                      <span
                                        className={
                                          passwordValidation.length
                                            ? "text-green-600"
                                            : "text-red-600"
                                        }
                                      >
                                        At least 8 characters
                                      </span>
                                    </div>
                                    <div className="flex items-center space-x-2 text-xs">
                                      {passwordValidation.uppercase ? (
                                        <CheckCircle className="w-3 h-3 text-green-500" />
                                      ) : (
                                        <XCircle className="w-3 h-3 text-red-500" />
                                      )}
                                      <span
                                        className={
                                          passwordValidation.uppercase
                                            ? "text-green-600"
                                            : "text-red-600"
                                        }
                                      >
                                        One uppercase letter
                                      </span>
                                    </div>
                                    <div className="flex items-center space-x-2 text-xs">
                                      {passwordValidation.lowercase ? (
                                        <CheckCircle className="w-3 h-3 text-green-500" />
                                      ) : (
                                        <XCircle className="w-3 h-3 text-red-500" />
                                      )}
                                      <span
                                        className={
                                          passwordValidation.lowercase
                                            ? "text-green-600"
                                            : "text-red-600"
                                        }
                                      >
                                        One lowercase letter
                                      </span>
                                    </div>
                                    <div className="flex items-center space-x-2 text-xs">
                                      {passwordValidation.number ? (
                                        <CheckCircle className="w-3 h-3 text-green-500" />
                                      ) : (
                                        <XCircle className="w-3 h-3 text-red-500" />
                                      )}
                                      <span
                                        className={
                                          passwordValidation.number
                                            ? "text-green-600"
                                            : "text-red-600"
                                        }
                                      >
                                        One number
                                      </span>
                                    </div>
                                  </div>
                                </div>
                                <div className="space-y-2">
                                  <Label htmlFor="confirmPassword">
                                    Confirm Password
                                  </Label>
                                  <Input
                                    id="confirmPassword"
                                    name="confirmPassword"
                                    type="password"
                                    required
                                    placeholder="Confirm your password"
                                    onChange={(e) => {
                                      const password =
                                        (
                                          document.getElementById(
                                            "password",
                                          ) as HTMLInputElement
                                        )?.value || "";
                                      setConfirmPasswordMatch(
                                        password === e.target.value,
                                      );
                                    }}
                                    className={
                                      !confirmPasswordMatch
                                        ? "border-red-500"
                                        : ""
                                    }
                                  />
                                  {!confirmPasswordMatch && (
                                    <p className="text-xs text-red-600">
                                      Passwords do not match
                                    </p>
                                  )}
                                </div>
                                <DialogFooter>
                                  <Button
                                    type="button"
                                    variant="outline"
                                    onClick={() => {
                                      setShowSetPasswordDialog(false);
                                      resetPasswordValidation();
                                    }}
                                  >
                                    Cancel
                                  </Button>
                                  <Button
                                    type="submit"
                                    disabled={
                                      settingPassword ||
                                      !isPasswordValid(passwordValidation) ||
                                      !confirmPasswordMatch
                                    }
                                  >
                                    {settingPassword
                                      ? "Setting Password..."
                                      : "Set Password"}
                                  </Button>
                                </DialogFooter>
                              </form>
                            </DialogContent>
                          </Dialog>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Connected Accounts */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center text-lg sm:text-xl">
                  <Link className="w-4 h-4 sm:w-5 sm:h-5 mr-2" />
                  Connected Accounts
                </CardTitle>
                <CardDescription className="text-sm">
                  Manage your OAuth provider connections. You can sign in using
                  any of these methods.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {loadingIdentities ? (
                  <div className="flex items-center justify-center py-8">
                    <Loading size="sm" text="Loading connected accounts..." />
                  </div>
                ) : (
                  <div className="space-y-4">
                    {/* Google */}
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-4 border rounded-lg space-y-3 sm:space-y-0">
                      <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-neutral-700 flex items-center justify-center">
                          <svg className="w-5 h-5" viewBox="0 0 24 24">
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
                        </div>
                        <div>
                          <p className="font-medium">Google</p>
                          <p className="text-sm text-muted-foreground break-all sm:break-normal">
                            {isProviderConnected("google")
                              ? `Connected to ${getProviderEmail("google")}`
                              : "Not connected"}
                          </p>
                        </div>
                      </div>
                      <div className="flex flex-col sm:flex-row items-start sm:items-center space-y-2 sm:space-y-0 sm:space-x-2">
                        {isProviderConnected("google") ? (
                          <>
                            <Badge
                              variant="outline"
                              className="text-green-600 border-green-600 w-fit"
                            >
                              Connected
                            </Badge>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleUnlinkProvider("google")}
                              disabled={
                                unlinkingProvider === "google" ||
                                identities.length <= 1
                              }
                              className="w-full sm:w-auto"
                            >
                              {unlinkingProvider === "google" ? (
                                <Loading size="sm" />
                              ) : (
                                <>
                                  <Unlink className="w-4 h-4 mr-2" />
                                  Unlink
                                </>
                              )}
                            </Button>
                          </>
                        ) : (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleLinkProvider("google")}
                            disabled={linkingProvider === "google"}
                            className="w-full sm:w-auto"
                          >
                            {linkingProvider === "google" ? (
                              <Loading size="sm" />
                            ) : (
                              <>
                                <Link className="w-4 h-4 mr-2" />
                                Connect
                              </>
                            )}
                          </Button>
                        )}
                      </div>
                    </div>

                    {/* GitHub */}
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-4 border rounded-lg space-y-3 sm:space-y-0">
                      <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-neutral-700 flex items-center justify-center">
                          <SiGithub className="w-5 h-5" />
                        </div>
                        <div>
                          <p className="font-medium">GitHub</p>
                          <p className="text-sm text-muted-foreground break-all sm:break-normal">
                            {isProviderConnected("github")
                              ? `Connected to ${getProviderEmail("github")}`
                              : "Not connected"}
                          </p>
                        </div>
                      </div>
                      <div className="flex flex-col sm:flex-row items-start sm:items-center space-y-2 sm:space-y-0 sm:space-x-2">
                        {isProviderConnected("github") ? (
                          <>
                            <Badge
                              variant="outline"
                              className="text-green-600 border-green-600 w-fit"
                            >
                              Connected
                            </Badge>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleUnlinkProvider("github")}
                              disabled={
                                unlinkingProvider === "github" ||
                                identities.length <= 1
                              }
                              className="w-full sm:w-auto"
                            >
                              {unlinkingProvider === "github" ? (
                                <Loading size="sm" />
                              ) : (
                                <>
                                  <Unlink className="w-4 h-4 mr-2" />
                                  Unlink
                                </>
                              )}
                            </Button>
                          </>
                        ) : (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleLinkProvider("github")}
                            disabled={linkingProvider === "github"}
                            className="w-full sm:w-auto"
                          >
                            {linkingProvider === "github" ? (
                              <Loading size="sm" />
                            ) : (
                              <>
                                <Link className="w-4 h-4 mr-2" />
                                Connect
                              </>
                            )}
                          </Button>
                        )}
                      </div>
                    </div>

                    {identities.length <= 1 && (
                      <div className="flex items-center text-sm text-amber-600 dark:text-amber-500 bg-amber-50 dark:bg-amber-950/40 p-3 rounded-lg space-x-2">
                        <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                        <span>
                          You must have at least two login methods to unlink an account.
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Danger Zone */}
            <Card className="border-red-200 dark:border-red-900">
              <CardHeader>
                <CardTitle className="flex items-center text-red-600 dark:text-red-400 text-lg sm:text-xl">
                  <AlertTriangle className="w-4 h-4 sm:w-5 sm:h-5 mr-2" />
                  Danger Zone
                </CardTitle>
                <CardDescription className="dark:text-red-300/80 text-sm">
                  Irreversible and destructive actions
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-4 border border-red-200 dark:border-red-900 rounded-lg bg-red-50 dark:bg-red-950/40 space-y-3 sm:space-y-0">
                  <div className="flex-1">
                    <h4 className="font-medium text-red-900 dark:text-red-300">
                      Delete Account
                    </h4>
                    <p className="text-sm text-red-700 dark:text-red-400">
                      Permanently delete your account and all associated data.
                      This action cannot be undone.
                    </p>
                  </div>
                  <Dialog
                    open={showDeleteDialog}
                    onOpenChange={setShowDeleteDialog}
                  >
                    <DialogTrigger asChild>
                      <Button variant="destructive" size="sm" className="w-full sm:w-auto sm:ml-4">
                        <UserX className="w-4 h-4 mr-2" />
                        Delete Account
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle className="flex items-center text-red-600 dark:text-red-400">
                          <AlertTriangle className="w-5 h-5 mr-2" />
                          Delete Account
                        </DialogTitle>
                        <DialogDescription className="dark:text-red-300/80">
                          This action cannot be undone. This will permanently
                          delete your account and remove all of your data from
                          our servers.
                        </DialogDescription>
                      </DialogHeader>
                      <div className="space-y-4">
                        <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-lg p-4">
                          <h4 className="font-medium text-red-900 dark:text-red-300 mb-2">
                            What will be deleted:
                          </h4>
                          <ul className="text-sm text-red-700 dark:text-red-400 space-y-1">
                            <li>• Your account and profile information</li>
                            <li>• All connected OAuth providers</li>
                            <li>• Billing history and payment methods</li>
                            <li>• All usage data and preferences</li>
                          </ul>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="deleteConfirmation">
                            Type{" "}
                            <code className="bg-gray-100 dark:bg-red-950/60 px-2 py-1 rounded">
                              DELETE
                            </code>{" "}
                            to confirm:
                          </Label>
                          <Input
                            id="deleteConfirmation"
                            value={deleteConfirmation}
                            onChange={(e) =>
                              setDeleteConfirmation(e.target.value)
                            }
                            placeholder="Type DELETE here"
                          />
                        </div>
                      </div>
                      <DialogFooter>
                        <Button
                          variant="outline"
                          onClick={() => {
                            setShowDeleteDialog(false);
                            setDeleteConfirmation("");
                          }}
                        >
                          Cancel
                        </Button>
                        <Button
                          variant="destructive"
                          onClick={handleDeleteAccount}
                          disabled={
                            deletingAccount || deleteConfirmation !== "DELETE"
                          }
                        >
                          {deletingAccount ? "Deleting..." : "Delete Account"}
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="devices" className="space-y-4 sm:space-y-6">
            <DeviceManagement />
          </TabsContent>

          <TabsContent value="subscription" className="space-y-4 sm:space-y-6">
            {/* Development Notice */}
            <Card className="border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-900/20">
              <CardHeader>
                <CardTitle className="flex items-center text-lg">
                  <Wrench className="w-4 h-4 mr-2 text-amber-500" />
                  Development Mode
                </CardTitle>
                <CardDescription>
                  All features are currently free during the development phase
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-3">
                  Orion Live is actively being developed. You can enable Pro features to test 
                  cloud processing and advanced capabilities without any charges. Billing will 
                  be introduced after the official release.
                </p>
                <ul className="text-sm text-muted-foreground space-y-1">
                  <li>• No payment required for any features</li>
                  <li>• Pro features available for testing</li>
                  <li>• Settings preserved for future billing</li>
                </ul>
              </CardContent>
            </Card>

            {/* Current Plan */}
            <Card>
              <CardHeader>
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-2 sm:space-y-0">
                  <div>
                    <CardTitle className="flex items-center text-lg sm:text-xl">
                      <Crown className="w-4 h-4 sm:w-5 sm:h-5 mr-2" />
                      Current Plan
                    </CardTitle>
                    <CardDescription className="text-sm">
                      Manage your plan features (no billing during development)
                    </CardDescription>
                  </div>
                  <Badge
                    variant={
                      subscriptionTier === "free" ? "secondary" : "default"
                    }
                    className="w-fit"
                  >
                    {subscriptionTier === "free" ? "Free Plan" : "Cloud Pro"}
                    {subscriptionTier === "pro" && (
                      <Crown className="w-3 h-3 ml-1" />
                    )}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid gap-6 lg:grid-cols-2">
                  {/* Free Plan */}
                  <div className="space-y-4">
                    <div>
                      <h3 className="text-xl font-bold">
                        {subscriptionTier === "free"
                          ? "Free Plan"
                          : "Cloud Pro"}
                      </h3>
                      <p className="text-muted-foreground">
                        {subscriptionTier === "free"
                          ? "Local processing with basic features"
                          : "Unlimited cloud processing with advanced features"}
                      </p>
                    </div>
                    <ul className="space-y-2 text-sm">
                      <li className="flex items-center">
                        <Check className="w-4 h-4 mr-2 text-green-500" />
                        Local Mac-iPhone processing
                      </li>
                      <li className="flex items-center">
                        <Check className="w-4 h-4 mr-2 text-green-500" />
                        Real-time visual perception
                      </li>
                      {subscriptionTier === "free" ? (
                        <>
                          <li className="flex items-center">
                            <Check className="w-4 h-4 mr-2 text-green-500" />
                            1-hour context memory
                          </li>
                          <li className="flex items-center">
                            <Check className="w-4 h-4 mr-2 text-green-500" />
                            Limited cloud features
                          </li>
                        </>
                      ) : (
                        <>
                          <li className="flex items-center">
                            <Check className="w-4 h-4 mr-2 text-green-500" />
                            Unlimited context memory
                          </li>
                          <li className="flex items-center">
                            <Check className="w-4 h-4 mr-2 text-green-500" />
                            Full cloud processing
                          </li>
                          <li className="flex items-center">
                            <Check className="w-4 h-4 mr-2 text-green-500" />
                            Advanced AI models
                          </li>
                          <li className="flex items-center">
                            <Check className="w-4 h-4 mr-2 text-green-500" />
                            Priority support
                          </li>
                        </>
                      )}
                    </ul>
                  </div>
                  <div className="space-y-4">
                    <div className="text-center sm:text-right">
                      <p className="text-2xl sm:text-3xl font-bold">
                        {subscriptionTier === "free" ? "Free" : "Free"}
                        <span className="text-base sm:text-lg text-muted-foreground">
                          {subscriptionTier === "free" ? "" : " (Pro Features)"}
                        </span>
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {subscriptionTier === "free"
                          ? "All features free during development"
                          : "No billing during development"}
                      </p>
                    </div>
                    <Button
                      className="w-full"
                      onClick={handleToggleSubscription}
                      disabled={togglingSubscription}
                      variant={
                        subscriptionTier === "pro" ? "outline" : "default"
                      }
                    >
                      {togglingSubscription
                        ? "Processing..."
                        : subscriptionTier === "free"
                          ? "Enable Pro Features"
                          : "Disable Pro Features"}
                    </Button>
                    {subscriptionTier === "pro" ? (
                      <p className="text-xs text-muted-foreground text-center">
                        Pro features enabled for testing. No charges during development.
                      </p>
                    ) : (
                      <p className="text-xs text-muted-foreground text-center">
                        Enable Pro features to test cloud processing and advanced capabilities.
                      </p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Plan Features Comparison */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center text-lg sm:text-xl">
                  <DollarSign className="w-4 h-4 sm:w-5 sm:h-5 mr-2" />
                  Plan Comparison
                </CardTitle>
                <CardDescription className="text-sm">
                  Compare features between Free and Cloud Pro plans
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="p-4 border rounded-lg">
                    <h4 className="font-semibold mb-3">Free Plan</h4>
                    <ul className="space-y-2 text-sm">
                      <li className="flex items-center">
                        <Check className="w-4 h-4 mr-2 text-green-500" />
                        Local processing
                      </li>
                      <li className="flex items-center">
                        <Check className="w-4 h-4 mr-2 text-green-500" />
                        1-hour memory
                      </li>
                      <li className="flex items-center">
                        <Check className="w-4 h-4 mr-2 text-green-500" />
                        Basic features
                      </li>
                    </ul>
                  </div>
                  <div className="p-4 border rounded-lg bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
                    <h4 className="font-semibold mb-3 flex items-center">
                      Cloud Pro
                      <Crown className="w-4 h-4 ml-2 text-primary" />
                    </h4>
                    <ul className="space-y-2 text-sm">
                      <li className="flex items-center">
                        <Check className="w-4 h-4 mr-2 text-green-500" />
                        Everything in Free
                      </li>
                      <li className="flex items-center">
                        <Check className="w-4 h-4 mr-2 text-green-500" />
                        Unlimited memory
                      </li>
                      <li className="flex items-center">
                        <Check className="w-4 h-4 mr-2 text-green-500" />
                        Cloud processing
                      </li>
                      <li className="flex items-center">
                        <Check className="w-4 h-4 mr-2 text-green-500" />
                        Advanced AI models
                      </li>
                      <li className="flex items-center">
                        <Check className="w-4 h-4 mr-2 text-green-500" />
                        Priority support
                      </li>
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

