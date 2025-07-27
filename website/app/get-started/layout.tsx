import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Get Started - Orion Live",
  description:
    "Set up Orion Live on your devices and start using visual AI. Download the iPhone app and optional Mac server for local inference.",
};

export default function GetStartedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
