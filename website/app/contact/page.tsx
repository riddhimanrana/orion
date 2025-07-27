import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Mail, Globe, MessageCircle, User, Briefcase} from "lucide-react";
import Link from "next/link";
import { SiGithub } from "react-icons/si";

export default function ContactPage() {
  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-12 max-w-4xl">
        {/* Header Section */}
        <div className="text-center mb-12">
          <h1 className="text-3xl md:text-6xl font-bold mb-4 ">
            Get in Touch
          </h1>
          {/* <p className="text-lg text-muted-foreground max-w-xl mx-auto">
            Have questions about Orion? Need support? Want to connect? We&apos;re here to help.
          </p> */}
        </div>

        {/* Contact Cards Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-12">
          {/* Support Card */}
          <Card className="group hover:shadow-lg transition-all duration-300 border-border/50">
            <CardHeader className="pb-3">
              <div className="flex items-start gap-3">
                <div className="p-2 bg-blue-500/10 rounded-lg group-hover:bg-blue-500/20 transition-colors">
                  <MessageCircle className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                </div>
                <div className="flex-1">
                  <CardTitle className="text-lg mb-1">Support & Help</CardTitle>
                  <CardDescription className="text-sm">
                    Get assistance with Orion Live
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="space-y-3">
                <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                  <Mail className="h-4 w-4 text-blue-600 dark:text-blue-400 flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-sm">support@orionlive.ai</p>
                    <p className="text-xs text-muted-foreground">
                      Support/Auth/App issues
                    </p>
                  </div>
                </div>
                <Button asChild className="w-full">
                  <Link href="mailto:support@orionlive.ai?subject=Orion Support Request">
                    <Mail className="h-4 w-4" />
                    Send Support Email
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Business Inquiries Card */}
          <Card className="group hover:shadow-lg transition-all duration-300 border-border/50">
            <CardHeader className="pb-3">
              <div className="flex items-start gap-3">
                <div className="p-2 bg-emerald-500/10 rounded-lg group-hover:bg-emerald-500/20 transition-colors">
                  <Briefcase className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                </div>
                <div className="flex-1">
                  <CardTitle className="text-lg mb-1">Business & Research</CardTitle>
                  <CardDescription className="text-sm">
                    Partnership, research, and business inquiries
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="space-y-3">
                <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                  <Mail className="h-4 w-4 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-sm">contact@orionlive.ai</p>
                    <p className="text-xs text-muted-foreground">
                      For partnerships and collaborations
                    </p>
                  </div>
                </div>
                <Button asChild variant="outline" className="w-full">
                  <Link href="mailto:contact@orionlive.ai?subject=Business Inquiry">
                    <Briefcase className="h-4 w-4" />
                    Send Business Email
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Creator Section */}
        <div className="max-w-xl mx-auto">
          <div className="text-center mb-6">
            <h2 className="text-xl font-bold mb-1">Creator</h2>
          </div>
          
          <Card className="group hover:shadow-lg transition-all duration-300">
            <CardContent className="p-6">
              <div className="flex flex-col md:flex-row items-center md:items-start gap-4">
                <div className="p-3 bg-purple-500/10 rounded-xl group-hover:bg-purple-500/20 transition-colors">
                  <User className="h-8 w-8 text-purple-600 dark:text-purple-400" />
                </div>
                
                <div className="flex-1 text-center md:text-left">
                  <h3 className="text-xl font-bold mb-1">Riddhiman Rana</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Student Researcher & Developer for Orion Live/Orion Architecture
                  </p>
                  
                  <div className="flex flex-col sm:flex-row gap-2">
                    <Button asChild variant="outline" size="sm" className="flex-1">
                      <Link
                        href="https://github.com/riddhimanrana"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <SiGithub className="h-4 w-4" />
                        GitHub
                      </Link>
                    </Button>
                    
                    <Button asChild variant="outline" size="sm" className="flex-1">
                      <Link
                        href="https://riddhimanrana.com"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <Globe className="h-4 w-4" />
                        Personal Website
                      </Link>
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
