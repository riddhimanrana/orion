import type { Metadata } from "next";
import React from "react";
import { generateMetadata, PAGE_METADATA } from "@/lib/metadata";
import { HomeContent } from "@/components/home/home-content";

export const metadata: Metadata = generateMetadata(PAGE_METADATA.home);

export default function Home() {
  return <HomeContent />;
}
