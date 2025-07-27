"use client";

import React from "react";
import { motion } from "motion/react";
import Link from "next/link";
import {
  ArrowRight,
  Shield,
  Zap,
  Brain,
  Eye,
  Server,
  Search,
  AlertTriangle,
  Microscope
} from "lucide-react";

// Import our clean components
import { SimpleNodes } from "@/components/ui/simple-nodes";
import {
  ScrollAnimation,
  ScrollReveal,
} from "@/components/ui/scroll-animation";
import { Cover } from "@/components/ui/cover";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export function HomeContent() {  
  return (
    <div className="min-h-screen overflow-hidden bg-white dark:bg-black text-black dark:text-white">
      {/* Hero Section */}
      <section
        id="hero"
        className="relative min-h-screen flex items-center justify-center"
      >
        <SimpleNodes
          className="z-0"
          baseNodeDensity={0.2}
          speed={0.07}
          baseNodeSize={1.5}
          baseConnectionDistance={100}
          enableConnections={true}
        />

        <div className="relative z-10 max-w-4xl mx-auto px-4 text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="mb-8"
          >
            {/* <div className="flex justify-center mb-8">
              <div className="relative w-20 h-20">
                <Image
                  src="/orion.svg"
                  alt="Orion"
                  width={80}
                  height={80}
                  className="w-full h-full"
                />
              </div>
            </div> */}
          </motion.div>

          <motion.h1
            className="text-5xl md:text-6xl lg:text-7xl font-bold max-w-7xl mx-auto text-center mt-6 relative z-20 py-6 bg-clip-text text-transparent bg-gradient-to-b from-neutral-800 via-neutral-700 to-neutral-700 dark:from-neutral-800 dark:via-white dark:to-white"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
          >
            Real-time Visual Intelligence at{" "}
            {/* Mobile: block with margin, Desktop: inline */}
            <div className="mt-1 sm:hidden">
              <Cover>speed</Cover>
            </div>
            <span className="hidden sm:inline">
              <Cover>speed</Cover>
            </span>
          </motion.h1>

          <motion.p
            className="text-lg md:text-2xl text-black/60 dark:text-white/60 mb-6 md:mb-12 max-w-3xl mx-auto leading-relaxed"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.4 }}
          >
            Orion Live brings real-time visual understanding to your device with
            privacy-first architecture and temporal memory
          </motion.p>

          <motion.div
            className="flex justify-center mb-8"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.5 }}
          >
            <Badge variant="outline" className="px-3 py-1.5 text-xs font-medium border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/50">
              <AlertTriangle className="w-3 h-3 mr-1.5" />
              Currently in Research & Development
            </Badge>
          </motion.div>

          <motion.div
            className="flex flex-col sm:flex-row items-center justify-center gap-4 px-4 sm:px-0 w-full sm:w-auto"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.6 }}
          >
            <Link href="/get-started" className="w-full sm:w-auto">
              <Button className="w-full h-12 sm:h-11 px-8 font-semibold text-sm group/arrow shadow-sm hover:shadow-md transform transition-all duration-200 hover:scale-[1.03]">
                Get Started
                <ArrowRight className="size-4 group-hover/arrow:translate-x-1 transition-transform duration-500" />
              </Button>
            </Link>
            <Link href="/research" className="w-full sm:w-auto">
              <Button
                variant="outline"
                className="w-full h-12 sm:h-11 px-8 text-sm hover:bg-secondary/80 transition-colors"
              >
                <Microscope className="size-4" />
                Explore Research
              </Button>
            </Link>
          </motion.div>

          {/* Stats */}
          <motion.div
            className="grid grid-cols-2 md:grid-cols-4 gap-8 mt-16 pt-16 border-t border-black/10 dark:border-white/10"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.8 }}
          >
            <div className="text-center">
              <div className="text-3xl font-bold text-black dark:text-white mb-2">
                &lt;50ms
              </div>
              <div className="text-sm text-black/60 dark:text-white/60">
                Response Time
              </div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-black dark:text-white mb-2">
                100%
              </div>
              <div className="text-sm text-black/60 dark:text-white/60">
                Local Processing
              </div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-black dark:text-white mb-2">
                2.4x
              </div>
              <div className="text-sm text-black/60 dark:text-white/60">
                Faster Than Gemini Live(as per initial testing)
              </div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-black dark:text-white mb-2">
                24/7
              </div>
              <div className="text-sm text-black/60 dark:text-white/60">
                Memory Retention
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Problem Section */}
      <section id="problems" className="py-20 px-4 bg-white dark:bg-black">
        <div className="max-w-6xl mx-auto">
          <ScrollAnimation animationType="slideUp" duration={0.8}>
            <div className="text-center mb-16">
              <h2 className="text-4xl md:text-5xl font-bold mb-6 text-black dark:text-white">
                Current AI Vision is Broken
              </h2>
              <p className="text-xl text-black/60 dark:text-white/60 max-w-3xl mx-auto">
                Despite billions in investment, today&apos;s AI vision systems
                fail when you need them most. They&apos;re too slow, too
                invasive, and too unreliable for real-world use.
              </p>
            </div>
          </ScrollAnimation>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            <ScrollReveal direction="up" delay={0.1}>
              <div className="p-6 bg-black/5 dark:bg-white/5 rounded-lg border border-black/10 dark:border-white/10">
                <div className="text-red-400 text-sm font-medium mb-2">
                  Critical
                </div>
                <h3 className="text-lg font-semibold mb-3 text-black dark:text-white">
                  Too Slow for Real-Time
                </h3>
                <p className="text-black/60 dark:text-white/60 text-sm">
                  Current AI models take seconds to process visual data, making
                  them useless for interactive applications.
                </p>
              </div>
            </ScrollReveal>

            <ScrollReveal direction="up" delay={0.2}>
              <div className="p-6 bg-black/5 dark:bg-white/5 rounded-lg border border-black/10 dark:border-white/10">
                <div className="text-orange-400 text-sm font-medium mb-2">
                  High
                </div>
                <h3 className="text-lg font-semibold mb-3 text-black dark:text-white">
                  Privacy Nightmare
                </h3>
                <p className="text-black/60 dark:text-white/60 text-sm">
                  Your personal videos are sent to remote servers, creating
                  massive privacy and security risks.
                </p>
              </div>
            </ScrollReveal>

            <ScrollReveal direction="up" delay={0.3}>
              <div className="p-6 bg-black/5 dark:bg-white/5 rounded-lg border border-black/10 dark:border-white/10">
                <div className="text-orange-400 text-sm font-medium mb-2">
                  High
                </div>
                <h3 className="text-lg font-semibold mb-3 text-black dark:text-white">
                  Visual Hallucinations
                </h3>
                <p className="text-black/60 dark:text-white/60 text-sm">
                  Models often &apos;see&apos; things that aren&apos;t there or
                  miss critical visual details entirely.
                </p>
              </div>
            </ScrollReveal>

            <ScrollReveal direction="up" delay={0.4}>
              <div className="p-6 bg-black/5 dark:bg-white/5 rounded-lg border border-black/10 dark:border-white/10">
                <div className="text-yellow-400 text-sm font-medium mb-2">
                  Medium
                </div>
                <h3 className="text-lg font-semibold mb-3 text-black dark:text-white">
                  No Memory
                </h3>
                <p className="text-black/60 dark:text-white/60 text-sm">
                  AI forgets everything between interactions, unable to build
                  understanding over time.
                </p>
              </div>
            </ScrollReveal>
          </div>
        </div>
      </section>

      {/* Solution Section */}
      <section id="features" className="py-20 px-4 bg-white dark:bg-black">
        <div className="max-w-6xl mx-auto">
          <ScrollAnimation animationType="slideUp" duration={0.8}>
            <div className="text-center mb-16">
              <h2 className="text-4xl md:text-5xl font-bold mb-6 text-black dark:text-white">
                Meet Orion
              </h2>
              <p className="text-xl text-black/60 dark:text-white/60 max-w-3xl mx-auto">
                A revolutionary hybrid architecture that brings real-time visual
                AI to your device while keeping your data private and secure.
              </p>
            </div>
          </ScrollAnimation>

          <div className="grid md:grid-cols-2 gap-12 items-center">
            <ScrollReveal direction="left" distance={50}>
              <div className="space-y-8">
                <div className="flex items-start space-x-4">
                  <div className="flex-shrink-0 w-12 h-12 bg-black/10 dark:bg-white/10 rounded-lg flex items-center justify-center">
                    <Zap className="w-6 h-6 text-black dark:text-white" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold mb-2 text-black dark:text-white">
                      Lightning Fast
                    </h3>
                    <p className="text-black/60 dark:text-white/60">
                      Process visual data in under 50ms for real-time
                      applications
                    </p>
                  </div>
                </div>

                <div className="flex items-start space-x-4">
                  <div className="flex-shrink-0 w-12 h-12 bg-black/10 dark:bg-white/10 rounded-lg flex items-center justify-center">
                    <Shield className="w-6 h-6 text-black dark:text-white" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold mb-2 text-black dark:text-white">
                      Privacy First
                    </h3>
                    <p className="text-black/60 dark:text-white/60">
                      Your videos never leave your device, always
                    </p>
                  </div>
                </div>

                <div className="flex items-start space-x-4">
                  <div className="flex-shrink-0 w-12 h-12 bg-black/10 dark:bg-white/10 rounded-lg flex items-center justify-center">
                    <Server className="w-6 h-6 text-black dark:text-white" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold mb-2 text-black dark:text-white">
                      Edge Processing
                    </h3>
                    <p className="text-black/60 dark:text-white/60">
                      Runs on your phone, tablet, or computer
                    </p>
                  </div>
                </div>

                <div className="flex items-start space-x-4">
                  <div className="flex-shrink-0 w-12 h-12 bg-black/10 dark:bg-white/10 rounded-lg flex items-center justify-center">
                    <Brain className="w-6 h-6 text-black dark:text-white" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold mb-2 text-black dark:text-white">
                      Smart Memory
                    </h3>
                    <p className="text-black/60 dark:text-white/60">
                      Builds understanding over time
                    </p>
                  </div>
                </div>
              </div>
            </ScrollReveal>

            <ScrollReveal direction="right" distance={50}>
              <div className="relative bg-black/5 dark:bg-white/5 rounded-xl p-8 border border-black/10 dark:border-white/10">
                <div className="space-y-6">
                  <div>
                    <div className="text-sm text-black/60 dark:text-white/60 mb-1">
                      9:00 AM - Kitchen
                    </div>
                    <div className="bg-black/10 dark:bg-white/10 rounded-lg p-4">
                      <p className="text-black/80 dark:text-white/80 text-sm">
                        &quot;Person placing keys on counter next to coffee
                        maker&quot;
                      </p>
                    </div>
                  </div>

                  <div>
                    <div className="text-sm text-black/60 dark:text-white/60 mb-1">
                      11:30 AM - User asks
                    </div>
                    <div className="bg-black/10 dark:bg-white/10 rounded-lg p-4">
                      <p className="text-black dark:text-white font-mono text-sm">
                        &quot;Where are my keys?&quot;
                      </p>
                    </div>
                  </div>

                  <div>
                    <div className="text-sm text-black/60 dark:text-white/60 mb-1">
                      Orion responds
                    </div>
                    <div className="bg-black/10 dark:bg-white/10 rounded-lg p-4">
                      <p className="text-black/80 dark:text-white/80 text-sm">
                        &quot;I saw your keys on the kitchen counter at 9:00 AM,
                        next to the coffee maker.&quot;
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </ScrollReveal>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="py-20 px-4 bg-white dark:bg-black">
        <div className="max-w-6xl mx-auto">
          <ScrollAnimation animationType="slideUp" duration={0.8}>
            <div className="text-center mb-16">
              <h2 className="text-4xl md:text-5xl font-bold mb-6 text-black dark:text-white">
                How Orion Works
              </h2>
              <p className="text-xl text-black/60 dark:text-white/60 max-w-3xl mx-auto">
                A simple 4-step process that transforms how AI understands your
                visual world
              </p>
            </div>
          </ScrollAnimation>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {[
              {
                step: "01",
                title: "Visual Detection",
                description:
                  "Your device's camera captures the scene and immediately processes it using advanced object detection.",
                icon: Eye,
              },
              {
                step: "02",
                title: "Semantic Uplift",
                description:
                  "Raw detections are transformed into rich, structured descriptions that capture context.",
                icon: Brain,
              },
              {
                step: "03",
                title: "Memory Storage",
                description:
                  "Descriptions are stored in a searchable memory system that builds understanding over time.",
                icon: Server,
              },
              {
                step: "04",
                title: "Intelligent Responses",
                description:
                  "When you ask questions, Orion searches its memory and provides contextual answers.",
                icon: Search,
              },
            ].map((item, index) => (
              <ScrollReveal key={index} direction="up" delay={index * 0.1}>
                <div className="text-center">
                  <div className="w-16 h-16 bg-black/10 dark:bg-white/10 rounded-full flex items-center justify-center mx-auto mb-6">
                    <item.icon className="w-8 h-8 text-black dark:text-white" />
                  </div>
                  <div className="text-2xl font-bold text-black/40 dark:text-white/40 mb-2">
                    {item.step}
                  </div>
                  <h3 className="text-xl font-bold mb-4 text-black dark:text-white">
                    {item.title}
                  </h3>
                  <p className="text-black/60 dark:text-white/60 text-sm leading-relaxed">
                    {item.description}
                  </p>
                </div>
              </ScrollReveal>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section
        id="get-started"
        className="py-20 px-4 bg-white dark:bg-black border-t border-black/10 dark:border-white/10"
      >
        <div className="max-w-4xl mx-auto text-center">
          <ScrollAnimation animationType="slideUp" duration={0.8}>
            <h2 className="text-4xl md:text-5xl font-bold mb-6 text-black dark:text-white">
              Ready to Experience The Future?
            </h2>
            <p className="sm:text-xl texl-lg text-black/60 dark:text-white/60 mb-12 max-w-2xl mx-auto">
              Whether you&#39;re a developer, researcher, or enthusiast, Orion
              is ready to transform your visual AI projects. Start now or
              explore our research to learn more.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link href="/get-started" className="w-full sm:w-auto">
                <Button className="w-full sm:w-auto h-12 px-8 font-semibold text-sm flex items-center justify-center gap-2">
                  Get Started
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </Link>
              <Link href="/research" className="w-full sm:w-auto">
                <Button
                  variant="outline"
                  className="w-full sm:w-auto h-12 px-8 font-semibold text-sm flex items-center justify-center gap-2"
                >
                  View Research
                  <Search className="w-4 h-4" />
                </Button>
              </Link>
            </div>
          </ScrollAnimation>
        </div>
      </section>
    </div>
  );
}
