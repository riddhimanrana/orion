'use client';

import { Suspense } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ResearchOverview } from "@/components/research/research-overview";
import { TechnicalSpecifications } from "@/components/research/technical-specifications";
import { MemorySection } from "@/components/research/memory-section";
import { HowItWorks } from "@/components/research/how-it-works";
import { Timeline } from "@/components/research/timeline";
import { Validation } from "@/components/research/validation";
import { RelatedWorks } from "@/components/research/related-works";
import { ApplicationSection } from "@/components/research/application";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { SiHuggingface, SiGithub } from "react-icons/si";

export function ResearchPageClient() {
  return (
    <div className="min-h-screen bg-background overflow-hidden scroll-smooth">
      {/* Research Header */}
      <section className="py-16 border-b">
        <div className="container mx-auto px-4 max-w-6xl">
          <div className="text-center space-y-6">
            <h1 className="text-4xl md:text-6xl font-bold tracking-tight">
              Research
            </h1>

            <p className="text-sm md:text-xl text-muted-foreground max-w-4xl mx-auto leading-relaxed">
              My research focuses on advancing visual perception systems by
              integrating edge-cloud processing, ensuring robust privacy
              safeguards, and leveraging dynamic temporal modeling to enable
              scalable, real-time scene understanding. I have not yet completed
              my research and work so this is just a preview of what I have done
              so far.
            </p>
          </div>
        </div>
      </section>

      {/* Research Content */}
      <div className="container mx-auto px-4 max-w-6xl py-12">
        <div className="space-y-16">
          {/* Research Overview */}
          <Suspense
            fallback={
              <div className="h-96 animate-pulse bg-muted rounded-lg" />
            }
          >
            <ResearchOverview />
          </Suspense>

          <Separator />

          {/* How It Works Section */}
          <Suspense
            fallback={
              <div className="h-96 animate-pulse bg-muted rounded-lg" />
            }
          >
            <HowItWorks />
          </Suspense>

          <Separator />

          {/* Technical Specifications */}
          <Suspense
            fallback={
              <div className="h-96 animate-pulse bg-muted rounded-lg" />
            }
          >
            <TechnicalSpecifications />
          </Suspense>

          <Separator />

          {/* Memory Section */}
          <Suspense
            fallback={
              <div className="h-96 animate-pulse bg-muted rounded-lg" />
            }
          >
            <MemorySection />
          </Suspense>

          <Separator />

          {/* Validation Framework */}
          <Suspense
            fallback={
              <div className="h-96 animate-pulse bg-muted rounded-lg" />
            }
          >
            <Validation />
          </Suspense>

          <Separator />
          {/* Development Timeline */}
          <Suspense
            fallback={
              <div className="h-96 animate-pulse bg-muted rounded-lg" />
            }
          >
            <Timeline />
          </Suspense>

          <Separator />

          {/* Real-World Applications */}
          <Suspense
            fallback={
              <div className="h-96 animate-pulse bg-muted rounded-lg" />
            }
          >
            <ApplicationSection />
          </Suspense>

          {/* Related Works & References */}
          <Separator />
          <Suspense
            fallback={
              <div className="h-96 animate-pulse bg-muted rounded-lg" />
            }
          >
            <RelatedWorks />
          </Suspense>
        </div>
      </div>

      {/* Research Footer */}
      <section className="py-16 bg-muted/30 border-t">
        <div className="container mx-auto px-4 max-w-6xl">
          <Card>
            <CardContent className="p-8 text-center">
              <h3 className="text-2xl font-bold mb-4">
                Open Science & Resources
              </h3>
              <p className="text-muted-foreground mb-6 max-w-2xl mx-auto">
                I have released my fine-tuned FastVLM-0.5b model and the custom
                COCO dataset used for validation. Explore the model and dataset
                on Huggingface, and check out the complete codebase on GitHub. I
                plan to formally publish this research in about one year through
                a professor-led collaboration.
              </p>
              <div className="flex flex-wrap justify-center gap-4">
                <Link
                  href="https://huggingface.co/riddhimanrana/fastvlm-0.5b-captions"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Button
                    variant="outline"
                    className="flex items-center px-4 py-2"
                  >
                    <SiHuggingface className="h-4 w-4 mr-1" />
                    Fine-tuned FastVLM-0.5b Model
                  </Button>
                </Link>
                <Link
                  href="https://huggingface.co/datasets/riddhimanrana/coco-fastvlm-2k-val2017"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Button
                    variant="outline"
                    className="flex items-center px-4 py-2"
                  >
                    <SiHuggingface className="h-4 w-4 mr-1" />
                    Custom COCO Dataset
                  </Button>
                </Link>
                <Link
                  href="https://github.com/riddhimanrana/orion"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Button
                    variant="outline"
                    className="flex items-center px-4 py-2"
                  >
                    <SiGithub className="h-4 w-4 mr-1" />
                    Code Repository
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
