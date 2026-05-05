import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Loader2 } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { RequireAuth } from "@/components/require-auth";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { addPhotos, type StoredPhoto } from "@/lib/photo-store";

export const Route = createFileRoute("/progress")({
  head: () => ({
    meta: [
      { title: "Uploading — Atelier" },
      { name: "description", content: "Your photos are arriving." },
    ],
  }),
  component: ProgressPage,
});

type Pending = { id: string; name: string; dataUrl: string };

function ProgressPage() {
  const navigate = useNavigate();
  const [pending, setPending] = useState<Pending[]>([]);
  const [done, setDone] = useState(0);
  const [finished, setFinished] = useState(false);
  const persistedRef = useRef(false);

  // Load pending queue from sessionStorage
  useEffect(() => {
    const raw = sessionStorage.getItem("photovault.pending");
    if (!raw) {
      navigate({ to: "/dashboard" });
      return;
    }
    try {
      const list = JSON.parse(raw) as Pending[];
      setPending(list);
    } catch {
      navigate({ to: "/dashboard" });
    }
  }, [navigate]);

  // Simulated upload progress — one image at a time
  useEffect(() => {
    if (!pending.length) return;
    if (done >= pending.length) return;
    const t = setTimeout(() => setDone((d) => d + 1), 500 + Math.random() * 400);
    return () => clearTimeout(t);
  }, [pending.length, done]);

  // When finished, persist photos to the mock store (once)
  useEffect(() => {
    if (pending.length && done >= pending.length && !persistedRef.current) {
      persistedRef.current = true;
      const stored: StoredPhoto[] = pending.map((p) => ({
        id: p.id,
        name: p.name,
        dataUrl: p.dataUrl,
        uploadedAt: Date.now(),
      }));
      addPhotos(stored);
      sessionStorage.removeItem("photovault.pending");
      setFinished(true);
    }
  }, [done, pending]);

  const total = pending.length;
  const pct = total ? Math.round((done / total) * 100) : 0;

  return (
    <RequireAuth>
      <div className="min-h-screen bg-background">
        <SiteHeader />
        <main className="mx-auto max-w-2xl px-5 py-16 sm:py-24">
          <p className="text-xs uppercase tracking-[0.2em] text-ochre">Uploading</p>
          <h1 className="mt-2 font-serif text-4xl sm:text-5xl">
            {finished ? "All safely tucked in." : "Bringing them in, one by one."}
          </h1>
          <p className="mt-3 text-muted-foreground">
            {finished
              ? "Your photos have arrived. You can now search by image."
              : "This would stream to your backend in production."}
          </p>

          <div className="mt-10 rounded-2xl border border-border bg-paper p-8 shadow-soft">
            <div className="mb-6 flex items-center justify-between">
              <div className="flex items-center gap-3">
                {finished ? (
                  <CheckCircle2 className="h-6 w-6 text-primary" />
                ) : (
                  <Loader2 className="h-6 w-6 animate-spin text-primary" />
                )}
                <div>
                  <p className="font-serif text-xl">
                    {done} / {total} uploaded
                  </p>
                  <p className="text-xs uppercase tracking-widest text-muted-foreground">
                    {pct}% complete
                  </p>
                </div>
              </div>
            </div>

            <Progress value={pct} className="h-2" />

            <div className="mt-8 grid grid-cols-4 gap-2 sm:grid-cols-6">
              {pending.map((p, i) => (
                <div
                  key={p.id}
                  className={`relative aspect-square overflow-hidden rounded-md border border-border transition-opacity ${
                    i < done ? "opacity-100" : "opacity-30"
                  }`}
                >
                  <img src={p.dataUrl} alt={p.name} className="h-full w-full object-cover" />
                  {i < done && (
                    <div className="absolute inset-0 flex items-center justify-center bg-primary/20">
                      <CheckCircle2 className="h-5 w-5 text-primary-foreground drop-shadow" />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {finished && (
            <div className="mt-8 flex flex-wrap gap-3">
              <Button asChild size="lg">
                <Link to="/query">Find by photo</Link>
              </Button>
              <Button asChild variant="outline" size="lg">
                <Link to="/dashboard">Upload more</Link>
              </Button>
            </div>
          )}
        </main>
      </div>
    </RequireAuth>
  );
}
