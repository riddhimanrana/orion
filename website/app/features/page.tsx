import type { Metadata } from "next";
import React from "react";
import { generateMetadata, PAGE_METADATA } from "@/lib/metadata";
import { FeaturesContent } from "@/components/features/features-content";

export const metadata: Metadata = generateMetadata(PAGE_METADATA.features);

export default function FeaturesPage() {
  return <FeaturesContent />;
}
