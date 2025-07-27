import type { Metadata } from "next";
import React from "react";
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";
import { generateMetadata, PAGE_METADATA } from "@/lib/metadata";

export const metadata: Metadata = generateMetadata(PAGE_METADATA.faq);

export default function FAQPage() {
  return (
    <main className="max-w-2xl mx-auto px-4 py-24">
      <h1 className="text-3xl font-bold mb-6 text-center">
        Frequently Asked Questions
      </h1>
      <section className="mb-10">
        <p className="text-lg mb-4 text-center">
          Here are answers to some common questions about Orion and Orion Live.
        </p>
      </section>
      <section>
        <Accordion type="single" collapsible className="w-full">
          <AccordionItem value="difference-gemini">
            <AccordionTrigger>
              How is this different than Gemini Live?
            </AccordionTrigger>
            <AccordionContent>
              The problem with tools like Gemini Live and OpenAI Sora(Note: As of 7/26/25, OpenAI Sora still lacks the ability to process real-time visual queries) is that they are often slow, require steady cloud processing, and are solely focused on short, user-based interactions. Like imagine you are a blind person who really needs assistance from a tool like this, and imagine that every aspect of your life and every moment and interaction is sent to some Google server hundreds of miles away and you have no clue with who&apos;s accessing that data and what they&apos;re doing with it. To solve that issue, and in many more applications like enterprise security and other systems, I want to create a system architecture like Orion that can bring all of this to happen on device or within your local machine&apos;s capabilities and give you the peace of mind that your data and your privacy are all in your control. With Orion, I aim to change that by providing a system architecture that can run on an entirely local architecture, split processing on edge devices, and provide real-time responses to user queries while maintaining a high quality of output, privacy, and security in various types of environments, maintaining context and memory of the world as it unfolds.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="orion-vs-orion-live">
            <AccordionTrigger>What is Orion vs Orion Live?</AccordionTrigger>
            <AccordionContent>
              <strong>Orion</strong> is the core AI architecture and
              intelligence you interact with. It powers all Orion experiences
              and is designed to be modular and adaptable.
              <br />
              <br />
              <strong>Orion Live</strong> is the mobile app that lets you
              interact with Orion on the go. The naming reflects that Orion is
              the underlying AI, while Orion Live is just one way to access
              it—specifically, through a mobile interface.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="privacy-security">
            <AccordionTrigger>
              How does Orion Live protect my privacy and data?
            </AccordionTrigger>
            <AccordionContent>
              Orion Live processes all visual data locally on your device. No
              images, videos, or personal information are sent to external
              servers unless you explicitly choose to use a cloud feature. Your
              privacy is our top priority.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="supported-devices">
            <AccordionTrigger>
              What devices and platforms does Orion Live support?
            </AccordionTrigger>
            <AccordionContent>
              Orion Live is available for iOS, Android, and web. The Orion
              architecture is designed to run on phones, tablets, and computers,
              with edge computing support for maximum flexibility.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="real-time-vision">
            <AccordionTrigger>
              What is real-time vision and how fast is Orion Live?
            </AccordionTrigger>
            <AccordionContent>
              Orion Live can process visual data in under 50ms, enabling instant
              feedback and interaction. This is possible due to optimized edge
              computing and efficient AI models.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="edge-computing">
            <AccordionTrigger>
              What is edge computing and why does Orion use it?
            </AccordionTrigger>
            <AccordionContent>
              Edge computing means Orion runs directly on your device, not just
              in the cloud. This ensures privacy, speed, and offline
              capabilities, making Orion Live responsive and secure.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="data-storage">
            <AccordionTrigger>
              Where is my data stored and processed?
            </AccordionTrigger>
            <AccordionContent>
              All data is processed locally on your device by default. You can
              opt-in to sync certain data to the cloud for backup or
              cross-device access, but this is never required.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="custom-integrations">
            <AccordionTrigger>
              Can I build custom integrations or extend Orion?
            </AccordionTrigger>
            <AccordionContent>
              Yes! Orion is designed for extensibility. Developers can use the
              Orion API to create custom plugins, integrations, and workflows
              tailored to their needs.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="pricing-licensing">
            <AccordionTrigger>
              What is the pricing model for Orion Live?
            </AccordionTrigger>
            <AccordionContent>
              Orion Live offers a free tier with core features. Premium plans
              unlock advanced capabilities, integrations, and priority support.
              See our{" "}
              <a href="/pricing" className="underline">
                Pricing
              </a>{" "}
              page for details.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="offline-functionality">
            <AccordionTrigger>Does Orion Live work offline?</AccordionTrigger>
            <AccordionContent>
              Yes, Orion Live is fully functional offline for most features.
              Some integrations or cloud sync options require an internet
              connection, but core AI and vision features do not.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="updates-roadmap">
            <AccordionTrigger>
              How often is Orion Live updated? What’s on the roadmap?
            </AccordionTrigger>
            <AccordionContent>
              Orion Live receives regular updates with new features,
              improvements, and bug fixes. Our roadmap includes expanded device
              support, more integrations, and enhanced AI capabilities.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="developer-support">
            <AccordionTrigger>
              Is there developer support or documentation?
            </AccordionTrigger>
            <AccordionContent>
              Yes, we provide comprehensive documentation, sample code, and
              community support for developers building on Orion. Visit our{" "}
              <a href="/research" className="underline">
                Research
              </a>{" "}
              page for resources.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="accessibility">
            <AccordionTrigger>
              Is Orion Live accessible for users with disabilities?
            </AccordionTrigger>
            <AccordionContent>
              Orion Live is designed with accessibility in mind, including
              support for screen readers, voice commands, and customizable UI
              options.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="troubleshooting">
            <AccordionTrigger>
              What should I do if I encounter issues or need help?
            </AccordionTrigger>
            <AccordionContent>
              You can reach out to our support team via the app or website. We
              also offer a comprehensive help center and community forums for
              troubleshooting and advice.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="ai-transparency">
            <AccordionTrigger>
              How transparent is Orion’s AI? Can I see how decisions are made?
            </AccordionTrigger>
            <AccordionContent>
              Orion emphasizes transparency. You can review logs, inspect
              decision flows, and understand how the AI arrives at its
              conclusions. We believe in open, explainable AI.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="security">
            <AccordionTrigger>How secure is Orion Live?</AccordionTrigger>
            <AccordionContent>
              Orion Live uses industry-standard encryption for all data, both at
              rest and in transit. Security audits and regular updates ensure
              your information remains protected.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="future-features">
            <AccordionTrigger>
              What features are planned for the future?
            </AccordionTrigger>
            <AccordionContent>
              Upcoming features include expanded device compatibility, more
              third-party integrations, advanced vision models, and enhanced
              developer tools.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="comparison-other">
            <AccordionTrigger>
              How does Orion Live compare to other visual AI platforms?
            </AccordionTrigger>
            <AccordionContent>
              Orion Live stands out for its privacy-first approach, real-time
              edge processing, extensibility, and transparent AI. Most
              competitors rely heavily on cloud processing and offer less
              control to users and developers.
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </section>
    </main>
  );
}
