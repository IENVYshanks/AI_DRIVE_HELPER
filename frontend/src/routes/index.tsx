import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ArrowRight, Aperture } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { signInWithGoogle } from "@/lib/auth";
import { GOOGLE_AUTH_ENABLED } from "@/lib/feature-flags";
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

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden>
      <path
        fill="#EA4335"
        d="M12 10.2v3.9h5.45c-.24 1.26-1.62 3.7-5.45 3.7-3.28 0-5.95-2.71-5.95-6.05S8.72 5.7 12 5.7c1.86 0 3.11.79 3.82 1.47l2.6-2.5C16.85 3.16 14.63 2.2 12 2.2 6.76 2.2 2.5 6.46 2.5 11.75S6.76 21.3 12 21.3c6.93 0 9.5-4.86 9.5-7.34 0-.5-.05-.88-.12-1.26z"
      />
    </svg>
  );
}

function LandingPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [authLoading, setAuthLoading] = useState(false);

  useEffect(() => {
    if (GOOGLE_AUTH_ENABLED && user) navigate({ to: "/dashboard" });
  }, [user, navigate]);

  const handleGoogle = async () => {
    setAuthLoading(true);
    try {
      await signInWithGoogle();
      toast.success("Signed in with Google");
      navigate({ to: "/dashboard" });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Google sign-in failed");
    } finally {
      setAuthLoading(false);
    }
  };

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
            {GOOGLE_AUTH_ENABLED && (
              <Button variant="outline" onClick={handleGoogle} disabled={authLoading}>
                <GoogleIcon />
                <span>{authLoading ? "Connecting..." : "Continue with Google"}</span>
              </Button>
            )}
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
