"use client";
import React, { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { motion, AnimatePresence } from "motion/react";
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
} from "./ui/navigation-menu";
import { cn } from "../lib/utils";
import { usePathname } from "next/navigation";

import { Menu, X } from "lucide-react";
import { Button } from "./ui/button";
import { ModeToggle } from "./ThemeToggle";
import { useUser } from "@/hooks/use-user";

interface NavigationProps {
  className?: string;
}

export const CleanNavigation = ({ className }: NavigationProps) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const { user } = useUser();
  const pathname = usePathname();

  const isActive = (path: string) => {
    if (path === '/') {
      return pathname === '/';
    }
    return pathname.startsWith(path);
  };

  return (
    <nav
      className={cn(
        "fixed top-0 left-0 right-0 z-50 bg-white/80 dark:bg-black/80 backdrop-blur-sm",
        className,
      )}
    >
      <div className="w-full  mx-auto px-3 sm:px-4 lg:px-8">
        <div className="flex items-center justify-between h-16 min-w-0">
          {/* Logo - Left aligned */}
          <Link
            href="/"
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
            <span className="text-lg sm:text-xl font-semibold text-black dark:text-white truncate">
              Orion Live
            </span>
          </Link>

          {/* Center Navigation Menu - Hidden on mobile */}
          <NavigationMenu className="hidden lg:flex">
            <NavigationMenuList>
              <NavigationMenuItem>
                <NavigationMenuLink asChild>
                  <Link
                    href="/"
                    className={cn(
                      "px-4 py-2 text-sm font-medium transition-colors",
                      isActive('/') 
                        ? "text-black dark:text-white font-semibold" 
                        : "text-black/80 dark:text-white/80 hover:text-black dark:hover:text-white"
                    )}
                  >
                    Home
                  </Link>
                </NavigationMenuLink>
              </NavigationMenuItem>

              <NavigationMenuItem>
                <NavigationMenuLink asChild>
                  <Link
                    href="/get-started"
                    className={cn(
                      "px-4 py-2 text-sm font-medium transition-colors",
                      isActive('/get-started') 
                        ? "text-black dark:text-white font-semibold" 
                        : "text-black/80 dark:text-white/80 hover:text-black dark:hover:text-white"
                    )}
                  >
                    Get Started
                  </Link>
                </NavigationMenuLink>
              </NavigationMenuItem>

              <NavigationMenuItem>
                <NavigationMenuLink asChild>
                  <Link
                    href="/features"
                    className={cn(
                      "px-4 py-2 text-sm font-medium transition-colors",
                      isActive('/features') 
                        ? "text-black dark:text-white font-semibold" 
                        : "text-black/80 dark:text-white/80 hover:text-black dark:hover:text-white"
                    )}
                  >
                    Features
                  </Link>
                </NavigationMenuLink>
              </NavigationMenuItem>

              <NavigationMenuItem>
                <NavigationMenuLink asChild>
                  <Link
                    href="/pricing"
                    className={cn(
                      "px-4 py-2 text-sm font-medium transition-colors",
                      isActive('/pricing') 
                        ? "text-black dark:text-white font-semibold" 
                        : "text-black/80 dark:text-white/80 hover:text-black dark:hover:text-white"
                    )}
                  >
                    Pricing
                  </Link>
                </NavigationMenuLink>
              </NavigationMenuItem>

              <NavigationMenuItem>
                <NavigationMenuLink asChild>
                  <Link
                    href="/faq"
                    className={cn(
                      "px-4 py-2 text-sm font-medium transition-colors",
                      isActive('/faq') 
                        ? "text-black dark:text-white font-semibold" 
                        : "text-black/80 dark:text-white/80 hover:text-black dark:hover:text-white"
                    )}
                  >
                    FAQ
                  </Link>
                </NavigationMenuLink>
              </NavigationMenuItem>

              <NavigationMenuItem>
                <NavigationMenuLink asChild>
                  <Link
                    href="/research"
                    className={cn(
                      "px-4 py-2 text-sm font-medium transition-colors",
                      isActive('/research') 
                        ? "text-black dark:text-white font-semibold" 
                        : "text-black/80 dark:text-white/80 hover:text-black dark:hover:text-white"
                    )}
                  >
                    Research
                  </Link>
                </NavigationMenuLink>
              </NavigationMenuItem>

              {user && (
                <NavigationMenuItem>
                  <NavigationMenuLink asChild>
                    <Link
                      href="/dashboard"
                      className={cn(
                        "px-4 py-2 text-sm font-medium transition-colors",
                        isActive('/dashboard') 
                          ? "text-black dark:text-white font-semibold" 
                          : "text-black/80 dark:text-white/80 hover:text-black dark:hover:text-white"
                      )}
                    >
                      Dashboard
                    </Link>
                  </NavigationMenuLink>
                </NavigationMenuItem>
              )}
            </NavigationMenuList>
          </NavigationMenu>

          {/* Right side - Auth buttons and theme toggle */}
          <div className="hidden lg:flex items-center space-x-3">
            <Link href="/login">
              <Button
                variant="ghost"
                size="sm"
                className="text-black/80 dark:text-white/80 hover:text-black dark:hover:text-white"
              >
                Login
              </Button>
            </Link>
            <Link href="/signup">
              <Button
                size="sm"
                className="bg-black dark:bg-white text-white dark:text-black hover:bg-black/90 dark:hover:bg-white/90"
              >
                Sign Up
              </Button>
            </Link>
            <ModeToggle />
          </div>

          {/* Mobile Menu Toggle */}
          <div className="lg:hidden flex items-center space-x-2">
            <ModeToggle />
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

        {/* Enhanced Mobile Menu */}
        <AnimatePresence>
          {menuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.3, ease: "easeInOut" }}
              className="lg:hidden overflow-hidden overflow-x-hidden bg-white/95 dark:bg-black/95 backdrop-blur-md border-t border-black/10 dark:border-white/10 w-full"
            >
              <motion.div
                initial={{ y: -20 }}
                animate={{ y: 0 }}
                exit={{ y: -20 }}
                transition={{ duration: 0.3, delay: 0.1 }}
                className="px-3 sm:px-4 py-6 space-y-6 w-full"
              >
                {/* Navigation Links */}
                <div className="space-y-4 w-full">
                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.1 }}
                  >
                    <Link
                      href="/"
                      className={cn(
                        "block text-lg font-medium transition-colors",
                        isActive('/') 
                          ? "text-black dark:text-white font-semibold" 
                          : "text-black dark:text-white hover:text-black/70 dark:hover:text-white/70"
                      )}
                      onClick={() => setMenuOpen(false)}
                    >
                      Home
                    </Link>
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.15 }}
                  >
                    <Link
                      href="/get-started"
                      className={cn(
                        "block text-lg font-medium transition-colors",
                        isActive('/get-started') 
                          ? "text-black dark:text-white font-semibold" 
                          : "text-black dark:text-white hover:text-black/70 dark:hover:text-white/70"
                      )}
                      onClick={() => setMenuOpen(false)}
                    >
                      Get Started
                    </Link>
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.2 }}
                  >
                    <Link
                      href="/features"
                      className={cn(
                        "block text-lg font-medium transition-colors",
                        isActive('/features') 
                          ? "text-black dark:text-white font-semibold" 
                          : "text-black dark:text-white hover:text-black/70 dark:hover:text-white/70"
                      )}
                      onClick={() => setMenuOpen(false)}
                    >
                      Features
                    </Link>
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.25 }}
                  >
                    <Link
                      href="/pricing"
                      className={cn(
                        "block text-lg font-medium transition-colors",
                        isActive('/pricing') 
                          ? "text-black dark:text-white font-semibold" 
                          : "text-black dark:text-white hover:text-black/70 dark:hover:text-white/70"
                      )}
                      onClick={() => setMenuOpen(false)}
                    >
                      Pricing
                    </Link>
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.3 }}
                  >
                    <Link
                      href="/faq"
                      className={cn(
                        "block text-lg font-medium transition-colors",
                        isActive('/faq') 
                          ? "text-black dark:text-white font-semibold" 
                          : "text-black dark:text-white hover:text-black/70 dark:hover:text-white/70"
                      )}
                      onClick={() => setMenuOpen(false)}
                    >
                      FAQ
                    </Link>
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.35 }}
                  >
                    <Link
                      href="/research"
                      className={cn(
                        "block text-lg font-medium transition-colors",
                        isActive('/research') 
                          ? "text-black dark:text-white font-semibold" 
                          : "text-black dark:text-white hover:text-black/70 dark:hover:text-white/70"
                      )}
                      onClick={() => setMenuOpen(false)}
                    >
                      Research
                    </Link>
                  </motion.div>

                  {user && (
                    <motion.div
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.4 }}
                    >
                      <Link
                        href="/dashboard"
                        className={cn(
                          "block text-lg font-medium transition-colors",
                          isActive('/dashboard') 
                            ? "text-black dark:text-white font-semibold" 
                            : "text-black dark:text-white hover:text-black/70 dark:hover:text-white/70"
                        )}
                        onClick={() => setMenuOpen(false)}
                      >
                        Dashboard
                      </Link>
                    </motion.div>
                  )}
                </div>

                {/* Auth Buttons */}
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 }}
                  className="space-y-3 pt-4 border-t border-black/10 dark:border-white/10"
                >
                  <Link href="/login">
                    <Button
                      variant="outline"
                      size="lg"
                      className="w-full mb-3 text-black dark:text-white border-black/20 dark:border-white/20 hover:bg-black/5 dark:hover:bg-white/5 "
                      onClick={() => setMenuOpen(false)}
                    >
                      Login
                    </Button>
                  </Link>
                  <Link href="/signup">
                    <Button
                      size="lg"
                      className="w-full bg-black dark:bg-white text-white dark:text-black hover:bg-black/90 dark:hover:bg-white/90"
                      onClick={() => setMenuOpen(false)}
                    >
                      Sign Up
                    </Button>
                  </Link>
                </motion.div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </nav>
  );
};

export default CleanNavigation;
