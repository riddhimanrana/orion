"use client";

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExternalLink, Github, FileText, Database, Brain } from "lucide-react";
import { SiHuggingface, SiArxiv, SiGithub } from "react-icons/si";
import Link from "next/link";

interface Reference {
  id: string;
  title: string;
  authors?: string;
  description?: string;
  type: "model" | "dataset" | "paper" | "repository" | "database" | "website";
  links: {
    label: string;
    url: string;
    icon?: React.ComponentType<{ className?: string }>;
  }[];
  year?: string;
  venue?: string;
}

const references: Reference[] = [
  {
    id: "fastvlm",
    title: "FastVLM",
    description: "FastVLM is a novel hybrid vision encoder designed to output fewer tokens and significantly reduce encoding time for high-resolution images based off FastViTHD. This was the base model I used for my finetuned FastVLM model.",
    type: "model",
    links: [
      {
        label: "GitHub",
        url: "https://github.com/apple/ml-fastvlm",
        icon: SiGithub,
      },
      {
        label: "arXiv Paper",
        url: "https://arxiv.org/pdf/2412.13303",
        icon: SiArxiv,
      },
      {
        label: "Apple ML Research",
        url: "https://machinelearning.apple.com/research/fast-vision-language-models",
        icon: ExternalLink,
      }
    ],
  },
  {
    id: "mobileclip",
    title: "MobileCLIP",
    description: "Apple's MobileCLIP model is designed for efficient vision-language tasks on mobile devices. This was the base vision tower I used for my finetuned FastVLM model which is based off the LlaVA model.",
    type: "model",
    links: [
      {
        label: "GitHub",
        url: "https://github.com/apple/ml-mobileclip",
        icon: SiGithub,
      },
      {
        label: "arXiv Paper",
        url: "https://arxiv.org/pdf/2311.17049",
        icon: SiArxiv,
      },
      {
        label: "Hugging Face",
        url: "https://huggingface.co/apple/MobileCLIP-S0",
        icon: SiHuggingface,
      }
    ],
  },
//   {
//     id: "fastvithd",
//     title: "FastViTHD",
//     authors: "Shaoxiong Ji, Shirui Pan, Erik Cambria, Pekka Marttinen, Philip S. Yu",
//     type: "paper",
//     links: [
//       {
//         label: "arXiv Paper",
//         url: "https://arxiv.org/abs/2403.06651",
//         icon: SiArxiv,
//       },
//     ],
//   },
  {
    id: "neo4j",
    title: "Neo4j Graph Database",
    description: "Graph database platform used for storing and querying complex relationships in knowledge graphs, enabling sophisticated temporal reasoning and semantic connections for Orion.",
    type: "database",
    links: [
        {
        label: "GitHub",
        url: "https://github.com/neo4j/neo4j",
        icon: SiGithub,
      },
      {
        label: "Documentation",
        url: "https://neo4j.com/docs/",
        icon: FileText,
      },
      {
        label: "Website",
        url: "https://neo4j.com/",
        icon: ExternalLink,
      },
      
      
    ],
  },
  {
    id: "milvus",
    title: "Milvus Vector Database",
    description: "Open-source vector database designed for AI applications, providing efficient high-performance similarity search and vector indexing for multimodal embeddings.",
    type: "database",
    links: [
        {
        label: "GitHub",
        url: "https://github.com/milvus-io/milvus",
        icon: SiGithub,
      },
      {
        label: "Documentation",
        url: "https://milvus.io/docs",
        icon: FileText,
      },
      {
        label: "Website",
        url: "https://milvus.io/",
        icon: ExternalLink,
      }
      
      
    ],
  },
  {
    id: "kg-survey",
    title: "A Survey on Knowledge Graphs: Representation, Acquisition and Applications",
    authors: "Shaoxiong Ji, Shirui Pan, Erik Cambria, Pekka Marttinen, Philip S. Yu",
    type: "paper",
    links: [
      {
        label: "arXiv",
        url: "https://arxiv.org/pdf/2002.00388",
        icon: SiArxiv,
      },
    ],
    year: "2021",
  },
  {
    id: "gaze-following",
    title: "Exploring the Zero-Shot Capabilities of Vision-Language Models for Improving Gaze Following",
    authors: "Anshul Gupta, Pierre Vuillecard, Arya Farkhondeh, Jean-Marc Odobez",
    type: "paper",
    links: [
      {
        label: "CVF Open Access",
        url: "https://openaccess.thecvf.com/content/CVPR2024W/GAZE/papers/Gupta_Exploring_the_Zero-Shot_Capabilities_of_Vision-Language_Models_for_Improving_Gaze_CVPRW_2024_paper.pdf",
        icon: FileText,
      },
    ],
    year: "2024",
    venue: "CVPR Workshop",
  },
  {
    id: "trisense",
    title: "Trisense: Watch and Listen: Understanding Audio-Visual-Speech Moments with Multimodal LLM",
    authors: "Zinuo Li, Xian Zhang, Yongxin Guo, Mohammed Bennamoun, Farid Boussaid, Girish Dwivedi, Luqi Gong, Qiuhong Ke",
    type: "paper",
    links: [
      {
        label: "arXiv",
        url: "https://arxiv.org/pdf/2505.18110v1",
        icon: SiArxiv,
      },
    ],
    year: "2024",
  },
];

