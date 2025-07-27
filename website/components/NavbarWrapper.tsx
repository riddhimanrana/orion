"use client";

import { useUser } from "@/hooks/use-user";
import { CleanNavigation } from "./Navbar";
import { AuthenticatedNavigation } from "./AuthenticatedNavbar";

interface NavbarWrapperProps {
  className?: string;
}

export const NavbarWrapper = ({ className }: NavbarWrapperProps) => {
  const { user, loading } = useUser();

  // During loading, show the unauthenticated navbar to prevent layout shift
  if (loading) {
    return <CleanNavigation className={className} />;
  }

  // Show appropriate navbar based on authentication state
  if (user) {
    return <AuthenticatedNavigation className={className} />;
  }

  return <CleanNavigation className={className} />;
};

export default NavbarWrapper;
