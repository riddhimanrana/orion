"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Smartphone,
  Server,
  ArrowRightLeft,
  Eye,
  Brain,
  ArrowDown,
  ArrowRight,
  Zap,
  Target,
  MessageSquare,
  Sparkles,
} from "lucide-react";

export function HowItWorks() {
  const semanticUpliftSteps = [
    {
      step: "1",
      title: "YOLO Detections",
      subtitle: "Raw object detection output",
      description:
        "Initial computer vision processing identifies objects and their bounding boxes",
      example:
        "[{class: 'person', box: [x,y,w,h]}, {class: 'chair', box: [x,y,w,h]}]",
      icon: <Eye className="h-5 w-5" />,
      color: "bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-400",
      borderColor: "border-red-500 dark:border-red-300",
    },
    {
      step: "2",
      title: "Narrative Primitives",
      subtitle: "Spatial relationships extracted",
      description:
        "Spatial analysis determines relative positions and relationships between objects",
      example: "person (right), chair (center)",
      icon: <Target className="h-5 w-5" />,
      color:
        "bg-orange-100 dark:bg-orange-900 text-orange-700 dark:text-orange-400",
      borderColor: "border-orange-500 dark:border-orange-300",
    },
    {
      step: "3",
      title: "Structured Prompt",
      subtitle: "Guided VLM instructions",
      description:
        "Structured queries guide the vision-language model for focused analysis",
      example: "Main Focus: ?, Spatial Relationships: ?, Activities: ?",
      icon: <MessageSquare className="h-5 w-5" />,
      color: "bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-400",
      borderColor: "border-blue-500 dark:border-blue-300",
    },
    {
      step: "4",
      title: "VLM Description",
      subtitle: "Rich, grounded scene description",
      description:
        "Vision-language model generates comprehensive, contextually-aware descriptions",
      example:
        "A person is sitting on a chair in the center of a modern office...",
      icon: <Sparkles className="h-5 w-5" />,
      color:
        "bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-400",
      borderColor: "border-green-500 dark:border-green-300",
    },
  ];

  return (
    <section id="how-it-works" className=" bg-background">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-8 sm:mb-16">
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-foreground mb-4">
            The Hybrid Cloud-Edge Architecture
          </h2>
          <p className="max-w-3xl mx-auto text-sm sm:text-base lg:text-lg text-muted-foreground">
            Orion&apos;s novelty is in its system architecture and data-flow
            paradigm. By splitting tasks between an edge device and a
            local server, Orion balances low-latency perception with
            sophisticated, stateful reasoning.
          </p>
        </div>

        <Tabs defaultValue="architecture" className="w-full">
          <TabsList className="grid w-full grid-cols-2 max-w-md mx-auto mb-8 sm:mb-12">
            <TabsTrigger
              value="architecture"
              className="flex items-center space-x-1 sm:space-x-2 text-xs sm:text-sm"
            >
              <ArrowRightLeft className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">System Architecture</span>
              <span className="sm:hidden">System</span>
            </TabsTrigger>
            <TabsTrigger
              value="semantic"
              className="flex items-center space-x-1 sm:space-x-2 text-xs sm:text-sm"
            >
              <Brain className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">Semantic Uplift</span>
              <span className="sm:hidden">Semantic</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="architecture">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:gap-8 items-center">
              {/* Edge Device */}
              <Card className="border-l-4 border-blue-500 dark:border-blue-300">
                <CardHeader className="pb-3">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-400">
                      <Smartphone className="h-5 w-5 sm:h-6 sm:w-6" />
                    </div>
                    <div>
                      <CardTitle className="text-lg sm:text-xl">Edge Device</CardTitle>
                      <p className="text-blue-700 dark:text-blue-400 text-xs sm:text-sm font-medium">
                        e.g., Smartphone
                      </p>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="space-y-3 sm:space-y-4">
                    <div className="p-3 sm:p-4 rounded-lg bg-muted">
                      <div className="font-medium text-foreground mb-2 text-sm sm:text-base">
                        Capabilities
                      </div>
                      <ul className="text-xs sm:text-sm text-muted-foreground space-y-1">
                        <li>• Real-time image capture</li>
                        <li>• On-device YOLO detection</li>
                        <li>• Spatial relationship analysis</li>
                        <li>• Low-power processing</li>
                      </ul>
                    </div>
                    <div className="flex items-center justify-center">
                      <Badge variant="outline" className="text-xs">
                        <Zap className="h-3 w-3 mr-1" />
                        Low Latency
                      </Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Data Flow */}
              <div className="flex flex-col items-center space-y-3 sm:space-y-4 py-4">
                <div className="flex items-center space-x-2 text-muted-foreground">
                  <ArrowRight className="h-4 w-4 sm:h-5 sm:w-5 " />
                  <span className="text-xs sm:text-sm font-medium">Text Payload</span>
                </div>
                <div className="p-3 sm:p-4 rounded-lg border bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/30 dark:to-purple-900/30 w-full max-w-xs">
                  <div className="text-center">
                    <div className="font-medium text-foreground mb-2 text-sm sm:text-base">
                      Data Exchange
                    </div>
                    <div className="text-xs sm:text-sm text-muted-foreground">
                      Structured descriptions, not the image
                    </div>
                  </div>
                </div>
                <div className="flex items-center space-x-2 text-muted-foreground">
                  <ArrowRight className="h-4 w-4 sm:h-5 sm:w-5 rotate-180" />
                  <span className="text-xs sm:text-sm font-medium">Insights & State</span>
                </div>
              </div>

              {/* Local Server */}
              <Card className="border-l-4 border-purple-500 dark:border-purple-300">
                <CardHeader className="pb-3">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 rounded-lg bg-purple-100 dark:bg-purple-900 text-purple-700 dark:text-purple-400">
                      <Server className="h-5 w-5 sm:h-6 sm:w-6" />
                    </div>
                    <div>
                      <CardTitle className="text-lg sm:text-xl">Local Server</CardTitle>
                      <p className="text-purple-700 dark:text-purple-400 text-xs sm:text-sm font-medium">
                        e.g., Apple Silicon Mac
                      </p>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="space-y-3 sm:space-y-4">
                    <div className="p-3 sm:p-4 rounded-lg bg-muted">
                      <div className="font-medium text-foreground mb-2 text-sm sm:text-base">
                        Capabilities
                      </div>
                      <ul className="text-xs sm:text-sm text-muted-foreground space-y-1">
                        <li>• Advanced VLM processing</li>
                        <li>• Temporal reasoning</li>
                        <li>• Knowledge graph storage</li>
                        <li>• Complex inference</li>
                      </ul>
                    </div>
                    <div className="flex items-center justify-center">
                      <Badge variant="outline" className="text-xs">
                        <Brain className="h-3 w-3 mr-1" />
                        High Compute
                      </Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="semantic">
            <div className="space-y-6 sm:space-y-8">
              <div className="text-center mb-8 sm:mb-12">
                <h3 className="text-xl sm:text-2xl font-bold text-foreground mb-4">
                  The Core Innovation: &quot;Semantic Uplift&quot;
                </h3>
                <p className="max-w-3xl mx-auto text-sm sm:text-base text-muted-foreground">
                  This on-device process transforms raw pixels into structured
                  knowledge, feeding the AI high-quality, grounded input instead
                  of noisy data. This mitigates bias and hallucination.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
                {semanticUpliftSteps.map((step, index) => (
                  <div key={index} className="relative">
                    <Card className={`border-l-4 ${step.borderColor} h-full`}>
                      <CardHeader className="pb-3">
                        <div className="flex items-center space-x-2 sm:space-x-3">
                          <div
                            className={`p-2 rounded-lg ${step.color} flex items-center justify-center`}
                          >
                            {step.icon}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center space-x-2">
                              <Badge variant="outline" className="text-xs">
                                {step.step}
                              </Badge>
                            </div>
                            <CardTitle className="text-sm sm:text-lg mt-1 truncate">
                              {step.title}
                            </CardTitle>
                            <p
                              className={`text-xs sm:text-sm font-medium ${step.color.split(" ")[2]} ${step.color.split(" ")[3]} line-clamp-1`}
                            >
                              {step.subtitle}
                            </p>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent className="pt-0">
                        <p className="text-xs sm:text-sm text-muted-foreground mb-3 sm:mb-4">
                          {step.description}
                        </p>
                        <div className="p-2 sm:p-3 rounded-lg bg-muted">
                          <div className="text-xs font-mono text-foreground break-all">
                            {step.example}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                    {index < semanticUpliftSteps.length - 1 && (
                      <div className="hidden lg:block absolute top-1/2 -right-6 transform -translate-y-1/2">
                        <ArrowRight className="h-6 w-6 text-muted-foreground" />
                      </div>
                    )}
                    {index < semanticUpliftSteps.length - 1 && (
                      <div className="lg:hidden flex justify-center mt-3 sm:mt-4">
                        <ArrowDown className="h-5 w-5 sm:h-6 sm:w-6 text-muted-foreground" />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </TabsContent>
        </Tabs>

        {/* <div className="mt-12 sm:mt-16 rounded-2xl p-4 sm:p-6 lg:p-8 bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20">
          <div className="text-center">
            <h3 className="text-lg sm:text-xl lg:text-2xl font-bold text-foreground mb-4">
              Why Hybrid Architecture Matters
            </h3>
            <p className="max-w-3xl mx-auto text-sm sm:text-base text-muted-foreground leading-relaxed mb-4 sm:mb-6">
              By distributing computation between edge and server, Orion
              achieves the best of both worlds: immediate responsiveness for
              real-time perception and sophisticated reasoning for complex
              analysis.
            </p>
            <div className="flex flex-wrap justify-center gap-2 sm:gap-3">
              <Badge className="bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200 text-xs sm:text-sm">
                Real-time Processing
              </Badge>
              <Badge className="bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-200 text-xs sm:text-sm">
                Privacy Preservation
              </Badge>
              <Badge className="bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-200 text-xs sm:text-sm">
                Reduced Hallucination
              </Badge>
              <Badge className="bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-200 text-xs sm:text-sm">
                Scalable Architecture
              </Badge>
            </div>
          </div>
        </div> */}
      </div>
    </section>
  );
}
