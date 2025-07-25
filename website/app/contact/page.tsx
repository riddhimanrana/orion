import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Mail, Globe, MessageCircle, User } from "lucide-react";
import Link from "next/link";
import { SiGithub } from "react-icons/si";

export default function ContactPage() {
  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-12 max-w-4xl">
        {/* Header Section */}
        <div className="text-center mb-12">
          <h1 className="text-4xl md:text-5xl font-bold mb-4 bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
            Get in Touch
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Have questions about Orion? Need support? Want to connect?
            We&apos;re here to help.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Support Section */}
          <Card className="h-fit">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <MessageCircle className="h-6 w-6 text-primary" />
                </div>
                <div>
                  <CardTitle>Orion Support</CardTitle>
                  <CardDescription>Get help with Orion Live AI</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* <p className="text-sm text-muted-foreground">
                Need assistance or have questions about Orion? Our support team
                is ready to help you get the most out of your AI experience.
              </p> */}
              <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                <Mail className="h-5 w-5 text-primary flex-shrink-0" />
                <div>
                  <p className="font-medium">support@orionlive.ai</p>
                  <p className="text-xs text-muted-foreground">
                    Response within 24 hours
                  </p>
                </div>
              </div>
              <Button asChild className="w-full">
                <Link href="mailto:support@orionlive.ai?subject=Orion Support Request">
                  <Mail className="h-4 w-4" />
                  Send Support Email
                </Link>
              </Button>
            </CardContent>
          </Card>
          <Card className="h-fit">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <MessageCircle className="h-6 w-6 text-primary" />
                </div>
                <div>
                  <CardTitle>Orion Contact</CardTitle>
                  <CardDescription>
                    Research/Business related inquiries?
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* <p className="text-sm text-muted-foreground">
                Need assistance or have questions about Orion? Our support team
                is ready to help you get the most out of your AI experience.
              </p> */}
              <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                <Mail className="h-5 w-5 text-primary flex-shrink-0" />
                <div>
                  <p className="font-medium">contact@orionlive.ai</p>
                  <p className="text-xs text-muted-foreground">
                    Response within 24 hours
                  </p>
                </div>
              </div>
              <Button asChild className="w-full">
                <Link href="mailto:contact@orionlive.ai?subject=Orion Contact Request">
                  <Mail className="h-4 w-4" />
                  Contact Orion Team
                </Link>
              </Button>
            </CardContent>
          </Card>

          {/* Creator Section */}
          <Card className="h-fit">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <User className="h-6 w-6 text-primary" />
                </div>
                <div>
                  <CardTitle>Creator</CardTitle>
                  <CardDescription>Riddhiman Rana</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                CEO, Researcher, Developer.
              </p>

              <div className="space-y-3">
                <Button asChild variant="outline" className="w-full">
                  <Link
                    href="https://github.com/riddhimanrana"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <SiGithub className="h-4 w-4" />
                    GitHub Profile
                  </Link>
                </Button>

                <Button asChild variant="outline" className="w-full">
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
            </CardContent>
          </Card>
        </div>

        {/* Additional Info Section */}

        {/* Footer Note */}
        {/* <div className="text-center mt-12 p-6 bg-muted/30 rounded-lg">
          <p className="text-sm text-muted-foreground">
            <Heart className="h-4 w-4 inline text-red-500" /> Built with passion
            by Riddhiman Rana. Orion Live AI is designed to empower users with
            intelligent conversations and assistance.
          </p>
        </div> */}
      </div>
    </div>
  );
}
