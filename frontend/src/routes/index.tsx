import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, Aperture } from "lucide-react";
import { Button } from "@/components/ui/button";
import heroImage from "@/assets/hero-photos.jpg";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Atelier — Photos that find each other" },
      {
        name: "description",
        content: "Explore a face-search demo and rediscover related photos from one frame.",
      },
    ],
  }),
  component: LandingPage,
});

function LandingPage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-background">
      <div className="absolute inset-0 bg-gradient-warm opacity-60" aria-hidden />
      <div className="relative mx-auto flex min-h-screen max-w-5xl items-center px-5 py-10 lg:py-16">
        <div className="w-full">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Aperture className="h-4 w-4 text-primary" />
            <span className="uppercase tracking-widest">Atelier</span>
          </div>
          <h1 className="mt-5 max-w-3xl font-serif text-5xl leading-[1.05] tracking-tight text-foreground sm:text-6xl lg:text-7xl">
            Photos that <em className="text-clay not-italic">find</em> each other.
          </h1>
          <p className="mt-6 max-w-xl text-base leading-relaxed text-muted-foreground">
            Explore a curated photo collection and discover every moment featuring the person you
            choose—no sign-in required.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Button asChild>
              <Link to="/demo">
                Try the demo
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
            <Link
              to="/about"
              className="group inline-flex items-center gap-1 text-sm font-medium text-foreground"
            >
              About us
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>
          </div>

          <div className="relative mt-10 overflow-hidden rounded-xl shadow-editorial">
            <img
              src={heroImage}
              alt="Vintage photo prints in warm afternoon light"
              width={1536}
              height={1024}
              className="h-64 w-full object-cover sm:h-80"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
