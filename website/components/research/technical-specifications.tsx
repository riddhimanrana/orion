"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Image from "next/image";
import {
  Database,
  Search,
  Network,
  Monitor,
  Code,
  Activity,
  Zap,
  ArrowRight,
  Play,
  Pause,
} from "lucide-react";

export function TechnicalSpecifications() {
  const [isSimulating, setIsSimulating] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);

  const vectorSearchProcess = [
    {
      step: "Query Embedding",
      description:
        "User query 'Where are my keys?' is processed through sentence-transformer",
      technical: "all-mpnet-base-v2 generates 768-dimensional dense vector",
      code: `query_vector = model.encode("Where are my keys?")\n# Output: [0.1234, -0.5678, 0.9012, ...]`,
    },
    {
      step: "Similarity Search",
      description: "Cosine similarity computed against stored scene embeddings",
      technical:
        "FAISS index enables sub-linear search through millions of vectors",
      code: `similarities = np.dot(query_vector, scene_vectors.T)\ntop_k_indices = np.argsort(similarities)[-5:]`,
    },
    {
      step: "Context Retrieval",
      description: "Top-K most similar scenes retrieved with metadata",
      technical: "Temporal weighting applied: recent scenes get 1.2x boost",
      code: `results = [\n  {"scene": "keys on kitchen counter", "similarity": 0.89, "timestamp": "2024-01-15T14:30:22Z"},\n  {"scene": "keys in jacket pocket", "similarity": 0.76, "timestamp": "2024-01-15T09:15:11Z"}\n]`,
    },
    {
      step: "LLM Synthesis",
      description:
        "Gemma-3B synthesizes retrieved contexts into coherent answer",
      technical: "Context window: 8192 tokens, retrieval-augmented generation",
      code: `prompt = f"Based on these observations: {retrieved_contexts}\\nAnswer: {user_query}"\nresponse = gemma_3b.generate(prompt)`,
    },
  ];

  const packetFlow = [
    {
      timestamp: "7:12:12 PM",
      event: "ios_frame_received",
      source: "iPhone",
      destination: "Edge Processor",
      payload: {
        frame_id: "50F150E5-2B5D-408D-844A-33675BC80316",
        resolution: "1920x1080",
        format: "HEVC",
        size_bytes: 245760,
      },
      description: "Raw video frame captured and queued for processing",
    },
    {
      timestamp: "7:12:12 PM",
      event: "yolo_analysis_complete",
      source: "YOLOv11n",
      destination: "Semantic Uplift",
      payload: {
        detections: [
          { class: "person", confidence: 0.94, bbox: [120, 80, 340, 520] },
          { class: "chair", confidence: 0.87, bbox: [400, 200, 600, 480] },
          { class: "table", confidence: 0.82, bbox: [50, 300, 200, 400] },
        ],
        inference_time_ms: 23,
      },
      description:
        "Object detection completed, spatial relationships extracted",
    },
    {
      timestamp: "7:12:13 PM",
      event: "vlm_analysis_complete",
      source: "FastVLM-0.5B",
      destination: "Server",
      payload: {
        frame_id: "50F150E5-2B5D-408D-844A-33675BC80316",
        description:
          "A young woman, Sarah, is meticulously arranging a collection of antique porcelain dolls in a dimly lit room...",
        confidence: 0.89,
        token_count: 156,
        processing_time_ms: 580,
      },
      description: "Semantic uplift complete, structured description generated",
    },
    {
      timestamp: "7:12:13 PM",
      event: "llm_reasoning_complete",
      source: "Gemma-3B",
      destination: "Memory Store",
      payload: {
        scene_embedding: "vector[768]",
        entities: ["Sarah", "porcelain_dolls", "dimly_lit_room"],
        relationships: [
          {
            subject: "Sarah",
            predicate: "ARRANGING",
            object: "porcelain_dolls",
          },
          {
            subject: "porcelain_dolls",
            predicate: "LOCATED_IN",
            object: "dimly_lit_room",
          },
        ],
        temporal_context: "continuation_of_previous_scene",
        memory_update: "knowledge_graph_extended",
      },
      description:
        "Temporal reasoning applied, memory updated with new context",
    },
    {
      timestamp: "7:12:13 PM",
      event: "response_sent_to_ios",
      source: "Server",
      destination: "iPhone",
      payload: {
        scene_summary:
          "Sarah continues arranging her porcelain doll collection...",
        confidence_score: 0.89,
        processing_latency_ms: 1520,
        memory_entries_updated: 3,
      },
      description: "Processed insights sent back to client device",
    },
  ];

  const startSimulation = () => {
    setIsSimulating(true);
    setCurrentStep(0);

    const interval = setInterval(() => {
      setCurrentStep((prev) => {
        if (prev >= packetFlow.length - 1) {
          setIsSimulating(false);
          clearInterval(interval);
          return 0;
        }
        return prev + 1;
      });
    }, 2000);
  };

  return (
    <section id="technical-deep-dive" className="bg-background">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-8 sm:mb-16">
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-foreground mb-4">
            Vector Database Search & API Packet Flow
          </h2>
          <p className="max-w-3xl mx-auto text-sm sm:text-base lg:text-lg text-muted-foreground">
            How Orion&apos;s vector
            database search, packet-level communication, and real-time
            processing pipeline work with live simulations and code examples.
          </p>
        </div>

        <Tabs defaultValue="vector-search" className="w-full">
          <TabsList className="grid w-full grid-cols-3 max-w-2xl mx-auto mb-8 sm:mb-12">
            <TabsTrigger
              value="vector-search"
              className="flex items-center space-x-1 sm:space-x-2 text-xs sm:text-sm"
            >
              <Search className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">Vector Search</span>
              <span className="sm:hidden">Vector</span>
            </TabsTrigger>
            <TabsTrigger
              value="packet-flow"
              className="flex items-center space-x-1 sm:space-x-2 text-xs sm:text-sm"
            >
              <Network className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">Packet Flow</span>
              <span className="sm:hidden">Packet</span>
            </TabsTrigger>
            <TabsTrigger
              value="dashboard"
              className="flex items-center space-x-1 sm:space-x-2 text-xs sm:text-sm"
            >
              <Monitor className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">Live Dashboard</span>
              <span className="sm:hidden">Live</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="vector-search">
            <div className="space-y-6 sm:space-y-8">
              <Card className="border-l-4 border-primary">
                <CardHeader>
                  <CardTitle className="flex items-center space-x-2">
                    <Database className="h-6 w-6 text-primary" />
                    <span>Vector Database Architecture & Semantic Search</span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className=" mb-6">
                    Orion&apos;s memory system uses high-dimensional vector
                    embeddings to enable semantic search across temporal
                    observations. Unlike traditional keyword matching, this
                    approach captures semantic similarity and contextual
                    relationships. I am currently using Milvus for vector database storage.
                  </p>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                    <div className="space-y-4">
                      <h4 className="font-semibold text-foreground">
                        Technical Specifications
                      </h4>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="">Embedding Model:</span>
                          <Badge variant="outline">all-mpnet-base-v2</Badge>
                        </div>
                        <div className="flex justify-between">
                          <span className="">Vector Dimensions:</span>
                          <Badge variant="outline">768</Badge>
                        </div>
                        <div className="flex justify-between">
                          <span className="">Index Type:</span>
                          <Badge variant="outline">FAISS IVF-PQ</Badge>
                        </div>
                        <div className="flex justify-between">
                          <span className="">Similarity Metric:</span>
                          <Badge variant="outline">Cosine Similarity</Badge>
                        </div>
                        <div className="flex justify-between">
                          <span className="">Search Complexity:</span>
                          <Badge variant="outline">O(log n)</Badge>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <h4 className="font-semibold ">Performance Metrics</h4>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="">Query Latency:</span>
                          <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100">
                            &lt; 50ms
                          </Badge>
                        </div>
                        <div className="flex justify-between">
                          <span className="">Index Size (1M vectors):</span>
                          <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100">
                            ~3GB
                          </Badge>
                        </div>
                        <div className="flex justify-between">
                          <span className="">Recall@10:</span>
                          <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-100">
                            0.95
                          </Badge>
                        </div>
                        <div className="flex justify-between">
                          <span className="">Memory Usage:</span>
                          <Badge className="bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-100">
                            ~4GB RAM
                          </Badge>
                        </div>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                {vectorSearchProcess.map((step, index) => (
                  <Card key={index} className="relative">
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <Badge variant="outline">{index + 1}</Badge>
                        <Code className="h-4 w-4 500" />
                      </div>
                      <CardTitle className="text-lg">{step.step}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="600 text-sm mb-3">{step.description}</p>
                      <div className="bg-muted p-3 rounded-md mb-3">
                        <p className="text-xs text-muted-foreground font-medium">
                          {step.technical}
                        </p>
                      </div>
                      <div className="bg-stone-900 p-3 rounded-md">
                        <pre className="text-xs text-green-400 overflow-x-auto">
                          <code>{step.code}</code>
                        </pre>
                      </div>
                    </CardContent>
                    {index < vectorSearchProcess.length - 1 && (
                      <div className="absolute -right-6 top-1/2 transform -translate-y-1/2 hidden lg:block">
                        <ArrowRight className="h-6 w-6 text-primary" />
                      </div>
                    )}
                  </Card>
                ))}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="packet-flow">
            <div className="space-y-8">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center space-x-2">
                      <Activity className="h-4 w-4 md:h-6 md:w-6 text-primary flex-shrink-0" />
                      <span>Real-time Packet Flow Simulation</span>
                    </CardTitle>
                    <Button
                      onClick={startSimulation}
                      disabled={isSimulating}
                      className="flex items-center space-x-2"
                    >
                      {isSimulating ? (
                        <Pause className="h-4 w-4" />
                      ) : (
                        <Play className="h-4 w-4" />
                      )}
                      <span>
                        {isSimulating ? "Simulating..." : "Start Simulation"}
                      </span>
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="mb-6">
                    Watch how data flows through the Orion system in real-time,
                    from frame capture to memory storage. Each packet contains
                    detailed metadata and processing information.
                  </p>

                  <div className="space-y-4">
                    {packetFlow.map((packet, index) => {
                      const isActive = isSimulating && index === currentStep;
                      const isCompleted = isSimulating && index < currentStep;
                      return (
                        <Card
                          key={index}
                          className={`transition-all duration-500 ${
                            isActive
                              ? "border-2 border-green-500 dark:border-green-400 bg-green-50 dark:bg-green-900"
                              : isCompleted
                                ? " opacity-80"
                                : ""
                          }`}
                        >
                          <CardContent className="p-4">
                            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 items-start">
                              <div>
                                <div className="flex items-center space-x-2 mb-2">
                                  <Badge variant="outline" className="">
                                    {packet.timestamp}
                                  </Badge>
                                  {isActive && (
                                    <Zap className="h-4 w-4 text-green-500 dark:text-green-400 animate-pulse" />
                                  )}
                                </div>
                                <h4 className="font-semibold text-gray-900 dark:text-gray-100">
                                  {packet.event}
                                </h4>
                                <p className="text-sm text-gray-600 dark:text-gray-300">
                                  {packet.source} → {packet.destination}
                                </p>
                              </div>

                              <div className="lg:col-span-2">
                                <div className="bg-neutral-800 dark:bg-neutral-950 p-3 rounded-md">
                                  <pre className="text-xs text-green-400 overflow-x-auto">
                                    <code>
                                      {JSON.stringify(packet.payload, null, 2)}
                                    </code>
                                  </pre>
                                </div>
                              </div>

                              <div>
                                <p className="text-sm text-gray-700 dark:text-gray-300">
                                  {packet.description}
                                </p>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="dashboard">
            <div className="space-y-8">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center space-x-2">
                    <Monitor className="h-6 w-6 text-purple-600" />
                    <span>Orion Vision Dashboard - Live System Monitoring</span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="600 mb-6">
                    The Orion Vision Dashboard provides real-time monitoring and
                    control of the entire system pipeline. This web-based
                    interface allows researchers and developers to observe
                    packet flows, system performance, and memory operations as
                    they happen.
                  </p>

                  <div className="bg-stone-100 p-4 rounded-lg mb-6">
                    <Image
                      src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/Screenshot%202025-07-07%20at%207.13.41%E2%80%AFPM-oNeABXAOJcMSqyG5fVRU7JQFU6Hkg8.png"
                      alt="Orion Vision Dashboard showing real-time packet timeline, system status, LLM scene descriptions, and technical logs"
                      className="w-full rounded-lg shadow-lg"
                      width={1200}
                      height={600}
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    <Card className="border-l-4 border-l-green-500">
                      <CardHeader className="pb-3">
                        <CardTitle className="text-lg">
                          Packet Timeline
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm mb-3">
                          Real-time event stream showing system operations with
                          precise timestamps
                        </p>
                        <ul className="space-y-1 text-xs ">
                          <li>• vlm_analysis_complete</li>
                          <li>• llm_reasoning_complete</li>
                          <li>• response_sent_to_ios</li>
                          <li>• yolo_analysis_complete</li>
                        </ul>
                      </CardContent>
                    </Card>

                    <Card className="border-l-4 border-l-blue-500">
                      <CardHeader className="pb-3">
                        <CardTitle className="text-lg">
                          System Metrics
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm mb-3">
                          Live performance monitoring and queue management
                        </p>
                        <div className="space-y-2 text-xs">
                          <div className="flex justify-between">
                            <span>Mode:</span>
                            <Badge className="bg-green-100 text-green-800">
                              FULL
                            </Badge>
                          </div>
                          <div className="flex justify-between">
                            <span>Queue Size:</span>
                            <Badge variant="outline">1</Badge>
                          </div>
                          <div className="flex justify-between">
                            <span>LLM Confidence:</span>
                            <Badge className="bg-blue-100 text-blue-800">
                              80.0%
                            </Badge>
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    <Card className="border-l-4 border-l-purple-500">
                      <CardHeader className="pb-3">
                        <CardTitle className="text-lg">
                          Raw Packet Data
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm mb-3">
                          JSON payload inspection for debugging and analysis
                        </p>
                        <div className="bg-stone-900 p-2 rounded text-xs text-green-400">
                          <code>
                            {`{
  "event_type": "vlm_analysis_complete",
  "timestamp": 1751924738.998111,
  "confidence": 0.89
}`}
                          </code>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </section>
  );
}
