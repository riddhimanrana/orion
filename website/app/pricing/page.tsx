import type { Metadata } from "next";
import React from "react";
import { generateMetadata, PAGE_METADATA } from "@/lib/metadata";
import { PricingContent } from "@/components/pricing/pricing-content";

export const metadata: Metadata = generateMetadata(PAGE_METADATA.pricing);

export default function PricingPage() {
  return <PricingContent />;
}
