"use client";

import React from "react";

export function TermsContent() {
  return (
    <div className="min-h-screen bg-white dark:bg-black pt-20">
      <div className="container mx-auto px-4 py-16 max-w-4xl">
        <h1 className="text-3xl font-bold text-black dark:text-white mb-4">
          Terms of Service
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-8">
          Last updated July 21, 2025
        </p>

        <section className="mb-8">
          <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
            1. Introduction
          </h2>
          <p className="text-gray-700 dark:text-gray-300">
            Welcome to Orion, a computer vision platform operated by Riddhiman
            Rana, located in the United States. These Terms of Service
            (&quot;Terms&quot;) govern your use of Orion&apos;s services,
            including our local and cloud-based computer vision solutions. By
            accessing or using Orion, you agree to be bound by these Terms and
            our Privacy Policy. If you disagree with any part of these terms,
            you may not access or use our services.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
            2. Service Description
          </h2>
          <p className="text-gray-700 dark:text-gray-300">
            Orion provides cutting-edge computer vision technology with the
            following features:
          </p>
          <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 mt-2">
            <li>Real-time computer vision processing</li>
            <li>
              Privacy-first architecture where raw visual data stays on your
              device
            </li>
            <li>Semantic search and memory capabilities</li>
            <li>Local processing options and cloud-enhanced features</li>
            <li>API access for developers and researchers</li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
            3. User Obligations
          </h2>
          <p className="text-gray-700 dark:text-gray-300">
            As a user of Orion, you agree to:
          </p>
          <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 mt-2">
            <li>
              Provide accurate and current information when creating an account
            </li>
            <li>Maintain the security of your account credentials</li>
            <li>Use Orion only for lawful purposes</li>
            <li>Respect others privacy and intellectual property rights</li>
            <li>Follow all applicable laws and regulations</li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
            4. Payment and Billing
          </h2>
          <p className="text-gray-700 dark:text-gray-300">
            For users of the Cloud Pro Plan, the following terms apply:
          </p>
          <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 mt-2">
            <li>Subscriptions are billed monthly in advance</li>
            <li>Prices are subject to change with 30 days notice</li>
            <li>No refunds for partial months except as required by law</li>
            <li>
              Automatic renewal unless canceled before the next billing cycle
            </li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
            5. Privacy and Data Protection
          </h2>
          <p className="text-gray-700 dark:text-gray-300">
            Your privacy is fundamental to Orion. Our privacy-first architecture
            ensures:
          </p>
          <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 mt-2">
            <li>Raw visual data never leaves your device</li>
            <li>
              Only anonymized text descriptions are processed in the cloud
            </li>
            <li>End-to-end encryption for all data transmission</li>
            <li>Compliance with GDPR, CCPA, and other privacy regulations</li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
            6. Limitations of Liability
          </h2>
          <p className="text-gray-700 dark:text-gray-300">
            Orion is provided &quot;as-is&quot; without warranties of any kind.
            We do not guarantee perfect accuracy in visual processing, and users
            are responsible for validating AI outputs for their use case. Our
            total liability is limited to the amount you paid in the last 12
            months. We are not liable for indirect, incidental, or consequential
            damages.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
            7. Termination
          </h2>
          <p className="text-gray-700 dark:text-gray-300">
            You may terminate your account at any time. We may suspend or
            terminate accounts for violations of these Terms. Upon termination,
            data retention follows our Privacy Policy.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
            8. Changes to These Terms
          </h2>
          <p className="text-gray-700 dark:text-gray-300">
            We may update these Terms to reflect changes in our services or
            legal requirements. Material changes will be announced with 30 days
            notice. Continued use of Orion indicates acceptance of the updated
            terms.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
            9. Contact
          </h2>
          <p className="text-gray-700 dark:text-gray-300">
            For questions about these Terms, contact us at{" "}
            <a
              href="mailto:support@orionlive.ai"
              className="text-blue-600 dark:text-blue-400 underline"
            >
              support@orionlive.ai
            </a>
            .
          </p>
        </section>
      </div>
    </div>
  );
}
