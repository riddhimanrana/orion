import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { 
  Drone, 
  Bot, 
  Accessibility, 
  Camera, 
  Shield, 
  Zap, 
  Globe,
  Home,
} from "lucide-react";

export function ApplicationSection() {
  const applications = [
    {
      icon: Accessibility,
      title: "Accessibility Assistance",
      description: "Real-time scene understanding for visually impaired users",
      features: [
        "Live scene narration and object identification",
        "Navigation assistance with obstacle detection",
        "Text recognition and reading assistance",
        "Smart home integration for daily activities"
      ],
      deployment: "Mobile apps, smart glasses, wearable devices"
    },
    {
      icon: Drone,
      title: "Autonomous Systems",
      description: "Visual perception for drones, robots, and autonomous vehicles",
      features: [
        "Real-time obstacle detection and avoidance",
        "Dynamic path planning with visual feedback",
        "Environmental monitoring and surveillance",
        "Search and rescue operations"
      ],
      deployment: "Edge computing modules, embedded systems"
    },
    {
      icon: Bot,
      title: "Intelligent Agents",
      description: "General-purpose visual intelligence for various applications",
      features: [
        "Interactive visual question answering",
        "Real-time video analysis and summarization",
        "Multi-modal conversation capabilities",
        "Context-aware visual reasoning"
      ],
      deployment: "Cloud services, mobile applications, web platforms"
    },
    {
      icon: Home,
      title: "Smart Environments",
      description: "Ambient intelligence for homes, offices, and public spaces",
      features: [
        "Occupancy detection and space optimization",
        "Security monitoring with privacy preservation",
        "Energy management through activity recognition",
        "Elderly care and health monitoring"
      ],
      deployment: "IoT devices, smart cameras, edge gateways"
    }
  ];

  // const industries = [
  //   { icon: Car, label: "Automotive", use: "Driver assistance systems" },
  //   { icon: Stethoscope, label: "Healthcare", use: "Medical imaging analysis" },
  //   { icon: ShoppingCart, label: "Retail", use: "Customer behavior analytics" },
  //   { icon: Globe, label: "Smart Cities", use: "Traffic and crowd management" }
  // ];

  return (
    <section id="applications" className="space-y-8">
      <div className="text-center space-y-4">
        <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
          Real-World Applications
        </h2>
        <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
          My whole goal with Orion Live is to serve as a deployable visual perception agent across many different domains,
          offering open-source, real-time, and privacy-first visual intelligence solutions.
        </p>
      </div>

      {/* Key Features */}
      <div className="flex flex-wrap justify-center gap-2 mb-8">
        <Badge className="bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900 dark:text-blue-200 dark:border-blue-700">
          <Zap className="h-3 w-3 mr-1" />
          Real-time Processing
        </Badge>
        <Badge className="bg-green-50 text-green-700 border-green-200 dark:bg-green-900 dark:text-green-200 dark:border-green-700">
          <Shield className="h-3 w-3 mr-1" />
          Privacy-First Design
        </Badge>
        <Badge className="bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-900 dark:text-purple-200 dark:border-purple-700">
          <Globe className="h-3 w-3 mr-1" />
          Open Source
        </Badge>
        <Badge className="bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-900 dark:text-orange-200 dark:border-orange-700">
          <Camera className="h-3 w-3 mr-1" />
          Multi-modal Intelligence
        </Badge>
      </div>

      {/* Application Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {applications.map((app, index) => {
          const IconComponent = app.icon;
          return (
            <Card key={index} className="h-full">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-primary/10">
                    <IconComponent className="h-6 w-6 text-primary" />
                  </div>
                  <div>
                    <CardTitle className="text-xl">{app.title}</CardTitle>
                    <p className="text-sm text-muted-foreground mt-1">
                      {app.description}
                    </p>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <h4 className="font-semibold mb-2 text-sm">Key Capabilities</h4>
                  <ul className="space-y-1">
                    {app.features.map((feature, idx) => (
                      <li key={idx} className="text-sm text-muted-foreground flex items-start gap-2">
                        <div className="w-1 h-1 rounded-full bg-primary mt-2 flex-shrink-0" />
                        {feature}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4 className="font-semibold mb-1 text-sm">Deployment</h4>
                  <p className="text-sm text-muted-foreground">{app.deployment}</p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Industry Applications */}
      {/* <Card>
        <CardHeader>
          <CardTitle className="text-xl flex items-center gap-2">
            <Eye className="h-5 w-5 text-primary" />
            Industry Applications
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {industries.map((industry, index) => {
              const IconComponent = industry.icon;
              return (
                <div key={index} className="text-center space-y-2 p-4 rounded-lg border">
                  <IconComponent className="h-8 w-8 text-primary mx-auto" />
                  <h4 className="font-semibold text-sm">{industry.label}</h4>
                  <p className="text-xs text-muted-foreground">{industry.use}</p>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card> */}

      {/* Competitive Advantages */}
      <Card
        className="shadow-lg bg-primary/5 border- border-l-6 border-purple-600 hover:shadow-xl transition-shadow"
      >
        <CardContent className="p-6">
          <h3 className="text-xl font-bold mb-4 text-center">
            Why Choose Orion Live?
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
            <div className="space-y-2">
              <Shield className="h-8 w-8 text-primary mx-auto" />
              <h4 className="font-semibold">Privacy-First</h4>
              <p className="text-sm text-muted-foreground">
                Unlike proprietary solutions, Orion processes data locally with optional cloud enhancement
              </p>
            </div>
            <div className="space-y-2">
              <Globe className="h-8 w-8 text-primary mx-auto" />
              <h4 className="font-semibold">Open Source</h4>
              <p className="text-sm text-muted-foreground">
                Fully transparent, customizable, and community-driven development
              </p>
            </div>
            <div className="space-y-2">
              <Zap className="h-8 w-8 text-primary mx-auto" />
              <h4 className="font-semibold">Real-Time</h4>
              <p className="text-sm text-muted-foreground">
                Edge-optimized processing for instant visual understanding
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
