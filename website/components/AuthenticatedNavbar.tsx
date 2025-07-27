"use client";

import React, { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { motion, AnimatePresence } from "motion/react";
import { useUser } from "@/hooks/use-user";
import { useSubscription } from "@/hooks/use-subscription";
import { Button } from "./ui/button";
import { UserAvatar } from "./UserAvatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { ModeToggle } from "./ThemeToggle";
import { cn } from "../lib/utils";
import {
  Menu,
  X,
  Home,
  User,
  Activity,
  LogOut,
  ChevronDown,
} from "lucide-react";
import { usePathname } from "next/navigation";

interface AuthenticatedNavigationProps {
  className?: string;
}

export const AuthenticatedNavigation = ({
  className,
}: AuthenticatedNavigationProps) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const { user, signOut } = useUser();
  const { subscriptionTier } = useSubscription();
  const pathname = usePathname();

  const handleSignOut = async () => {
    await signOut();
  };

  const navigationItems = [
    {
      href: "/dashboard",
      label: "Dashboard",
      icon: Home,
      description: "Overview and metrics",
    },
    {
      href: "/account",
      label: "Account",
      icon: User,
      description: "Profile and settings",
    },
    {
      href: "/activity",
      label: "Activity",
      icon: Activity,
      description: "Usage and logs",
    },
  ];

  const isActiveRoute = (href: string) => {
    return pathname === href;
  };

  return (
    <nav
      className={cn(
        "fixed top-0 left-0 right-0 z-50 bg-white/80 dark:bg-black/80 backdrop-blur-sm border-b border-border/50",
        className,
      )}
    >
      <div className="w-full mx-auto px-3 sm:px-4 lg:px-8">
        <div className="flex items-center justify-between h-16 min-w-0">
          {/* Logo - Left aligned */}
          <Link
            href="/dashboard"
            className="flex items-center space-x-2 sm:space-x-3 flex-shrink-0 min-w-0"
          >
            <div className="relative w-8 h-8 flex-shrink-0">
              <Image
                src="/orion.svg"
                alt="Orion Live Logo"
                width={32}
                height={32}
                className="w-full h-full"
              />
            </div>
            <span className="text-lg sm:text-xl font-semibold text-black dark:text-white truncate flex items-center">
              Orion Live
              {subscriptionTier === "pro" && (
                <span className="ml-2 px-2 py-0.5 text-xs font-medium border-1 border-amber-400 dark:border-amber-500  text-amber-600  dark:text-amber-400 rounded-sm inline-flex items-center">
                  PRO
                </span>
              )}
            </span>
          </Link>

          {/* Center Navigation Menu - Hidden on mobile */}
          <div className="hidden lg:flex items-center space-x-1">
            {navigationItems.map((item) => {
              const Icon = item.icon;
              const isActive = isActiveRoute(item.href);

              return (
                <Link key={item.href} href={item.href}>
                  <Button
                    variant={isActive ? "default" : "ghost"}
                    size="sm"
                    className={cn(
                      "flex items-center space-x-2 px-4 py-2 h-9",
                      isActive
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:text-foreground hover:bg-accent",
                    )}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="font-medium">{item.label}</span>
                  </Button>
                </Link>
              );
            })}
          </div>

          {/* Right side - Profile dropdown and theme toggle */}
          <div className="hidden lg:flex items-center space-x-3">
            {/* <Button
              variant="ghost"
              size="icon"
              className="relative"
              aria-label="Notifications"
            >
              <Bell className="w-4 h-4" />
              <span className="absolute -top-1 -right-1 w-2 h-2 bg-red-500 rounded-full"></span>
            </Button> */}

            <ModeToggle />

            {/* Profile Dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  className="flex items-center px-3 py-2 h-9 hover:bg-accent"
                >
                  <UserAvatar user={user} size="sm" className="w-7 h-7" />
                  <div className="hidden sm:block text-left">
                    <p className="text-sm font-medium leading-none flex items-center">
                      {user?.user_metadata?.full_name || "User"}
                      {/* {subscriptionTier === "pro" && (
                        <Crown className="w-3 h-3 ml-1 text-amber-500" />
                      )} */}
                    </p>
                    {/* <p className="text-xs text-muted-foreground leading-none mt-1">
                      {user?.email?.split("@")[0]}
                    </p> */}
                  </div>
                  <ChevronDown className="w-3 h-3 text-muted-foreground" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-64">
                <DropdownMenuLabel className="font-normal">
                  <div className="flex flex-col space-y-1">
                    <p className="text-sm font-medium leading-none flex items-center">
                      {user?.user_metadata?.full_name || "User"}
                    </p>
                    <p className="text-xs leading-none text-muted-foreground">
                      {user?.email}
                      {subscriptionTier === "pro" && (
                        <span className="ml-2 text-amber-600 font-medium">
                          Pro
                        </span>
                      )}
                    </p>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link
                    href="/dashboard"
                    className="flex items-center cursor-pointer"
                  >
                    <Home className="w-4 h-4 mr-2" />
                    Home
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link
                    href="/account"
                    className="flex items-center cursor-pointer"
                  >
                    <User className="w-4 h-4 mr-2" />
                    Account Settings
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link
                    href="/activity"
                    className="flex items-center cursor-pointer"
                  >
                    <Activity className="w-4 h-4 mr-2" />
                    Activity
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={handleSignOut}
                  className="text-red-600 dark:text-red-400 focus:text-red-600 dark:focus:text-red-400 cursor-pointer"
                >
                  <LogOut className="w-4 h-4 mr-2 text-red-600 dark:text-red-400" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          {/* Mobile Menu Toggle */}
          <div className="lg:hidden flex items-center space-x-2">
            {/* <Button
              variant="ghost"
              size="icon"
              className="relative"
              aria-label="Notifications"
            >
              <Bell className="w-4 h-4" />
              <span className="absolute -top-1 -right-1 w-2 h-2 bg-red-500 rounded-full"></span>
            </Button> */}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setMenuOpen(!menuOpen)}
              aria-label="Toggle menu"
              className="relative"
            >
              <motion.div
                animate={{ rotate: menuOpen ? 180 : 0 }}
                transition={{ duration: 0.2 }}
              >
                {menuOpen ? (
                  <X className="w-6 h-6 text-black dark:text-white" />
                ) : (
                  <Menu className="w-6 h-6 text-black dark:text-white" />
                )}
              </motion.div>
            </Button>
          </div>
        </div>

        {/* Mobile Menu */}
        <AnimatePresence>
          {menuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.3, ease: "easeInOut" }}
              className="lg:hidden  bg-white/95 dark:bg-black/95 backdrop-blur-md border-t border-border/50 w-full"
            >
              <motion.div
                initial={{ y: -20 }}
                animate={{ y: 0 }}
                exit={{ y: -20 }}
                transition={{ duration: 0.3, delay: 0.1 }}
                className="px-3 sm:px-4 py-6 space-y-6 w-full"
              >
                {/* User Info */}
                <motion.div
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.1 }}
                  className="flex items-center space-x-3 pb-4 border-b border-border/50"
                >
                  <UserAvatar user={user} size="lg" className="w-10 h-10" />
                  <div>
                    <p className="text-sm font-medium flex items-center">
                      {user?.user_metadata?.full_name || "User"}
                      {/* {subscriptionTier === "pro" && (
                        <Crown className="w-3 h-3 ml-1 text-amber-500" />
                      )} */}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {user?.email}
                      {subscriptionTier === "pro" && (
                        <span className="ml-2 text-amber-600 font-medium">
                          Pro
                        </span>
                      )}
                    </p>
                  </div>
                </motion.div>

                {/* Navigation Links */}
                <div className="space-y-2 w-full">
                  {navigationItems.map((item, index) => {
                    const Icon = item.icon;
                    const isActive = isActiveRoute(item.href);

                    return (
                      <motion.div
                        key={item.href}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.1 + index * 0.05 }}
                      >
                        <Link
                          href={item.href}
                          className={cn(
                            "flex items-center space-x-3 p-3 rounded-lg transition-colors",
                            isActive
                              ? "bg-primary text-primary-foreground"
                              : "hover:bg-accent",
                          )}
                          onClick={() => setMenuOpen(false)}
                        >
                          <Icon className="w-5 h-5" />
                          <div>
                            <p className="font-medium">{item.label}</p>
                            <p className="text-xs opacity-70">
                              {item.description}
                            </p>
                          </div>
                        </Link>
                      </motion.div>
                    );
                  })}
                </div>

                {/* Additional Options */}
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 }}
                  className="space-y-2 pt-4 border-t border-border/50"
                >
                  {/* <Link
                    href="/account"
                    className="flex items-center space-x-3 p-3 rounded-lg hover:bg-accent transition-colors"
                    onClick={() => setMenuOpen(false)}
                  >
                    <Settings className="w-5 h-5" />
                    <span>Settings</span>
                  </Link> */}

                  <div className="flex items-center justify-between p-3">
                    <span className="text-sm font-medium">Theme</span>
                    <ModeToggle />
                  </div>

                  <Button
                    variant="ghost"
                    onClick={handleSignOut}
                    className="w-full justify-start text-red-600 dark:text-red-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/20"
                  >
                    <LogOut className="w-5 h-5 mr-3" />
                    Sign out
                  </Button>
                </motion.div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </nav>
  );
};

export default AuthenticatedNavigation;
