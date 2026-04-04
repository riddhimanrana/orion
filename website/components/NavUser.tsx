"use client";

import {
  ChevronsUpDown,
  LogOut,
  Crown,
  MessageSquare,
  Sun,
  Moon,
  MonitorSmartphone,
} from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { useUser } from "@/hooks/use-user";
import { useSubscription } from "@/hooks/use-subscription";
import { UserAvatar } from "@/components/UserAvatar";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";
import Link from "next/link";

export function NavUser() {
  const { isMobile } = useSidebar();
  const { user, signOut } = useUser();
  const { subscriptionTier } = useSubscription();
  const { theme, setTheme } = useTheme();

  if (!user) return null;

  const userName = user.user_metadata?.full_name || user.email || "User";
  const userEmail = user.email || "";

  const handleSignOut = async () => {
    await signOut();
    window.location.href = "/";
  };

  const ThemeSelector = () => (
    <div className="relative flex items-center border rounded-lg p-0.5 space-x-1">
      <Button
        variant="ghost"
        size="icon"
        className={cn(
          "relative z-10 h-6 w-6 flex items-center justify-center rounded-md",
          theme === "light" && "text-sidebar-primary bg-sidebar-primary-foreground hover:text-sidebar-primary/90 hover:bg-sidebar-primary-foreground/90"
        )}
        onClick={() => setTheme("light")}
      >
        <Sun className="h-3 w-3" />
      </Button>
      <Button 
        variant="ghost"
        size="icon"
        className={cn(
          "relative z-10 h-6 w-6 flex items-center justify-center rounded-md",
          theme === "dark" && "text-sidebar-primary bg-sidebar-primary-foreground/90 hover:text-sidebar-primary hover:bg-sidebar-primary-foreground/90"
        )}
        onClick={() => setTheme("dark")}
      >
        <Moon className="h-3 w-3" />
      </Button>
      <Button
        variant="ghost" 
        size="icon"
        className={cn(
          "relative z-10 h-6 w-6 flex items-center justify-center rounded-md",
          theme === "system" && "text-sidebar-primary bg-sidebar-primary-foreground hover:text-sidebar-primary/90 hover:bg-sidebar-primary-foreground/90"
        )}
        onClick={() => setTheme("system")}
      >
        <MonitorSmartphone className="h-3 w-3" />
      </Button>
    </div>
  );

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <UserAvatar user={user} size="sm" className="h-8 w-8 rounded-lg" />
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium flex items-center gap-1">
                  {userName}
                  {subscriptionTier === "pro" && (
                    <Crown className="h-3 w-3 text-amber-500" />
                  )}
                </span>
                <span className="truncate text-xs">{userEmail}</span>
              </div>
              <ChevronsUpDown className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuLabel className="p-0 font-normal">
              <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                <UserAvatar user={user} size="sm" className="h-8 w-8 rounded-lg" />
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-medium flex items-center gap-1">
                    {userName}
                    {subscriptionTier === "pro" && (
                      <Crown className="h-3 w-3 text-amber-500" />
                    )}
                  </span>
                  <span className="truncate text-xs">{userEmail}</span>
                </div>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            {subscriptionTier === "free" && (
              <>
                <DropdownMenuGroup>
                  <DropdownMenuItem asChild>
                    <Link href="/dashboard/account">
                      <Crown />
                      Upgrade to Pro
                    </Link>
                  </DropdownMenuItem>
                </DropdownMenuGroup>
                <DropdownMenuSeparator />
              </>
            )}
            <DropdownMenuGroup>
              <DropdownMenuItem asChild>
                <a
                  href="https://github.com/riddhimanrana/orion/issues"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <MessageSquare />
                  Send Feedback
                </a>
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
                <div className="flex items-center justify-between w-full">
                  <span className="text-sm">Appearance</span>
                  <ThemeSelector />
                </div>
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleSignOut}>
              <LogOut />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
