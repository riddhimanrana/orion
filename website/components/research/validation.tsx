"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { 
  Eye, 
  MessageSquare, 
  Search, 
  Network, 
  Clock,
  Target,
  Database,
  BarChart3,
  CheckCircle
} from "lucide-react";

interface ValidationMetric {
  component: string;
  task: string;
  metrics: string[];
  datasets: string[];
  icon: React.ReactNode;
  color: string;
  description: string;
}

const validationData: ValidationMetric[] = [
  {
    component: "YOLOv11n",
    task: "Real-time Object Detection",
    metrics: ["mAP (mean Average Precision)", "FPS (Frames Per Second)"],
    datasets: ["MS-COCO", "Open Images Dataset"],
    icon: <Eye className="h-5 w-5" />,
    color: "bg-blue-500",
    description: "Evaluating object detection accuracy and real-time performance capabilities"
  },
  {
    component: "FastVLM-0.5b",
    task: "Image/Frame Captioning",
    metrics: ["BLEU", "METEOR", "CIDEr"],
    datasets: ["MS-COCO Captions", "Flickr30k"],
    icon: <MessageSquare className="h-5 w-5" />,
    color: "bg-green-500",
    description: "Measuring quality of machine-generated captions against human references"
  },
  {
    component: "Semantic Search (Milvus)",
    task: "Video Question Answering",
    metrics: ["Accuracy", "WUPS (Wu-Palmer Similarity)"],
    datasets: ["VideoQA", "Custom Video Benchmark"],
    icon: <Search className="h-5 w-5" />,
    color: "bg-purple-500",
    description: "Testing semantic similarity and retrieval accuracy for video content"
  },
  {
    component: "Knowledge Extraction",
    task: "Entity & Relation Extraction",
    metrics: ["Precision", "Recall", "F1-score"],
    datasets: ["Custom-annotated Dataset", "ConceptNet"],
    icon: <Network className="h-5 w-5" />,
    color: "bg-orange-500",
    description: "Evaluating correctness of (subject, predicate, object) triple extraction"
  },
  {
    component: "Temporal Reasoning",
    task: "Temporal & Causal QA",
    metrics: ["Accuracy on Custom Benchmark", "Causal Reasoning Score"],
    datasets: ["Custom Benchmark (REXTIME-inspired)", "SOK-Bench"],
    icon: <Clock className="h-5 w-5" />,
    color: "bg-red-500",
    description: "Testing unique reasoning for questions like 'Why did event X happen?'"
  }
];

const evaluationObjectives = [
  {
    title: "Semantic Retrieval Evaluation",
    description: "Evaluate semantic retrieval performance on video content",
    status: "In Progress",
    icon: <Target className="h-4 w-4" />
  },
  {
    title: "VideoQA Benchmarking",
    description: "Benchmark system performance on VideoQA datasets",
    status: "Planned",
    icon: <BarChart3 className="h-4 w-4" />
  },
  {
    title: "Scene Description Quality",
    description: "Test and validate scene description generation quality",
    status: "Completed",
    icon: <CheckCircle className="h-4 w-4" />
  },
  {
    title: "Custom Temporal Benchmark",
    description: "Develop custom temporal reasoning benchmark dataset",
    status: "In Progress",
    icon: <Database className="h-4 w-4" />
  },
  {
    title: "Causal Reasoning Testing",
    description: "Test causal reasoning capabilities and accuracy",
    status: "Planned",
    icon: <Network className="h-4 w-4" />
  },
  {
    title: "Entity Resolution Accuracy",
    description: "Evaluate entity resolution and disambiguation accuracy",
    status: "In Progress",
    icon: <Eye className="h-4 w-4" />
  }
];

export function Validation() {
  return (
    <section className="space-y-8">
      <div className="text-center space-y-4">
        <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight">
          Validation Framework
        </h2>
        {/* <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
          Comprehensive evaluation methodology for each system component, 
          using industry-standard metrics and carefully curated datasets 
          to ensure robust performance validation.
        </p> */}
      </div>

      {/* Component Evaluation Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Component Evaluation Metrics
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="min-w-[200px]">Component</TableHead>
                  <TableHead className="min-w-[180px]">Evaluation Task</TableHead>
                  <TableHead className="min-w-[200px]">Metrics</TableHead>
                  <TableHead className="min-w-[200px]">Datasets</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {validationData.map((item, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-md ${item.color} text-white`}>
                          {item.icon}
                        </div>
                        <div>
                          <div className="font-medium">{item.component}</div>
                          <div className="text-sm text-muted-foreground">
                            {item.description}
                          </div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="whitespace-nowrap">
                        {item.task}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        {item.metrics.map((metric, i) => (
                          <Badge key={i} variant="secondary" className="mr-1 mb-1">
                            {metric}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        {item.datasets.map((dataset, i) => (
                          <div key={i} className="text-sm flex items-center gap-1">
                            <Database className="h-3 w-3 text-muted-foreground" />
                            {dataset}
                          </div>
                        ))}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Evaluation Objectives */}
      <div className="space-y-6">
        <div className="text-center">
          <h3 className="text-2xl font-bold mb-2">Evaluation Objectives</h3>
          {/* <p className="text-muted-foreground">
            Key validation goals and current progress status
          </p> */}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {evaluationObjectives.map((objective, index) => (
            <Card key={index} className="h-full">
              <CardContent className="p-6">
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-primary/10 rounded-md">
                    {objective.icon}
                  </div>
                  <div className="flex-1 space-y-2">
                    <h4 className="font-semibold leading-tight">
                      {objective.title}
                    </h4>
                    <p className="text-sm text-muted-foreground">
                      {objective.description}
                    </p>
                    <Badge 
                      variant={
                        objective.status === "Completed" ? "default" :
                        objective.status === "In Progress" ? "secondary" : "outline"
                      }
                      className="text-xs"
                    >
                      {objective.status}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>


      {/* Validation Methodology */}
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Validation Methodology</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <h4 className="font-semibold flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-green-500" />
                Standard Metrics Justification
              </h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>• <strong>BLEU, METEOR, CIDEr:</strong> Testing for text generation quality</li>
                <li>• <strong>mAP:</strong> Standard for object detection accuracy(used in YOLO research papers as well)</li>
                <li>• <strong>WUPS:</strong> Semantic similarity for open-ended answers</li>
                <li>• <strong>Precision/Recall/F1:</strong> Used for knowledge extraction evaluation</li>
              </ul>
            </div>
            
            <div className="space-y-4">
              <h4 className="font-semibold flex items-center gap-2">
                <Target className="h-4 w-4 text-blue-500" />
                Custom Benchmarks
              </h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>• <strong>Temporal QA:</strong> I will develop a custom benchmark for unique reasoning capabilities</li>
                <li>• <strong>Video Context:</strong> Similar, specific evaluation datasets</li>
                <li>• <strong>Real-time Performance:</strong> FPS metrics for practical deployment(real-time abilities)</li>
                <li>• <strong>Causal Reasoning:</strong> Evaluation for &ldquo;Why&rdquo; questions</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
