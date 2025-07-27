"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Database,
  Search,
  GitBranch,
  ArrowDown,
  Brain,
  Network,
} from "lucide-react";
import VectorDatabaseTechnical from "./vector-database-technical";

export function MemorySection() {
  const phases = {
    phase1: {
      title: "Phase 1: Vector-Based Semantic Memory",
      subtitle: "The 'What and Where'",
      description:
        "Creates a searchable log of all observations, enabling content-based retrieval of past events.",
      icon: <Search className="h-6 w-6" />,
      features: [
        "Store and search scene descriptions",
        "Sentence Embeddings + Vector Database",
        "Semantic similarity search",
        "Query: 'Where did I last see my wallet?'",
      ],
      workflow: [
        { step: "User Query", example: "Find my keys" },
        {
          step: "Query Embedding",
          example: "Vector representation",
        },
        {
          step: "Vector DB Search",
          example: "Similarity matching",
        },
        {
          step: "Ranked Results",
          example: "Scene descriptions",
        },
      ],
    },
    phase2: {
      title: "Phase 2: Dynamic Knowledge Graph",
      subtitle: "The 'Why and How'",
      description:
        "Evolves memory into a structured, relational model enabling true causal reasoning.",
      icon: <Network className="h-6 w-6" />,
      features: [
        "Extract entities and relationships",
        "LLM-based Information Extraction",
        "Graph database storage",
        "Query: 'What happened before the person picked up keys?'",
      ],
      workflow: [
        {
          step: "Text Input",
          example: "A person sits on a chair",
        },
        {
          step: "LLM Extraction",
          example: "Entity & relation extraction",
        },
        {
          step: "Knowledge Triples",
          example: "(Person, SITS_ON, Chair)",
        },
        {
          step: "Graph Update",
          example: "Update knowledge graph",
        },
      ],
    },
  };

  return (
    <section id="memory" className=" bg-background">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-8 sm:mb-16">
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-foreground mb-4">
            Vector Embeddings & Dynamic Graph Knowledge
          </h2>
          <p className="max-w-3xl mx-auto text-sm sm:text-base lg:text-lg text-muted-foreground">
            A key goal for Orion is to move beyond stateless perception to
            stateful understanding. This requires an explicit memory system. I
            propose a phased implementation, starting with semantic search and
            evolving towards structured knowledge graphs.
          </p>
        </div>

        <Tabs defaultValue="phase1" className="w-full">
          <TabsList className="grid w-full grid-cols-2 max-w-md mx-auto mb-8 sm:mb-12">
            <TabsTrigger value="phase1" className="flex items-center text-xs sm:text-sm">
              <Database className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">Phase 1: Vector Memory</span>
              <span className="sm:hidden">Vector</span>
            </TabsTrigger>
            <TabsTrigger value="phase2" className="flex items-center text-xs sm:text-sm">
              <GitBranch className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">Phase 2: Knowledge Graph</span>
              <span className="sm:hidden">Graph</span>
            </TabsTrigger>
          </TabsList>

          {Object.entries(phases).map(([key, phase]) => (
            <TabsContent key={key} value={key}>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12 items-start">
                <Card
                  className={`border-l-4 ${key === "phase1" ? "border-amber-500 dark:border-amber-300" : "border-blue-500 dark:border-blue-300"}`}
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-center space-x-3">
                      <div
                        className={`p-2 rounded-lg ${key === "phase1" ? "bg-amber-100 dark:bg-amber-900 text-amber-700 dark:text-amber-400" : "bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-400"}`}
                      >
                        {phase.icon}
                      </div>
                      <div className="flex-1 min-w-0">
                        <CardTitle className="text-lg sm:text-xl">{phase.title}</CardTitle>
                        <p
                          className={`${key === "phase1" ? "text-amber-700 dark:text-amber-400" : "text-blue-700 dark:text-blue-400"} text-xs sm:text-sm font-medium`}
                        >
                          {phase.subtitle}
                        </p>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <p className="text-sm sm:text-base text-muted-foreground mb-4 sm:mb-6">
                      {phase.description}
                    </p>
                    <div className="space-y-2 sm:space-y-3">
                      {phase.features.map((feature, index) => (
                        <div key={index} className="flex items-start space-x-2">
                          <div
                            className={`w-2 h-2 rounded-full mt-2 ${key === "phase1" ? "bg-amber-500 dark:bg-amber-300" : "bg-blue-500 dark:bg-blue-300"}`}
                          />
                          <span className="text-sm sm:text-base text-foreground">{feature}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center space-x-2 text-lg sm:text-xl">
                      <Brain className="h-4 w-4 sm:h-5 sm:w-5" />
                      <span>
                        {key === "phase1"
                          ? "Query Flow"
                          : "Knowledge Extraction"}
                      </span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <div className="space-y-3 sm:space-y-4">
                      {phase.workflow.map((item, index) => (
                        <div key={index}>
                          <div className="p-3 sm:p-4 rounded-lg border bg-muted">
                            <div className="font-medium text-foreground text-sm sm:text-base">
                              {item.step}
                            </div>
                            <div className="text-xs sm:text-sm text-muted-foreground mt-1">
                              {item.example}
                            </div>
                          </div>
                          {index < phase.workflow.length - 1 && (
                            <div className="flex justify-center">
                              <ArrowDown className="h-4 w-4 sm:h-5 sm:w-5 text-muted-foreground" />
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          ))}
        </Tabs>

        <div className="mt-12 sm:mt-16">
          <VectorDatabaseTechnical />
        </div>

        <div className="mt-12 sm:mt-16 rounded-2xl p-4 sm:p-6 lg:p-8 bg-secondary/10 dark:bg-secondary/20">
          <div className="text-center">
            <h3 className="text-lg sm:text-xl lg:text-2xl font-bold text-foreground mb-4">
              Temporal Reasoning: From Snapshots to Understanding
            </h3>
            <p className="max-w-3xl mx-auto text-sm sm:text-base text-muted-foreground leading-relaxed">
              By maintaining a persistent memory of structured observations,
              Orion can perform sophisticated temporal reasoning. It compares
              textual snapshots over time to detect changes, infer complex
              events, and answer questions about causality and sequence.
            </p>
            <div className="mt-4 sm:mt-6 flex flex-wrap justify-center gap-2 sm:gap-3">
              <Badge className="text-xs sm:text-sm">Change Detection</Badge>
              <Badge className="text-xs sm:text-sm">Causal Inference</Badge>
              <Badge className="text-xs sm:text-sm">Event Sequencing</Badge>
              <Badge className="text-xs sm:text-sm">Context Preservation</Badge>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
