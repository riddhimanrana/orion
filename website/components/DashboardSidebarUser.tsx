"use client";

import React from "react";
import { useUser } from "@/hooks/use-user";
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import Image from "next/image";

export default function DashboardSidebarUser() {
  const { user } = useUser();

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton
          size="lg"
          className="data-[slot=sidebar-menu-button]:!p-1.5"
        >
          <div className="flex aspect-square size-8 items-center justify-center rounded-lg">
            <Image
              src="/orion.svg"
              alt="Orion Live"
              width={24}
              height={24}
              className="size-6"
            />
          </div>
          <div className="grid flex-1 text-left text-sm leading-tight">
            <span className="truncate font-semibold">Orion Live</span>
            <span className="truncate text-xs">
              {user?.user_metadata?.full_name || user?.email || "Dashboard"}
            </span>
          </div>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
