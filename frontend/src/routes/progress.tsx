import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Loader2 } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { RequireAuth } from "@/components/require-auth";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { getIngestionJob, type IngestionJobResponse } from "@/lib/api";
import { addPhotos, type StoredPhoto } from "@/lib/photo-store";

export const Route = createFileRoute("/progress")({
  head: () => ({
    meta: [
      { title: "Uploading - Atelier" },
      { name: "description", content: "Your photos are arriving." },
    ],
  }),
  component: ProgressPage,
});

type Pending = { id: string; name: string; dataUrl: string };

function ProgressPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [pending, setPending] = useState<Pending[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<IngestionJobResponse | null>(null);
  const [done, setDone] = useState(0);
  const [finished, setFinished] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const persistedRef = useRef(false);

  useEffect(() => {
    const storedJobId = sessionStorage.getItem("photovault.ingestionJobId");
    const rawPending = sessionStorage.getItem("photovault.pending");

    if (storedJobId) {
      setJobId(storedJobId);
      return;
    }

    if (!rawPending) {
      navigate({ to: "/dashboard" });
      return;
    }

    try {
      setPending(JSON.parse(rawPending) as Pending[]);
    } catch {
      navigate({ to: "/dashboard" });
    }
  }, [navigate]);

  useEffect(() => {
    if (!jobId || !user?.backendAccessToken || finished) return;

    let cancelled = false;
    const poll = async () => {
      try {
        const nextJob = await getIngestionJob(user.backendAccessToken!, jobId);
        if (cancelled) return;
        setJob(nextJob);
        if (["done", "completed", "failed"].includes(nextJob.status.toLowerCase())) {
          setFinished(true);
          sessionStorage.removeItem("photovault.ingestionJobId");
        }
      } catch (pollError) {
        if (!cancelled) {
          setError(pollError instanceof Error ? pollError.message : "Could not load ingestion status");
        }
      }
    };

    void poll();
    const intervalId = window.setInterval(poll, 2500);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [finished, jobId, user?.backendAccessToken]);

  useEffect(() => {
    if (jobId || !pending.length || done >= pending.length) return;
    const timeoutId = window.setTimeout(() => setDone((value) => value + 1), 500 + Math.random() * 400);
    return () => window.clearTimeout(timeoutId);
  }, [done, jobId, pending.length]);

  useEffect(() => {
    if (jobId || !pending.length || done < pending.length || persistedRef.current) return;

    persistedRef.current = true;
    const stored: StoredPhoto[] = pending.map((item) => ({
      id: item.id,
      name: item.name,
      dataUrl: item.dataUrl,
      uploadedAt: Date.now(),
    }));
    addPhotos(stored);
    sessionStorage.removeItem("photovault.pending");
    setFinished(true);
  }, [done, jobId, pending]);

  const isBackendJob = Boolean(jobId);
  const total = isBackendJob ? job?.total || 0 : pending.length;
  const processed = isBackendJob ? job?.processed || 0 : done;
  const pct = total ? Math.round((processed / total) * 100) : finished ? 100 : 0;
  const title = finished ? "All safely tucked in." : "Bringing them in, one by one.";

  return (
    <RequireAuth>
      <div className="min-h-screen bg-background">
        <SiteHeader />
        <main className="mx-auto max-w-2xl px-5 py-16 sm:py-24">
          <p className="text-xs uppercase tracking-[0.2em] text-ochre">
            {isBackendJob ? "Ingesting" : "Uploading"}
          </p>
          <h1 className="mt-2 font-serif text-4xl sm:text-5xl">{title}</h1>
          <p className="mt-3 text-muted-foreground">
            {isBackendJob
              ? "FastAPI is processing images from Google Drive."
              : finished
                ? "Your photos have arrived. You can now search by image."
                : "Preparing local photos for this browser session."}
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
                    {processed} / {total} {isBackendJob ? "processed" : "uploaded"}
                  </p>
                  <p className="text-xs uppercase tracking-widest text-muted-foreground">
                    {pct}% complete
                  </p>
                </div>
              </div>
            </div>

            <Progress value={pct} className="h-2" />

            {error && <p className="mt-4 text-sm text-destructive">{error}</p>}

            {job && (
              <div className="mt-6 grid grid-cols-2 gap-3 text-sm text-muted-foreground sm:grid-cols-4">
                <span>Status: {job.status}</span>
                <span>Total: {job.total}</span>
                <span>Failed: {job.failed}</span>
                <span>Type: {job.job_type}</span>
              </div>
            )}

            {!isBackendJob && (
              <div className="mt-8 grid grid-cols-4 gap-2 sm:grid-cols-6">
                {pending.map((item, index) => (
                  <div
                    key={item.id}
                    className={`relative aspect-square overflow-hidden rounded-md border border-border transition-opacity ${
                      index < done ? "opacity-100" : "opacity-30"
                    }`}
                  >
                    <img src={item.dataUrl} alt={item.name} className="h-full w-full object-cover" />
                    {index < done && (
                      <div className="absolute inset-0 flex items-center justify-center bg-primary/20">
                        <CheckCircle2 className="h-5 w-5 text-primary-foreground drop-shadow" />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
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
