"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { CleanFooter } from "@/components/Footer";

export default function FooterClientWrapper() {
  const pathname = usePathname() || "/";
  const isDashboardRoute = pathname.startsWith("/dashboard");
  const isAuthRoute = pathname.startsWith("/login") || pathname.startsWith("/signup");

  if (isDashboardRoute || isAuthRoute) return null;

  return <CleanFooter />;
}
