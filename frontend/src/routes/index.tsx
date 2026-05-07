import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ArrowRight, Aperture } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { signIn, signUp, signInWithGoogle } from "@/lib/auth";
import { useAuth } from "@/hooks/use-auth";
import heroImage from "@/assets/hero-photos.jpg";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Atelier — Photos that find each other" },
      { name: "description", content: "Sign in to upload, organize, and rediscover your photos by image search." },
    ],
  }),
  component: LandingPage,
});

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden>
      <path fill="#EA4335" d="M12 10.2v3.9h5.45c-.24 1.26-1.62 3.7-5.45 3.7-3.28 0-5.95-2.71-5.95-6.05S8.72 5.7 12 5.7c1.86 0 3.11.79 3.82 1.47l2.6-2.5C16.85 3.16 14.63 2.2 12 2.2 6.76 2.2 2.5 6.46 2.5 11.75S6.76 21.3 12 21.3c6.93 0 9.5-4.86 9.5-7.34 0-.5-.05-.88-.12-1.26z"/>
    </svg>
  );
}

function LandingPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  useEffect(() => {
    if (user) navigate({ to: "/dashboard" });
  }, [user, navigate]);

  // signin state
  const [siEmail, setSiEmail] = useState("");
  const [siPassword, setSiPassword] = useState("");

  // signup state
  const [suName, setSuName] = useState("");
  const [suEmail, setSuEmail] = useState("");
  const [suPassword, setSuPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!siEmail || !siPassword) {
      toast.error("Enter email and password");
      return;
    }
    setAuthLoading(true);
    try {
      await signIn(siEmail, siPassword);
      toast.success("Welcome back");
      navigate({ to: "/dashboard" });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Sign in failed");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!suName || !suEmail || suPassword.length < 6) {
      toast.error("Fill all fields — password ≥ 6 chars");
      return;
    }
    setAuthLoading(true);
    try {
      await signUp(suName, suEmail, suPassword);
      toast.success("Account created");
      navigate({ to: "/dashboard" });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Account creation failed");
    } finally {
      setAuthLoading(false);
    }
  };

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
      <div className="relative mx-auto grid min-h-screen max-w-6xl grid-cols-1 gap-10 px-5 py-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-center lg:gap-16 lg:py-16">
        {/* Left — editorial hero */}
        <div className="order-2 lg:order-1">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Aperture className="h-4 w-4 text-primary" />
            <span className="tracking-widest uppercase">Atelier</span>
          </div>
          <h1 className="mt-5 font-serif text-5xl leading-[1.05] tracking-tight text-foreground sm:text-6xl lg:text-7xl">
            Photos that <em className="text-clay not-italic">find</em> each other.
          </h1>
          <p className="mt-6 max-w-md text-base leading-relaxed text-muted-foreground">
            A quiet home for your image collection. Upload from your device or Drive,
            then rediscover any memory by showing us a single frame.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link to="/about" className="group inline-flex items-center gap-1 text-sm font-medium text-foreground">
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

        {/* Right — auth */}
        <div className="order-1 lg:order-2">
          <div className="relative overflow-hidden rounded-2xl border border-border/70 bg-card/95 p-6 shadow-editorial backdrop-blur-sm sm:p-8">
            <Tabs defaultValue="signin" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="signin">Sign in</TabsTrigger>
                <TabsTrigger value="signup">Create account</TabsTrigger>
              </TabsList>

              <TabsContent value="signin" className="mt-6">
                <form onSubmit={handleSignIn} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="si-email">Email</Label>
                    <Input id="si-email" type="email" autoComplete="email"
                      value={siEmail} onChange={(e) => setSiEmail(e.target.value)} placeholder="you@studio.com" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="si-password">Password</Label>
                    <Input id="si-password" type="password" autoComplete="current-password"
                      value={siPassword} onChange={(e) => setSiPassword(e.target.value)} placeholder="••••••••" />
                  </div>
                  <Button type="submit" className="w-full" disabled={authLoading}>Sign in</Button>
                </form>
              </TabsContent>

              <TabsContent value="signup" className="mt-6">
                <form onSubmit={handleSignUp} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="su-name">Name</Label>
                    <Input id="su-name" value={suName} onChange={(e) => setSuName(e.target.value)} placeholder="Ada Lovelace" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="su-email">Email</Label>
                    <Input id="su-email" type="email" value={suEmail} onChange={(e) => setSuEmail(e.target.value)} placeholder="you@studio.com" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="su-password">Password</Label>
                    <Input id="su-password" type="password" value={suPassword} onChange={(e) => setSuPassword(e.target.value)} placeholder="At least 6 characters" />
                  </div>
                  <Button type="submit" className="w-full" disabled={authLoading}>Create account</Button>
                </form>
              </TabsContent>
            </Tabs>

            <div className="relative my-6 flex items-center">
              <div className="flex-1 border-t border-border" />
              <span className="px-3 text-xs uppercase tracking-widest text-muted-foreground">or</span>
              <div className="flex-1 border-t border-border" />
            </div>

            <Button variant="outline" className="w-full" onClick={handleGoogle} disabled={authLoading}>
              <GoogleIcon />
              <span className="ml-2">Continue with Google</span>
            </Button>

            <p className="mt-6 text-center text-xs text-muted-foreground">
              By continuing you agree to our quiet terms of respectful use.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
