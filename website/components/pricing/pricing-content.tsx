"use client";

import React from "react";
import { motion } from "framer-motion";
import { Check, Download, Cloud, Zap, Shield, Globe, Wrench } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";

export function PricingContent() {
  const plans = [
    {
      name: "Free Tier",
      price: "Free",
      description: "Perfect for development and testing",
      icon: Download,
      popular: false,
      features: [
        "Local Mac server deployment",
        "Full privacy - data never leaves your device",
        "Standard inference speed",
        "Basic API access",
        "Local model storage",
        "GitHub source code access",
      ],
      cta: "Get Started",
      ctaVariant: "outline" as const,
      ctaLink: "/get-started",
    },
    {
      name: "Pro Features",
      price: "Coming Soon",
      description: "Enhanced performance features (in development)",
      icon: Cloud,
      popular: true,
      features: [
        "Cloud-hosted infrastructure",
        "3x faster inference speed",
        "99.9% uptime guarantee",
        "Advanced API features",
        "Automatic scaling",
        "Priority support",
      ],
      cta: "Enable in Account",
      ctaVariant: "default" as const,
      ctaLink: "/account",
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-white to-gray-50 dark:from-black dark:to-gray-950 pt-20">
      <div className="container mx-auto px-4 py-16">
        {/* Header */}
        <motion.div
          className="text-center mb-16"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <h1 className="text-4xl md:text-6xl font-bold text-black dark:text-white mb-4">
            Pricing & Features
          </h1>
          <p className="text-xl text-gray-600 dark:text-gray-400 max-w-2xl mx-auto mb-6">
            Orion Live is currently in development. All features are free during the development phase.
            Pro features can be enabled in your account settings.
          </p>
          
          {/* Development Status Alert */}
          <div className="max-w-lg mx-auto">
            <Card className="border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-900/20">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Wrench className="h-4 w-4 text-amber-500" />
                  <h3 className="font-semibold text-sm">Currently in Development</h3>
                </div>
                <p className="text-sm text-muted-foreground">
                  No billing is active yet. All features are available for testing and development.
                </p>
              </CardContent>
            </Card>
          </div>
        </motion.div>

        {/* Pricing Cards */}
        <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          {plans.map((plan, index) => (
            <motion.div
              key={plan.name}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: index * 0.1 }}
              className="relative"
            >
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 transform -translate-x-1/2 z-10">
                  <Badge>Most Popular</Badge>
                </div>
              )}

              <Card
                className={`relative h-full ${
                  plan.popular ? "ring-2 ring-black dark:ring-white" : ""
                }`}
              >
                <CardHeader className="text-center">
                  <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                    <plan.icon className="w-6 h-6 text-black dark:text-white" />
                  </div>
                  <CardTitle className="text-2xl">{plan.name}</CardTitle>
                  <CardDescription className="text-base">
                    {plan.description}
                  </CardDescription>
                  <div className="pt-4">
                    <span className="text-4xl font-bold text-black dark:text-white">
                      {plan.price}
                    </span>
                  </div>
                </CardHeader>

                <CardContent className="space-y-6">
                  <Button
                    variant={plan.ctaVariant}
                    size="lg"
                    className="w-full"
                    asChild
                  >
                    <Link href={plan.ctaLink}>
                      {plan.cta}
                    </Link>
                  </Button>

                  <div className="space-y-3">
                    <h4 className="font-semibold text-black dark:text-white">
                      What&apos;s included:
                    </h4>
                    <ul className="space-y-2">
                      {plan.features.map((feature, featureIndex) => (
                        <li
                          key={featureIndex}
                          className="flex items-start gap-3"
                        >
                          <Check className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
                          <span className="text-gray-600 dark:text-gray-400 text-sm">
                            {feature}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

        {/* Feature Comparison */}
        <motion.div
          className="mt-20 text-center"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
        >
          <h2 className="text-2xl font-bold text-black dark:text-white mb-8">
            Why Choose Orion Live?
          </h2>

          <div className="grid md:grid-cols-3 gap-8 max-w-3xl mx-auto">
            <div className="text-center">
              <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center">
                <Zap className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 className="font-semibold text-black dark:text-white mb-2">
                Lightning Fast
              </h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm">
                Process visual data in under 50ms with our optimized inference engine
              </p>
            </div>

            <div className="text-center">
              <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center">
                <Shield className="w-6 h-6 text-green-600 dark:text-green-400" />
              </div>
              <h3 className="font-semibold text-black dark:text-white mb-2">
                Privacy First
              </h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm">
                Your data stays on your device with local processing options
              </p>
            </div>

            <div className="text-center">
              <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-purple-100 dark:bg-purple-900 flex items-center justify-center">
                <Globe className="w-6 h-6 text-purple-600 dark:text-purple-400" />
              </div>
              <h3 className="font-semibold text-black dark:text-white mb-2">
                Open Source
              </h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm">
                Fully open source development with transparent progress and community involvement
              </p>
            </div>
          </div>
        </motion.div>

        {/* FAQ Section */}
        <motion.div
          className="mt-20 max-w-2xl mx-auto"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.4 }}
        >
          <h2 className="text-2xl font-bold text-black dark:text-white text-center mb-8">
            Frequently Asked Questions
          </h2>

          <div className="space-y-6">
            <div className="border-b border-gray-200 dark:border-gray-800 pb-4">
              <h3 className="font-semibold text-black dark:text-white mb-2">
                Is Orion Live free during development?
              </h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm">
                Yes! During the development phase, all features including Pro features 
                are available for free. No billing or payment is required.
              </p>
            </div>

            <div className="border-b border-gray-200 dark:border-gray-800 pb-4">
              <h3 className="font-semibold text-black dark:text-white mb-2">
                How do I enable Pro features?
              </h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm">
                Go to your account settings and click the button to upgrade to Pro. 
                This will enable all Pro features without any charges during development.
              </p>
            </div>

            <div className="border-b border-gray-200 dark:border-gray-800 pb-4">
              <h3 className="font-semibold text-black dark:text-white mb-2">
                When will billing be introduced?
              </h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm">
                Billing will be introduced after the official release. All existing 
                users will be notified well in advance of any pricing changes.
              </p>
            </div>

            <div>
              <h3 className="font-semibold text-black dark:text-white mb-2">
                Can I compile and run Orion Live now?
              </h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm">
                Yes! The entire codebase is open source on GitHub. You can compile 
                and test both the iOS app and Mac server yourself.
              </p>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
