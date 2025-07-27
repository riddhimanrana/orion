"use client";

import React from "react";

export function PrivacyContent() {
  return (
    <div className="min-h-screen bg-white dark:bg-black pt-20">
      <div className="container mx-auto px-4 py-16 max-w-4xl">
        <h1 className="text-3xl font-bold text-black dark:text-white mb-4">
          Privacy Policy
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-8">
          Last updated July 21, 2025
        </p>

        <section className="mb-8">
          <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
            1. Introduction
          </h2>
          <p className="text-gray-700 dark:text-gray-300">
            At Orion, we value your privacy. This Privacy Policy explains what
            information we collect, how we use it, and your rights regarding
            your data. We are committed to protecting your personal information
            and being transparent about our data practices.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
            2. Information We Collect
          </h2>
          <p className="text-gray-700 dark:text-gray-300">
            We collect different types of data to provide and improve our
            services:
          </p>
          <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 mt-2">
            <li>
              <strong>Personal Information:</strong> When you sign up or contact
              us, we collect your name, email address, and any other details you
              provide.
            </li>
            <li>
              <strong>Usage Data:</strong> We collect data about your
              interactions with the platform, including browsing behavior and
              feature usage. This helps us analyze trends and improve our
              services.
            </li>
            <li>
              <strong>Cookies and Tracking Technologies:</strong> We use cookies
              and similar tracking technologies to personalize your experience
              and monitor website performance.
            </li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
            3. How We Use Your Data
          </h2>
          <p className="text-gray-700 dark:text-gray-300">
            We use the collected data to:
          </p>
          <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 mt-2">
            <li>Facilitate and enhance the user experience on Orion.</li>
            <li>Provide relevant features and recommendations.</li>
            <li>Improve our platform through analytics and user feedback.</li>
            <li>
              Communicate updates, notifications, and important service
              announcements.
            </li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
            4. Third-Party Services
          </h2>
          <p className="text-gray-700 dark:text-gray-300">
            We collaborate with third-party services to optimize our platform:
          </p>
          <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 mt-2">
            <li>
              <strong>Supabase:</strong> For secure data storage and management.
            </li>
            <li>
              <strong>PostHog:</strong> To analyze usage data and enhance user
              experience.
            </li>
          </ul>
          <p className="text-gray-700 dark:text-gray-300 mt-2">
            These services have their own privacy policies, and by using Orion,
            you also agree to their data processing practices.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
            5. Data Security
          </h2>
          <p className="text-gray-700 dark:text-gray-300">
            We implement strict security measures to protect your personal data
            from unauthorized access, loss, or misuse. However, no system is
            completely secure, and we cannot guarantee absolute protection. We
            encourage users to take precautions, such as using strong passwords
            and being mindful of data sharing.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
            6. Your Rights
          </h2>
          <p className="text-gray-700 dark:text-gray-300">
            You have the right to:
          </p>
          <ul className="list-disc list-inside text-gray-700 dark:text-gray-300 mt-2">
            <li>Access the personal data we hold about you.</li>
            <li>Request corrections or deletions of inaccurate information.</li>
            <li>Withdraw consent for data processing where applicable.</li>
            <li>
              Opt out of analytics tracking by adjusting your browser settings
              or using available opt-out tools.
            </li>
            <li>
              Delete your account and all associated personal data at any time.
              If you wish to delete your account, you can do so in your account
              settings or by contacting{" "}
              <a
                href="mailto:privacy@orionlive.ai"
                className="text-blue-600 dark:text-blue-400 underline"
              >
                privacy@orionlive.ai
              </a>
              .
            </li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
            7. Retention of Data
          </h2>
          <p className="text-gray-700 dark:text-gray-300">
            We retain personal data only for as long as necessary to fulfill the
            purposes outlined in this Privacy Policy. When data is no longer
            needed, we securely delete or anonymize it. If you request account
            deletion, we will remove your personal information from our system
            within a reasonable timeframe, subject to any legal obligations.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
            8. Changes to this Policy
          </h2>
          <p className="text-gray-700 dark:text-gray-300">
            We may update this Privacy Policy to reflect changes in our
            practices or legal requirements. Significant changes will be
            communicated via email or website notifications. We recommend
            reviewing this policy periodically.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-black dark:text-white mb-2">
            9. Contact
          </h2>
          <p className="text-gray-700 dark:text-gray-300">
            For privacy-related inquiries, email us at{" "}
            <a
              href="mailto:privacy@orionlive.ai"
              className="text-blue-600 dark:text-blue-400 underline"
            >
              privacy@orionlive.ai
            </a>
            .
          </p>
        </section>
      </div>
    </div>
  );
}
