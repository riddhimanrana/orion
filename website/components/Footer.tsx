"use client";
import React from "react";
import Link from "next/link";
import Image from "next/image";
import { Mail, Microscope } from "lucide-react";
import { SiGithub, SiX } from "react-icons/si";
import { cn } from "../lib/utils";

interface FooterProps {
  className?: string;
}

export const CleanFooter = ({ className }: FooterProps) => {
  return (
    <footer
      className={cn(
        "bg-white dark:bg-black border-t border-black/10 dark:border-white/10",
        className,
      )}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
        {/* Mobile layout (simplified) */}
        <div className="flex flex-col space-y-6 lg:hidden">
          {/* Logo */}
          <div className="flex justify-start ml-1">
            <div className="flex items-center space-x-3">
              <div className="relative w-8 h-8">
                <Image
                  src="/orion.svg"
                  alt="Orion"
                  width={32}
                  height={32}
                  className="w-full h-full"
                />
              </div>
              <span className="text-xl font-semibold text-black dark:text-white">
                Orion Live
              </span>
            </div>
          </div>

          {/* Navigation links in grid */}
          <nav className="grid grid-cols-2 gap-x-6 gap-y-4 text-left ml-1">
            <Link
              href="/features"
              className="text-sm text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors"
            >
              Features
            </Link>
            <Link
              href="/research"
              className="text-sm text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors"
            >
              Research
            </Link>
            <Link
              href="/get-started"
              className="text-sm text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors"
            >
              Get Started
            </Link>
            <Link
              href="/privacy"
              className="text-sm text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors"
            >
              Privacy
            </Link>
            <Link
              href="/terms"
              className="text-sm text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors"
            >
              Terms
            </Link>
            <Link
              href="/contact"
              className="text-sm text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors"
            >
              Contact
            </Link>
          </nav>

          {/* Copyright and social media */}
          <div className="flex items-center justify-between ml-1">
            <p className="text-sm text-black/40 dark:text-white/40">
              © 2025 Riddhiman Rana
            </p>
            <div className="flex items-center mr-3 space-x-4">
              <Link
                href="https://github.com/riddhimanrana/orion"
                target="_blank"
                rel="noopener noreferrer"
                className="text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors"
                aria-label="GitHub"
              >
                <SiGithub className="w-5 h-5" />
              </Link>
              <Link
                href="https://x.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors"
                aria-label="X / Twitter"
              >
                <SiX className="w-5 h-5" />
              </Link>
              <Link
                href="mailto:contact@orionlive.ai"
                className="text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors"
                aria-label="Email"
              >
                <Mail className="w-5 h-5" />
              </Link>
            </div>
          </div>
        </div>

        {/* Mobile: Development status at the very bottom */}
        <div className="flex justify-center lg:hidden mt-6">
          <div className="inline-flex items-center space-x-1 px-3 py-2 bg-black/5 dark:bg-white/5 rounded-full border border-black/10 dark:border-white/10">
            <div className="flex items-center space-x-2">
            <Microscope className="w-3.5 h-3.5 text-blue-500" />
            <span className="text-black/60 dark:text-white/60 text-sm font-medium">
              Research Phase
            </span>
            </div>
            
            <div className="flex items-center space-x-2">
              <span className="text-black dark:text-white text-sm font-semibold">2</span>
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
            </div>
          </div>
        </div>

        {/* Desktop layout (original) */}
        <div className="hidden lg:grid lg:grid-cols-5 gap-8">
          {/* Logo and Description */}
          <div className="lg:col-span-2">
            <div className="flex items-center space-x-3 mb-4">
              <div className="relative w-8 h-8">
                <Image
                  src="/orion.svg"
                  alt="Orion"
                  width={32}
                  height={32}
                  className="w-full h-full"
                />
              </div>
              <span className="text-xl font-semibold text-black dark:text-white">
                Orion Live
              </span>
            </div>
            <p className="text-black/60 dark:text-white/60 text-sm leading-relaxed max-w-md">
              Revolutionary computer vision research bringing real-time,
              privacy-first visual AI to everyone.
            </p>
            <div className="flex items-center space-x-4 mt-6">
              <Link
                href="https://github.com/riddhimanrana/orion"
                target="_blank"
                rel="noopener noreferrer"
                className="text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors"
              >
                <SiGithub className="w-5 h-5" />
              </Link>
              <Link
                href="https://x.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors"
              >
                <SiX className="w-5 h-5" />
              </Link>
              <Link
                href="mailto:contact@orionlive.ai"
                className="text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors"
              >
                <Mail className="w-5 h-5" />
              </Link>
            </div>
          </div>

          {/* Product */}
          <div>
            <h3 className="text-black dark:text-white font-medium mb-4">
              Product
            </h3>
            <ul className="space-y-2">
              <li>
                <Link
                  href="/features"
                  className="text-black/60 dark:text-white/60 text-sm hover:text-black dark:hover:text-white transition-colors"
                >
                  Features
                </Link>
              </li>
              <li>
                <Link
                  href="/pricing"
                  className="text-black/60 dark:text-white/60 text-sm hover:text-black dark:hover:text-white transition-colors"
                >
                  Pricing
                </Link>
              </li>
              <li>
                <Link
                  href="/faq"
                  className="text-black/60 dark:text-white/60 text-sm hover:text-black dark:hover:text-white transition-colors"
                >
                  FAQ
                </Link>
              </li>
            </ul>
          </div>

          {/* Research */}
          <div>
            <h3 className="text-black dark:text-white font-medium mb-4">
              Research
            </h3>
            <ul className="space-y-2">
              <li>
                <Link
                  href="/research"
                  className="text-black/60 dark:text-white/60 text-sm hover:text-black dark:hover:text-white transition-colors"
                >
                  Research Overview
                </Link>
              </li>
              <li>
                <Link
                  href="https://github.com/riddhimanrana/orion"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-black/60 dark:text-white/60 text-sm hover:text-black dark:hover:text-white transition-colors"
                >
                  Open Source
                </Link>
              </li>
              <li>
                <Link
                  href="https://huggingface.co/riddhimanrana/fastvlm-0.5b-captions"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-black/60 dark:text-white/60 text-sm hover:text-black dark:hover:text-white transition-colors"
                >
                  Models & Data
                </Link>
              </li>
            </ul>
          </div>

          {/* Company & Legal */}
          <div>
            {/* <h3 className="text-white font-medium mb-4">Company</h3>
            <ul className="space-y-2">
              <li>
                <Link
                  href="/about"
                  className="text-white/60 text-sm hover:text-white transition-colors"
                >
                  About
                </Link>
              </li>
              <li>
                <Link
                  href="/team"
                  className="text-white/60 text-sm hover:text-white transition-colors"
                >
                  Team
                </Link>
              </li>
              <li>
                <Link
                  href="/careers"
                  className="text-white/60 text-sm hover:text-white transition-colors"
                >
                  Careers
                </Link>
              </li>
              <li>
                <Link
                  href="/contact"
                  className="text-white/60 text-sm hover:text-white transition-colors"
                >
                  Contact
                </Link>
              </li>
            </ul> */}

            <h3 className="text-black dark:text-white font-medium mb-4">
              Legal
            </h3>
            <ul className="space-y-2">
              <li>
                <Link
                  href="/privacy"
                  className="text-black/60 dark:text-white/60 text-sm hover:text-black dark:hover:text-white transition-colors"
                >
                  Privacy Policy
                </Link>
              </li>
              <li>
                <Link
                  href="/terms"
                  className="text-black/60 dark:text-white/60 text-sm hover:text-black dark:hover:text-white transition-colors"
                >
                  Terms of Service
                </Link>
              </li>
              <li>
                <Link
                  href="/contact"
                  className="text-black/60 dark:text-white/60 text-sm hover:text-black dark:hover:text-white transition-colors"
                >
                  Contact
                </Link>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Section - Desktop only */}
        <div className="hidden lg:flex w-full justify-between items-center pt-6 mt-6 border-t border-black/10 dark:border-white/10">
          <p className="text-black/40 dark:text-white/40 text-sm">
            © 2025 Riddhiman Rana. All rights reserved.
          </p>
          <div className="inline-flex items-center space-x-1 px-3 py-2 bg-black/5 dark:bg-white/5 rounded-full border border-black/10 dark:border-white/10">
            <div className="flex items-center space-x-2">
            <Microscope className="w-3.5 h-3.5 text-blue-500" />
            <span className="text-black/60 dark:text-white/60 text-sm font-medium">
              Research Phase
            </span>
            </div>
            <div className="flex items-center space-x-1">
              <span className="text-black dark:text-white text-sm font-semibold">2</span>
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
          </div>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default CleanFooter;
