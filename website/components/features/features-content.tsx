"use client";

import React from "react";
import { motion } from "framer-motion";
import {
  Eye,
  Shield,
  Zap,
  Smartphone,
  Brain,
  Lock,
  Clock,
  Cpu,
  Globe,
  Monitor,
  Database,
  CheckCircle,
  Layers,
  Target,
  Activity,
  Image as ImageIcon,
  Video,
  Scan,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const fadeInUp = {
  initial: { opacity: 0, y: 15 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4 },
};

export function FeaturesContent() {
  return (
    <div className="min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Header */}
        <motion.div {...fadeInUp} className="text-center mb-16">
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 dark:text-white mb-4">
            Orion Live Features
          </h1>
          <p className="text-lg text-gray-600 dark:text-gray-400 max-w-3xl mx-auto">
            Advanced computer vision AI that processes visual data locally on
            your device with enterprise-grade performance and complete privacy
            protection.
          </p>
        </motion.div>

        {/* Core Vision Capabilities Bento Grid */}
        <motion.div {...fadeInUp} className="mb-20">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-8">
            Computer Vision Capabilities
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Card className="border-0 shadow-sm">
              <CardContent className="p-6">
                <Target className="w-8 h-8 text-blue-600 mb-4" />
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  Object Detection
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Identifies and localizes multiple objects in images with
                  precise bounding boxes and confidence scores.
                </p>
              </CardContent>
            </Card>

            <Card className="border-0 shadow-sm">
              <CardContent className="p-6">
                <Eye className="w-8 h-8 text-green-600 mb-4" />
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  Scene Analysis
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Understands complex scenes, spatial relationships, and
                  contextual information in visual data.
                </p>
              </CardContent>
            </Card>

            <Card className="border-0 shadow-sm">
              <CardContent className="p-6">
                <Scan className="w-8 h-8 text-purple-600 mb-4" />
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  Text Recognition
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Extracts and interprets text from images with high accuracy
                  OCR capabilities.
                </p>
              </CardContent>
            </Card>

            <Card className="border-0 shadow-sm">
              <CardContent className="p-6">
                <Activity className="w-8 h-8 text-orange-600 mb-4" />
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  Motion Tracking
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Tracks object movement and analyzes motion patterns in
                  real-time video streams.
                </p>
              </CardContent>
            </Card>
          </div>
        </motion.div>

        {/* Performance & Architecture */}
        <motion.div {...fadeInUp} className="mb-20">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-2 border-0 shadow-sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Zap className="w-5 h-5 text-yellow-600" />
                  Performance Metrics
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-gray-900 dark:text-white mb-1">
                      &lt;50ms
                    </div>
                    <div className="text-sm text-gray-500">Processing Time</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-gray-900 dark:text-white mb-1">
                      99.2%
                    </div>
                    <div className="text-sm text-gray-500">Accuracy Rate</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-gray-900 dark:text-white mb-1">
                      30fps
                    </div>
                    <div className="text-sm text-gray-500">
                      Video Processing
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-gray-900 dark:text-white mb-1">
                      Zero
                    </div>
                    <div className="text-sm text-gray-500">
                      Cloud Dependency
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-0 shadow-sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Shield className="w-5 h-5 text-green-600" />
                  Privacy First
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-600" />
                    <span className="text-sm text-gray-700 dark:text-gray-300">
                      100% Local Processing
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-600" />
                    <span className="text-sm text-gray-700 dark:text-gray-300">
                      No Data Transmission
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-600" />
                    <span className="text-sm text-gray-700 dark:text-gray-300">
                      Offline Capable
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-600" />
                    <span className="text-sm text-gray-700 dark:text-gray-300">
                      GDPR Compliant
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </motion.div>

        {/* Technical Architecture */}
        <motion.div {...fadeInUp} className="mb-20">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-8">
            Technical Architecture
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <Card className="border-0 shadow-sm">
              <CardContent className="p-6">
                <Cpu className="w-8 h-8 text-blue-600 mb-4" />
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  Edge Computing
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                  Optimized neural networks run directly on device hardware
                  without external dependencies.
                </p>
                <div className="text-xs text-gray-500">
                  CPU, GPU & NPU acceleration
                </div>
              </CardContent>
            </Card>

            <Card className="border-0 shadow-sm">
              <CardContent className="p-6">
                <Brain className="w-8 h-8 text-purple-600 mb-4" />
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  Neural Networks
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                  Compressed deep learning models optimized for mobile and edge
                  deployment.
                </p>
                <div className="text-xs text-gray-500">
                  TensorFlow Lite & ONNX support
                </div>
              </CardContent>
            </Card>

            <Card className="border-0 shadow-sm">
              <CardContent className="p-6">
                <Database className="w-8 h-8 text-teal-600 mb-4" />
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  Memory Management
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                  Efficient memory allocation and caching for optimal
                  performance on resource-constrained devices.
                </p>
                <div className="text-xs text-gray-500">
                  &lt;200MB memory footprint
                </div>
              </CardContent>
            </Card>
          </div>
        </motion.div>

        {/* Media Processing Capabilities */}
        <motion.div {...fadeInUp} className="mb-20">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="border-0 shadow-sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ImageIcon className="w-5 h-5 text-indigo-600" />
                  Image Processing
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <div className="font-medium text-gray-900 dark:text-white mb-2">
                      Supported Formats
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className="px-2 py-1 bg-gray-100 dark:bg-gray-800 text-xs rounded">
                        JPEG
                      </span>
                      <span className="px-2 py-1 bg-gray-100 dark:bg-gray-800 text-xs rounded">
                        PNG
                      </span>
                      <span className="px-2 py-1 bg-gray-100 dark:bg-gray-800 text-xs rounded">
                        WebP
                      </span>
                      <span className="px-2 py-1 bg-gray-100 dark:bg-gray-800 text-xs rounded">
                        HEIF
                      </span>
                    </div>
                  </div>
                  <div>
                    <div className="font-medium text-gray-900 dark:text-white mb-2">
                      Processing Speed
                    </div>
                    <div className="text-sm text-gray-600 dark:text-gray-400">
                      Up to 4K resolution at 30fps with real-time analysis
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-0 shadow-sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Video className="w-5 h-5 text-red-600" />
                  Video Processing
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <div className="font-medium text-gray-900 dark:text-white mb-2">
                      Live Stream Analysis
                    </div>
                    <div className="text-sm text-gray-600 dark:text-gray-400">
                      Real-time processing of camera feeds, recorded videos, and
                      live streams
                    </div>
                  </div>
                  <div>
                    <div className="font-medium text-gray-900 dark:text-white mb-2">
                      Frame-by-Frame
                    </div>
                    <div className="text-sm text-gray-600 dark:text-gray-400">
                      Temporal analysis with motion tracking and scene changes
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </motion.div>

        {/* Platform Support */}
        <motion.div {...fadeInUp} className="mb-20">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-8">
            Platform Support
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <Card className="border-0 shadow-sm text-center">
              <CardContent className="p-6">
                <Smartphone className="w-12 h-12 text-gray-700 mx-auto mb-4" />
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  Mobile
                </h3>
                <div className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                  <div>iOS 14+</div>
                  <div>Android 8+</div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-0 shadow-sm text-center">
              <CardContent className="p-6">
                <Monitor className="w-12 h-12 text-gray-700 mx-auto mb-4" />
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  Desktop
                </h3>
                <div className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                  <div>Windows 10+</div>
                  <div>macOS 11+</div>
                  <div>Linux</div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-0 shadow-sm text-center">
              <CardContent className="p-6">
                <Globe className="w-12 h-12 text-gray-700 mx-auto mb-4" />
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  Web
                </h3>
                <div className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                  <div>WebAssembly</div>
                  <div>WebGL support</div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-0 shadow-sm text-center">
              <CardContent className="p-6">
                <Layers className="w-12 h-12 text-gray-700 mx-auto mb-4" />
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  Embedded
                </h3>
                <div className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                  <div>ARM processors</div>
                  <div>Edge devices</div>
                </div>
              </CardContent>
            </Card>
          </div>
        </motion.div>

        {/* Security Features */}
        <motion.div {...fadeInUp}>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-8">
            Security & Compliance
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Card className="border-0 shadow-sm">
              <CardContent className="p-6">
                <Lock className="w-8 h-8 text-red-600 mb-4" />
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  Local Processing
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  All computation happens on-device. No data leaves your system.
                </p>
              </CardContent>
            </Card>

            <Card className="border-0 shadow-sm">
              <CardContent className="p-6">
                <Shield className="w-8 h-8 text-green-600 mb-4" />
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  Data Protection
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  GDPR, HIPAA, and SOC 2 compliant architecture.
                </p>
              </CardContent>
            </Card>

            <Card className="border-0 shadow-sm">
              <CardContent className="p-6">
                <Globe className="w-8 h-8 text-blue-600 mb-4" />
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  Offline Operation
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Full functionality without internet connectivity.
                </p>
              </CardContent>
            </Card>

            <Card className="border-0 shadow-sm">
              <CardContent className="p-6">
                <Clock className="w-8 h-8 text-purple-600 mb-4" />
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  Real-time
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Instant processing with no network latency or delays.
                </p>
              </CardContent>
            </Card>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