const getTypeIcon = (type: Reference["type"]) => {
  switch (type) {
    case "model":
      return Brain;
    case "dataset":
      return Database;
    case "paper":
      return FileText;
    case "repository":
      return Github;
    case "database":
      return Database;
    case "website":
      return ExternalLink;
    default:
      return FileText;
  }
};

const getTypeColor = (type: Reference["type"]) => {
  switch (type) {
    case "model":
      return "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900 dark:text-blue-200 dark:border-blue-700";
    case "dataset":
      return "bg-green-50 text-green-700 border-green-200 dark:bg-green-900 dark:text-green-200 dark:border-green-700";
    case "paper":
      return "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-900 dark:text-purple-200 dark:border-purple-700";
    case "repository":
      return "bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-900 dark:text-orange-200 dark:border-orange-700";
    case "database":
      return "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900 dark:text-emerald-200 dark:border-emerald-700";
    case "website":
      return "bg-gray-50 text-gray-700 border-gray-200 dark:bg-gray-900 dark:text-gray-200 dark:border-gray-700";
    default:
      return "bg-gray-50 text-gray-700 border-gray-200 dark:bg-gray-900 dark:text-gray-200 dark:border-gray-700";
  }
};

const ReferenceCard = ({ reference }: { reference: Reference }) => {
  const IconComponent = getTypeIcon(reference.type);

  return (
    <Card className="h-full transition-all duration-200 hover:shadow-lg border-l-4 border-l-primary/20">
      <CardHeader className="-mb-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <IconComponent className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              <Badge variant="outline" className={getTypeColor(reference.type)}>
                {reference.type.charAt(0).toUpperCase() + reference.type.slice(1)}
              </Badge>
              {reference.year && (
                <Badge variant="secondary" className="text-xs">
                  {reference.year}
                </Badge>
              )}
            </div>
            <CardTitle className="text-lg leading-tight">
              {reference.title}
            </CardTitle>
            {reference.authors && (
              <p className="text-sm text-muted-foreground mt-1 font-medium">
                {reference.authors}
              </p>
            )}
            {reference.venue && (
              <p className="text-xs text-muted-foreground italic">
                {reference.venue}
              </p>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        {reference.description && (reference.type === "model" || reference.type === "database" || reference.type === "website") && (
          <p className="text-sm text-muted-foreground mb-2 leading-relaxed">
            {reference.description}
          </p>
        )}
        
        <div className="flex flex-wrap gap-2">
          {reference.links.map((link, index) => (
            <Link key={index} href={link.url} target="_blank" rel="noopener noreferrer">
              <Button variant="outline" size="sm" className="h-8 px-3">
                {link.icon && <link.icon className="h-3 w-3 mr-1.5" />}
                {link.label}
              </Button>
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};

export const RelatedWorks = () => {
  const groupedReferences = references.reduce((acc, ref) => {
    if (!acc[ref.type]) {
      acc[ref.type] = [];
    }
    acc[ref.type].push(ref);
    return acc;
  }, {} as Record<string, Reference[]>);

  const typeOrder: Reference["type"][] = ["model", "paper", "database", "dataset", "repository", "website"];

  return (
    <section className="space-y-8">
      <div className="text-center space-y-4">
        <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight">Related Works & References</h2>
        <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
          All the key research papers, technologies, and resources that I&apos;ve used so far in my research and development of the Orion architecture.
        </p>
      </div>

      <div className="space-y-12">
        {typeOrder.map((type) => {
          const refs = groupedReferences[type];
          if (!refs || refs.length === 0) return null;

          return (
            <div key={type} className="space-y-6">
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  {React.createElement(getTypeIcon(type), {
                    className: "h-5 w-5 text-primary",
                  })}
                  <h3 className="text-2xl font-semibold capitalize">
                    {type === "paper" ? "Research Papers" : 
                     type === "model" ? "Models & Frameworks" :
                     type === "database" ? "Databases & Infrastructure" :
                     `${type.charAt(0).toUpperCase()}${type.slice(1)}s`}
                  </h3>
                </div>
                <div className="flex-1 h-px bg-border" />
                <Badge variant="secondary" className="text-sm">
                  {refs.length} {refs.length === 1 ? 'item' : 'items'}
                </Badge>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {refs.map((reference) => (
                  <ReferenceCard key={reference.id} reference={reference} />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* <div className="text-center space-y-4">
        <h3 className="text-xl font-semibold">Contributing References</h3>
        <p className="text-sm text-muted-foreground max-w-2xl mx-auto">
          This research builds upon the foundational work of numerous researchers and open-source projects. 
          Each reference contributes unique insights and capabilities that enable the development of robust, 
          privacy-preserving visual intelligence systems.
        </p>
      </div> */}
    </section>
  );
};
