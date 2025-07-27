import type { Metadata } from "next";
import { generateMetadata, PAGE_METADATA } from "@/lib/metadata";
import { ResearchPageClient } from "../../components/research/research-page-client";

export const metadata: Metadata = generateMetadata(PAGE_METADATA.research);

export default function ResearchPage() {
	return <ResearchPageClient />;
}
