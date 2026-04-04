"use client";

import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import Image from "next/image";

export function TeamSwitcher() {

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton
          size="lg"
          className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
        >
          <div className="flex aspect-square size-8 items-center justify-center rounded-lg">
            <Image src="/orion.svg" alt="Orion Live" width={24} height={24} className="size-6" />
          </div>
          <div className="grid flex-1 text-left text-sm leading-tight">
            <div className="flex items-center space-x-2">
              <span className="font-semibold text-lg">Orion Live</span>
              {/* {subscriptionTier === "pro" && (
                <Badge
                  className=" px-2 py-0.5 text-xs font-medium border border-amber-400 dark:border-amber-500 text-amber-600 dark:text-amber-400 rounded-sm inline-flex items-center bg-transparent"
                >
                  <span>PRO</span>
                </Badge>
              )} */}
            </div>
          </div>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
