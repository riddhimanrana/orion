import type { Metadata } from "next";
import React from "react";
import { generateMetadata, PAGE_METADATA } from "@/lib/metadata";
import { TermsContent } from "@/components/terms/terms-content";

export const metadata: Metadata = generateMetadata(PAGE_METADATA.privacy);

export default function PrivacyPage() {
  return <TermsContent />;
}
