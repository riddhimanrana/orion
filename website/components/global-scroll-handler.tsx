'use client';

import { useScrollToAnchor } from "@/hooks/use-scroll-to-anchor";

export function GlobalScrollHandler() {
  useScrollToAnchor();
  return null;
}
