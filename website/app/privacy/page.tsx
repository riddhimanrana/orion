import type { Metadata } from "next";
import React from "react";
import { generateMetadata, PAGE_METADATA } from "@/lib/metadata";
import { PrivacyContent } from "@/components/privacy/privacy-content";

export const metadata: Metadata = generateMetadata(PAGE_METADATA.privacy);

export default function PrivacyPage() {
  return <PrivacyContent />;
}
