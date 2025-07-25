import type { Metadata } from "next";

// Simple site configuration
const SITE_CONFIG = {
  name: "Orion Live",
  url: process.env.NEXT_PUBLIC_SITE_URL || "https://orionlive.ai",
};

interface SimpleMetadataConfig {
  title: string;
  description: string;
}

/**
 * Generate simple metadata with just title and description
 */
export function generateMetadata(config: SimpleMetadataConfig): Metadata {
  return {
    title: config.title,
    description: config.description,
    openGraph: {
      title: config.title,
      description: config.description,
      url: SITE_CONFIG.url,
      siteName: SITE_CONFIG.name,
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title: config.title,
      description: config.description,
    },
  };
}

/**
 * Page-specific metadata configurations
 */
export const PAGE_METADATA = {
  home: {
    title: "Orion Live: Real-time, privacy first visual AI for everyone",
    description:
      "Experience real-time AI that sees, remembers, and understands your world while keeping your privacy intact. Revolutionary visual perception with hybrid edge-server architecture.",
  },
  features: {
    title: "Features - Orion Live",
    description:
      "Discover Orion Live's powerful features: real-time visual processing, edge computing, privacy protection, and seamless integration capabilities.",
  },
  pricing: {
    title: "Pricing - Orion Live",
    description:
      "Choose between free local deployment or premium cloud hosting. Transparent pricing for individuals and teams using Orion Live.",
  },
  research: {
    title: "Research - Orion Live",
    description:
      "Deep dive into Orion's research, technical specifications, and open-source contributions to advancing visual AI and privacy-preserving computing.",
  },
  faq: {
    title: "FAQ - Orion Live",
    description:
      "Get answers to common questions about Orion Live, including privacy, technical specifications, pricing, and implementation details.",
  },
  dashboard: {
    title: "Dashboard - Orion Live",
    description:
      "Monitor your Orion Live usage, API calls, and system performance in real-time.",
  },
  account: {
    title: "Account - Orion Live",
    description: "Manage your Orion Live account, billing, and preferences.",
  },
  activity: {
    title: "Activity - Orion Live",
    description: "Track your visual AI processing activity and usage patterns.",
  },
  privacy: {
    title: "Privacy Policy - Orion Live",
    description:
      "Learn how Orion Live protects your privacy and handles your data with our comprehensive privacy policy.",
  },
  terms: {
    title: "Terms of Service - Orion Live",
    description:
      "Review the terms and conditions for using Orion Live and our visual AI platform.",
  },
  login: {
    title: "Sign In - Orion Live",
    description:
      "Sign in to your Orion Live account to access real-time visual AI features and manage your preferences.",
  },
  signup: {
    title: "Sign Up - Orion Live",
    description:
      "Create your Orion Live account to experience real-time visual AI with privacy protection and edge computing.",
  },
  resetPassword: {
    title: "Reset Password - Orion Live",
    description:
      "Reset your Orion Live account password securely to regain access to your visual AI features.",
  },
} as const;

export { SITE_CONFIG };
