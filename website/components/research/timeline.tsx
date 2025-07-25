import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle, Circle, Clock, Smartphone, Database, Brain, Rocket } from "lucide-react";
import { cn } from "@/lib/utils";

interface TimelineItem {
  period: string;
  title: string;
  description: string;
  status: "completed" | "current" | "upcoming";
  icon: React.ReactNode;
  details: string[];
  phase?: string;
}

const timelineData: TimelineItem[] = [
  {
    period: "June 2025 - July 2025",
    title: "Research Phase 1: Foundation & Prototype Development",
    description: "Core infrastructure, authentication, and initial prototypes. So far during this time I have made a fully built out API, auth system(w/email), a Mac app, and an iOS app which are all fully functional and passing all unit tests.",
    status: "completed",
    icon: <Smartphone className="h-4 w-4 sm:h-5 sm:w-5" />,
    phase: "Research Phase 1",
    details: [
      "API architecture & authentication",
      "Dashboard, Mac app, iOS app development",
      "FastVLM, YOLOv11n, Gemma-3B prototypes"
    ]
  },
  {
    period: "August 2025 - December 2025",
    title: "Research Phase 2: Vector Database & Server Architecture", 
    description: "Vector database system and server architecture optimization. This phase also does include framework validation and making sure that vector database search is evaluated and tweaked.",
    status: "current",
    icon: <Database className="h-4 w-4 sm:h-5 sm:w-5" />,
    phase: "Research Phase 2",
    details: [
      "Vector database implementation",
      "Edge-cloud processing framework",
      "Distributed inference protocols"
    ]
  },
  {
    period: "January 2025 - April 2026",
    title: "Research Phase 3: Dynamic Graph Knowledge System",
    description: "Advanced temporal reasoning and dynamic knowledge systems. I will also be tweaking the Gemma-3B model to work with the vector database and the dynamic graph knowledge system, and creating a new model that can understand the context of the scene based on this new information.",
    status: "upcoming",
    icon: <Brain className="h-4 w-4 sm:h-5 sm:w-5" />,
    phase: "Research Phase 3",
    details: [
      "Dynamic graph architecture",
      "Temporal reasoning models",
      "Real-time scene understanding"
    ]
  },
  {
    period: "May 2026 - June 2026",
    title: "Beta Deployment & Publication",
    description: "Real-world deployment and academic research publication. This would mean deployment as a real-world service in beta that people could actually use and test out, and also publishing the research paper on the work done so far.",
    status: "upcoming",
    icon: <Rocket className="h-4 w-4 sm:h-5 sm:w-5" />,
    details: [
      "Beta application deployment",
      "Research paper completion",
      "Public release preparation"
    ]
  }
];

export function Timeline() {
  const getStatusIcon = (status: TimelineItem["status"]) => {
    switch (status) {
      case "completed":
        return <CheckCircle className="h-6 w-6 text-green-500" />;
      case "current":
        return <Clock className="h-6 w-6 text-blue-500" />;
      case "upcoming":
        return <Circle className="h-6 w-6 text-muted-foreground" />;
    }
  };

  const getStatusBadge = (status: TimelineItem["status"]) => {
    switch (status) {
      case "completed":
        return (
          <Badge className="bg-green-50 text-green-700 border-green-200 dark:bg-green-900 dark:text-green-200 dark:border-green-700">
            Completed
          </Badge>
        );
      case "current":
        return (
          <Badge className="bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900 dark:text-blue-200 dark:border-blue-700">
            In Progress
          </Badge>
        );
      case "upcoming":
        return (
          <Badge variant="outline" className="text-muted-foreground">
            Upcoming
          </Badge>
        );
    }
  };

  return (
    <section className="space-y-8 sm:space-y-10">
      <div className="text-center space-y-2 sm:space-y-3">
        <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight">Development Timeline</h2>
        {/* <p className="text-sm sm:text-base text-muted-foreground max-w-2xl mx-auto">
          My roadmap for the next year of research and development for Orion.
        </p> */}
      </div>

      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-4 sm:left-6 top-0 bottom-0 w-0.5 bg-border" />

        <div className="space-y-4 sm:space-y-6">
          {timelineData.map((item, index) => (
            <div key={index} className="relative flex gap-3 sm:gap-4">
              {/* Timeline node */}
              <div className="relative z-10 flex-shrink-0">
                <div
                  className={cn(
                    "flex h-8 w-8 sm:h-12 sm:w-12 items-center justify-center rounded-full border-3 bg-background",
                    item.status === "completed" && "border-green-500",
                    item.status === "current" && "border-blue-500",
                    item.status === "upcoming" && "border-muted-foreground"
                  )}
                >
                  <div className="">
                    {item.icon}
                  </div>
                </div>
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0 pb-4 sm:pb-6">
                <Card className={cn(
                  "transition-all duration-200",
                  item.status === "current" && "border-blue-200 dark:border-blue-800 shadow-md"
                )}>
                  <CardContent className="p-3 sm:p-4">
                    <div className="flex items-start justify-between gap-3 sm:gap-4 mb-2">
                      <div className="space-y-1 flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          {getStatusIcon(item.status)}
                          <p className="text-xs font-medium text-muted-foreground">
                            {item.period}
                          </p>
                        </div>
                        <h3 className="font-semibold text-sm sm:text-lg">{item.title}</h3>
                        {item.phase && (
                          <Badge variant="secondary" className="w-fit text-xs">
                            {item.phase}
                          </Badge>
                        )}
                      </div>
                      <div className="flex-shrink-0">
                        {getStatusBadge(item.status)}
                      </div>
                    </div>
                    <p className="text-xs sm:text-sm text-muted-foreground mb-2 sm:mb-3">{item.description}</p>
                    <ul className="grid gap-1 text-xs text-muted-foreground">
                      {item.details.map((detail, detailIndex) => (
                        <li key={detailIndex} className="flex items-start gap-1">
                          <span className="text-primary">•</span>
                          <span className="break-words">{detail}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Current Status Summary */}
      {/* <Card className="border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-900/20">
        <CardContent className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="h-4 w-4 text-blue-500" />
            <h3 className="font-semibold text-sm">Current Status</h3>
          </div>
          <p className="text-sm text-muted-foreground">
            Currently in progress on <strong>Research Phase 1</strong> - building foundational infrastructure, 
            authentication systems, and initial prototypes across all platforms.
          </p>
        </CardContent>
      </Card> */}
    </section>
  );
}
