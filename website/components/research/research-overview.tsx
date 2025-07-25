"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  AlertTriangle,
  Brain,
  Zap,
  Shield,
  Clock,
  Microscope
} from "lucide-react";

export function ResearchOverview() {
  const keyContributions = [
    {
      title: "Hybrid Edge-Server Architecture",
      description:
        "Split-computation design that processes visual data locally while performing complex reasoning on a local server.",
      icon: <Brain className="h-5 w-5" />,
    },
    {
      title: "Semantic Uplift Process",
      description:
        "Transforms raw object detection outputs into structured, grounded scene descriptions using vision-language models.",
      icon: <Zap className="h-5 w-5" />,
    },
    {
      title: "Privacy-First Design",
      description:
        "Makes sure raw video never leaves the device, transmitting only anonymized textual descriptions for processing.",
      icon: <Shield className="h-5 w-5" />,
    },
    {
      title: "Temporal Memory System",
      description:
        "Implements persistent contextual memory using vector databases like Milvus for queryable event analysis over time.",
      icon: <Clock className="h-5 w-5" />,
    },
  ];

  const problemStatement = [
    {
      issue: "Latency Bottleneck",
      description:
        "Current AI vision systems take 3-5 seconds to process visual data, making them unsuitable for real-time applications.",
      severity: "Critical",
    },
    {
      issue: "Privacy Violations",
      description:
        "Existing solutions require sending raw video to cloud servers, creating significant privacy and security risks.",
      severity: "High",
    },
    {
      issue: "Visual Hallucinations",
      description:
        "Vision-language models frequently generate inaccurate descriptions, failing to ground responses in actual visual evidence.",
      severity: "High",
    },
    {
      issue: "Stateless Processing",
      description:
        "Current systems lack memory between interactions, unable to build understanding or context over time.",
      severity: "Medium",
    },
  ];

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* Abstract */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-xl sm:text-2xl">Research Abstract</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 sm:space-y-4 pt-0">
          <p className="text-sm sm:text-base lg:text-lg leading-relaxed text-muted-foreground">
            Current Vision Language Models (VLMs) often struggle with real-time
            performance and maintaining continuous contextual understanding of
            dynamic visual scenes, particularly within privacy-sensitive or
            resource-constrained environments.
          </p>

          <p className="text-sm sm:text-base lg:text-lg leading-relaxed text-muted-foreground">
            Addressing these limitations, I introduce <strong>Orion</strong>, a
            novel, real-time local visual perception architecture featuring a hybrid
            on-device and server architecture. At its core, Orion integrates
            YOLOv11n for efficient real-time object detection, a custom
            finetuned version of FastVLM-0.5b for structured, on-device image
            captioning, a custom fine-tuned version of server-side/locally inferenced Gemma-3B LLM, a novel high-dimensional vector database embedding system, and a structured relational model of dynamic graph knowledge to enable true causal reasoning for
            for sophisticated temporal reasoning, contextual analysis, and answering user queries. This
            design prioritizes privacy and low-latency inference by performing
            visual encoding and captioning directly on the mobile device,
            leveraging FastVLM&apos;s proven efficiency, including RAM usage
            below 1GB and Time-to-First-Token (TTFT) as low as 600ms on
            higher-end iPhones.
          </p>

          <p className="text-sm sm:text-base lg:text-lg leading-relaxed text-muted-foreground">
            Building upon this robust foundation, I propose to extend Orion’s
            architectural and methodological capabilities to enable advanced
            analysis and tracking of visual events within a persistent
            contextual memory using a vector database. This expanded framework
            will allow Orion to automatically detect and articulate subtle or
            significant changes across successive video frames, provide deep
            visual insights into the evolution of scenes, and facilitate complex
            user queries regarding temporal visual events and their contextual
            implications. Orion represents a significant step towards creating
            intelligent, interactive, and deployable visual perception agents
            that can truly &quot;remember&quot; and &quot;understand&quot; the
            world as it unfolds.
          </p>
        </CardContent>
      </Card>

      {/* Problem Statement */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg sm:text-xl lg:text-2xl flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 sm:h-6 sm:w-6 text-amber-500" />
            Research Motivation
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
            {problemStatement.map((problem, index) => (
              <div key={index} className="border rounded-lg p-3 sm:p-4 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <h4 className="font-semibold text-sm sm:text-base flex-1">{problem.issue}</h4>
                </div>
                <p className="text-xs sm:text-sm text-muted-foreground">
                  {problem.description}
                </p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* <Separator /> */}

      {/* Key Contributions */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg sm:text-xl lg:text-2xl flex items-center gap-2">
            <Microscope className="h-5 w-5 sm:h-6 sm:w-6 text-blue-500" />
            Key Research Contributions
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
            {keyContributions.map((contribution, index) => (
              <div key={index} className="flex gap-3 sm:gap-4 p-3 sm:p-4 border rounded-lg">
                <div className="text-primary bg-primary/10 p-2 sm:p-3 rounded-lg flex-shrink-0 h-fit">
                  <div>
                    {contribution.icon}
                  </div>
                </div>
                <div className="space-y-1 sm:space-y-2 flex-1 min-w-0">
                  <h4 className="font-semibold text-sm sm:text-base">{contribution.title}</h4>
                  <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
                    {contribution.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Research Impact */}
      {/* <Card className="bg-muted/30">
        <CardContent className="p-6">
          <div className="text-center space-y-4">
            <h3 className="text-xl font-semibold">Research Impact</h3>
            <p className="text-muted-foreground max-w-3xl mx-auto">
              Orion represents a paradigm shift from monolithic cloud-based
              vision AI to distributed, privacy-preserving systems that can
              operate in real-time. This work opens new research directions in
              edge computing, multimodal AI, and privacy-preserving machine
              learning.
            </p>
            <div className="flex justify-center gap-6 pt-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-primary">70+</div>
                <div className="text-sm text-muted-foreground">Citations</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-primary">&lt;50ms</div>
                <div className="text-sm text-muted-foreground">Latency</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-primary">100%</div>
                <div className="text-sm text-muted-foreground">
                  Local Processing
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card> */}
    </div>
  );
}
