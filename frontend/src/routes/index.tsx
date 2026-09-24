import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ArrowRight, ScanFace } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { signInWithGoogle } from "@/lib/auth";
import { GOOGLE_AUTH_ENABLED } from "@/lib/feature-flags";
import heroImage from "@/assets/hero-photos.jpg";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "FaceSeek — Find every face, rediscover every photo" },
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
    <div className="min-h-screen bg-background">
      <header className="mx-auto flex h-20 max-w-[90rem] items-center justify-between border-b border-foreground/15 px-5 sm:px-8">
        <Link to="/" className="flex items-center gap-2.5" aria-label="FaceSeek home">
          <ScanFace className="h-5 w-5 text-primary" strokeWidth={1.7} />
          <span className="text-sm font-bold uppercase tracking-[0.13em]">FaceSeek</span>
        </Link>
        <nav className="flex items-center gap-5 text-xs font-semibold uppercase tracking-[0.1em] sm:gap-8">
          <Link to="/demo" className="hidden transition-colors hover:text-primary sm:inline">
            Demo
          </Link>
          <Link to="/about" className="transition-colors hover:text-primary">
            About
          </Link>
        </nav>
      </header>

      <main className="mx-auto max-w-[90rem] px-5 sm:px-8">
        <section className="grid min-h-[calc(100vh-5rem)] items-center gap-10 py-12 lg:grid-cols-[1.18fr_0.82fr] lg:gap-16 lg:py-16">
          <div>
            <p className="flex items-center gap-3 text-xs font-semibold uppercase tracking-[0.14em] text-primary">
              <span className="h-px w-12 bg-primary" aria-hidden />
              Private face search
            </p>
            <h1 className="mt-7 max-w-[12ch] font-serif text-[clamp(4.5rem,9vw,9.2rem)] leading-[0.82] tracking-[-0.055em] text-foreground">
              Find every <em className="text-primary">face.</em>
              <br />
              Rediscover every photo.
            </h1>
            <div className="mt-9 border-t border-foreground pt-6">
              <p className="max-w-lg text-lg leading-relaxed text-muted-foreground">
                Search a photo collection by the person in the frame. Start with our curated demo,
                then connect your own private library.
              </p>
            </div>
            <div className="mt-9 flex flex-wrap items-center gap-3">
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
            </div>
          </div>

          <div className="relative lg:justify-self-end">
            <div className="absolute -left-4 -top-4 z-10 bg-primary px-4 py-3 text-xs font-bold uppercase tracking-[0.12em] text-white sm:-left-7 sm:-top-7">
              Search by face
              <br />
              not by filename
            </div>
            <div className="relative aspect-[4/5] max-h-[70vh] overflow-hidden bg-muted">
              <img
                src={heroImage}
                alt="Vintage photo prints in warm afternoon light"
                width={1536}
                height={1024}
                className="h-full w-full object-cover saturate-[0.9] transition-transform duration-700 hover:scale-[1.02]"
              />
              <div className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-foreground/90 px-5 py-4 text-xs uppercase tracking-[0.1em] text-background backdrop-blur-sm">
                <span>One face</span>
                <span className="text-white/55">Every matching moment</span>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
