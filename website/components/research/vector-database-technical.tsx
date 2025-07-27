"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { Database, Search, Cpu, Zap, Code2 } from "lucide-react";

export default function VectorDatabaseTechnical() {
  const [selectedQuery, setSelectedQuery] = useState<number | null>(null);

  const queryExamples = [
    {
      query: "Where did I put my laptop?",
      embedding: "[0.1234, -0.5678, 0.9012, 0.3456, -0.7890, ...]",
      similarScenes: [
        {
          scene: "laptop on desk next to coffee mug",
          similarity: 0.94,
          timestamp: "2024-01-15T14:30:22Z",
        },
        {
          scene: "laptop in bedroom on nightstand",
          similarity: 0.87,
          timestamp: "2024-01-15T09:15:11Z",
        },
        {
          scene: "laptop bag on kitchen counter",
          similarity: 0.73,
          timestamp: "2024-01-14T18:45:33Z",
        },
      ],
      response:
        "Based on recent observations, your laptop was last seen on the desk next to a coffee mug at 2:30 PM today.",
    },
    {
      query: "What was the person doing before they sat down?",
      embedding: "[0.8765, 0.2341, -0.6789, 0.4567, 0.1234, ...]",
      similarScenes: [
        {
          scene: "person standing and organizing books",
          similarity: 0.91,
          timestamp: "2024-01-15T14:29:45Z",
        },
        {
          scene: "person walking across room carrying items",
          similarity: 0.85,
          timestamp: "2024-01-15T14:29:12Z",
        },
        {
          scene: "person reaching for objects on shelf",
          similarity: 0.78,
          timestamp: "2024-01-15T14:28:55Z",
        },
      ],
      response:
        "The person was organizing books while standing, then walked across the room before sitting down.",
    },
  ];

  const indexingProcess = [
    {
      step: "Scene Description",
      input:
        "A person is sitting on a red chair reading a book in a well-lit living room",
      output: "Tokenized text ready for embedding",
      icon: <Code2 className="h-5 w-5" />,
    },
    {
      step: "Sentence Embedding",
      input: "Tokenized scene description",
      output: "768-dimensional dense vector [0.1234, -0.5678, ...]",
      icon: <Cpu className="h-5 w-5" />,
    },
    {
      step: "Vector Indexing",
      input: "Dense vector + metadata",
      output: "FAISS IVF-PQ index entry with clustering",
      icon: <Database className="h-5 w-5" />,
    },
    {
      step: "Memory Storage",
      input: "Indexed vector",
      output: "Searchable memory entry with temporal weighting",
      icon: <Search className="h-5 w-5" />,
    },
  ];

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* Vector Database Architecture */}
      <Card className="border-l-4 border-l-indigo-500 dark:border-l-indigo-400">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center space-x-2">
            <Database className="h-5 w-5 sm:h-6 sm:w-6 text-indigo-600 dark:text-indigo-400" />
            <span className="text-lg sm:text-xl lg:text-2xl">
              Vector Database: Technical Implementation
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-8">
            <div>
              <h4 className="font-semibold text-indigo-900 dark:text-indigo-100 mb-3 sm:mb-4 text-sm sm:text-base">
                Embedding & Indexing Pipeline
              </h4>
              <div className="space-y-3 sm:space-y-4">
                {indexingProcess.map((step, index) => (
                  <div key={index} className="flex items-start space-x-2 sm:space-x-3">
                    <div className="bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300 p-2 rounded-lg flex-shrink-0">
                      <div className="h-4 w-4 sm:h-5 sm:w-5">
                        {step.icon}
                      </div>
                    </div>
                    <div className="flex-1 min-w-0">
                      <h5 className="font-medium text-indigo-900 dark:text-indigo-100 text-sm sm:text-base">
                        {step.step}
                      </h5>
                      <p className="text-xs sm:text-sm text-muted-foreground mb-1">
                        {step.input}
                      </p>
                      <p className="text-xs font-mono bg-indigo-50 dark:bg-indigo-950 p-2 rounded break-all">
                        → {step.output}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h4 className="font-semibold text-indigo-900 dark:text-indigo-100 mb-3 sm:mb-4 text-sm sm:text-base">
                FAISS Index Configuration
              </h4>
              <div className="bg-muted p-3 sm:p-4 rounded-lg">
                <pre className="text-green-700 dark:text-green-500 text-xs sm:text-sm overflow-x-auto">
                  <code>
                    {`dimension = 768  # all-mpnet-base-v2 output
nlist = 1024     # number of clusters
quantizer = faiss.IndexFlatL2(dimension)
index = faiss.IndexIVFPQ(quantizer, dimension, nlist, m, nbits)`}
                  </code>
                </pre>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Interactive Query Examples */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center space-x-2">
            <Search className="h-5 w-5 sm:h-6 sm:w-6 text-green-600" />
            <span className="text-lg sm:text-xl">Interactive Query Examples</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {/* <p className="text-sm sm:text-base text-muted-foreground mb-4 sm:mb-6">
            Explore how different queries are processed through the vector
            search pipeline, showing embedding generation, similarity matching,
            and context retrieval.
          </p> */}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4 mb-4 sm:mb-6">
            {queryExamples.map((example, index) => (
              <Button
                key={index}
                variant={selectedQuery === index ? "default" : "outline"}
                className="h-auto p-3 sm:p-4 text-left justify-start w-full"
                onClick={() =>
                  setSelectedQuery(selectedQuery === index ? null : index)
                }
              >
                <div className="w-full">
                  <h4 className="font-medium mb-1 text-sm sm:text-base break-words whitespace-normal">
                    &quot;{example.query}&quot;
                  </h4>
                  <p className="text-xs sm:text-sm opacity-70">
                    Click to see processing details
                  </p>
                </div>
              </Button>
            ))}
          </div>

          {selectedQuery !== null && (
            <Card className="border-2 dark:border-green-800 border-green-500 bg-green-500/10 dark:bg-green-800/10">
              <CardContent className="p-4 sm:p-6">
                <div className="space-y-4 sm:space-y-6">
                  <div>
                    <h4 className="font-semibold text-foreground mb-2 text-sm sm:text-base">
                      1. Query Embedding
                    </h4>
                    <div className="bg-muted p-2 sm:p-3 rounded">
                      <code className="text-muted-foreground text-xs sm:text-sm break-all">
                        query_vector = {queryExamples[selectedQuery].embedding}
                      </code>
                    </div>
                  </div>

                  <div>
                    <h4 className="font-semibold text-foreground mb-2 text-sm sm:text-base">
                      2. Similarity Search Results
                    </h4>
                    <div className="space-y-2">
                      {queryExamples[selectedQuery].similarScenes.map(
                        (scene, index) => (
                          <div
                            key={index}
                            className="flex items-center justify-between bg-background p-3 rounded border"
                          >
                            <div className="flex-1">
                              <p className="text-foreground font-medium text-sm sm:text-base">
                                {scene.scene}
                              </p>
                              <p className="text-muted-foreground text-xs sm:text-sm">
                                {scene.timestamp}
                              </p>
                            </div>
                            <Badge variant="secondary">
                              {(scene.similarity * 100).toFixed(1)}% match
                            </Badge>
                          </div>
                        ),
                      )}
                    </div>
                  </div>

                  <div>
                    <h4 className="font-semibold text-foreground mb-2 text-sm sm:text-base">
                      3. LLM Synthesis
                    </h4>
                    <div className="border border-border p-3 sm:p-4 rounded bg-amber-100/80 dark:bg-amber-900/50">
                      <p className="text-foreground text-sm sm:text-base">
                        &quot;{queryExamples[selectedQuery].response}&quot;
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </CardContent>
      </Card>

      {/* Performance Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6">
        <Card className="text-center">
          <CardContent className="p-4 sm:p-6">
            <Zap className="h-6 w-6 sm:h-8 sm:w-8 text-foreground mx-auto mb-2 sm:mb-3" />
            <h3 className="font-semibold text-foreground mb-1 sm:mb-2 text-sm sm:text-base">
              Query Latency
            </h3>
            <div className="text-2xl sm:text-3xl font-bold text-foreground mb-1">
              &lt;50ms
            </div>
            <p className="text-muted-foreground text-xs sm:text-sm">
              Average search time across 1M+ vectors
            </p>
          </CardContent>
        </Card>

        <Card className="text-center">
          <CardContent className="p-4 sm:p-6">
            <Database className="h-6 w-6 sm:h-8 sm:w-8 text-foreground mx-auto mb-2 sm:mb-3" />
            <h3 className="font-semibold text-foreground mb-1 sm:mb-2 text-sm sm:text-base">
              Memory Efficiency
            </h3>
            <div className="text-2xl sm:text-3xl font-bold text-foreground mb-1">75%</div>
            <p className="text-muted-foreground text-xs sm:text-sm">
              Compression ratio vs. flat index
            </p>
          </CardContent>
        </Card>

        <Card className="text-center">
          <CardContent className="p-4 sm:p-6">
            <Search className="h-6 w-6 sm:h-8 sm:w-8 text-foreground mx-auto mb-2 sm:mb-3" />
            <h3 className="font-semibold text-foreground mb-1 sm:mb-2 text-sm sm:text-base">
              Search Accuracy
            </h3>
            <div className="text-2xl sm:text-3xl font-bold text-foreground mb-1">95%</div>
            <p className="text-muted-foreground text-xs sm:text-sm">
              Recall@10 on semantic queries
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
