"use client";

import { SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import { usePathname } from "next/navigation";

export function DashboardHeader() {
  const pathname = usePathname();
  
  const getPageName = () => {
    const paths = pathname.split('/').filter(Boolean);
    
    if (paths.length > 1) {
      if (paths[1] === 'account') {
        return 'Account';
      } else if (paths[1] === 'activity') {
        return 'Activity';
      }
    }
    
    return 'Dashboard';
  };

  const pageName = getPageName();

  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mr-2 h-4 data-[orientation=vertical]" />
      <h1 className="text-base font-medium">{pageName}</h1>
    </header>
  );
}
