"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { NavbarWrapper } from "@/components/NavbarWrapper";

export default function NavbarClientWrapper() {
  const pathname = usePathname() || "/";
  const isDashboardRoute = pathname.startsWith("/dashboard");
  const isAuthRoute = pathname.startsWith("/login") || pathname.startsWith("/signup") || pathname.startsWith("/reset-password");

  if (isDashboardRoute || isAuthRoute) return null;

  return (
    <>
      <NavbarWrapper />
      {/* Spacer div to push content below the fixed navbar */}
      <div className="h-16" />
    </>
  );
}
