import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";
import {
  Aperture,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  BrainCircuit,
  Cloud,
  Database,
  FolderInput,
  Github,
  Heart,
  Images,
  Mail,
  Search,
  Server,
  ShieldCheck,
  Users,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import { SiteHeader } from "@/components/site-header";

export const Route = createFileRoute("/about")({
  head: () => ({
    meta: [
      { title: "About — FaceSeek" },
      {
        name: "description",
        content: "The mission, architecture, and technology behind FaceSeek.",
      },
      { property: "og:title", content: "About — FaceSeek" },
      {
        property: "og:description",
        content: "See how FaceSeek turns photos into a private, searchable face index.",
      },
    ],
  }),
  component: AboutPage,
});

type FlowName = "ingestion" | "search";

type FlowStep = {
  title: string;
  detail: string;
  icon: LucideIcon;
};

const flows: Record<FlowName, FlowStep[]> = {
  ingestion: [
    {
      title: "Choose a folder",
      detail: "React sends an authenticated Drive folder request to FastAPI.",
      icon: FolderInput,
    },
    {
      title: "Run the job",
      detail: "A background task or Celery worker downloads each image safely.",
      icon: Workflow,
    },
    {
      title: "Understand faces",
      detail: "InsightFace detects face boxes and creates 512-value embeddings.",
      icon: BrainCircuit,
    },
    {
      title: "Persist by purpose",
      detail: "Metadata, vectors, and image bytes go to their specialized stores.",
      icon: Database,
    },
  ],
  search: [
    {
      title: "Submit a face",
      detail: "The browser sends a query image to the protected search endpoint.",
      icon: Search,
    },
    {
      title: "Create a vector",
      detail: "FastAPI validates the image and InsightFace extracts its strongest face.",
      icon: BrainCircuit,
    },
    {
      title: "Find neighbors",
      detail: "Qdrant compares embeddings inside the current user's boundary.",
      icon: Aperture,
    },
    {
      title: "Return photos",
      detail: "Postgres resolves identities and signed storage URLs reach the UI.",
      icon: Images,
    },
  ],
};

function SystemNode({
  icon: Icon,
  title,
  subtitle,
  active = false,
}: {
  icon: LucideIcon;
  title: string;
  subtitle: string;
  active?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-4 transition-colors ${
        active ? "border-primary bg-primary/10" : "border-border bg-background/75"
      }`}
    >
      <div className="flex items-center gap-2">
        <Icon className={`h-4 w-4 ${active ? "text-primary" : "text-clay"}`} aria-hidden />
        <p className="text-sm font-medium">{title}</p>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{subtitle}</p>
    </div>
  );
}

function Layer({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-3 md:grid-cols-[8rem_1fr] md:items-center">
      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <div>{children}</div>
    </div>
  );
}

function ArchitectureMap() {
  const [activeFlow, setActiveFlow] = useState<FlowName>("ingestion");
  const isIngestion = activeFlow === "ingestion";

  return (
    <section className="mt-20" aria-labelledby="architecture-heading">
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-ochre">High-level design</p>
          <h2 id="architecture-heading" className="mt-2 font-serif text-4xl sm:text-5xl">
            One product, three kinds of memory.
          </h2>
          <p className="mt-3 max-w-2xl leading-relaxed text-muted-foreground">
            The API coordinates relational state, vector similarity, and private image storage.
            Choose a path to see how data moves through the system.
          </p>
        </div>

        <div
          className="inline-flex w-fit rounded-xl border border-border bg-paper p-1"
          role="group"
          aria-label="Architecture flow"
        >
          {(["ingestion", "search"] as const).map((flow) => (
            <button
              key={flow}
              type="button"
              aria-pressed={activeFlow === flow}
              onClick={() => setActiveFlow(flow)}
              className={`rounded-lg px-4 py-2 text-sm font-medium capitalize transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                activeFlow === flow
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {flow}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-8 overflow-hidden rounded-3xl border border-border bg-paper p-5 shadow-editorial sm:p-8">
        <div className="space-y-4">
          <Layer label="Experience">
            <div className="grid gap-3 md:grid-cols-2">
              <SystemNode
                icon={Users}
                title="React + TanStack"
                subtitle="Routes, accessible interactions, uploads, progress, and ranked results."
                active
              />
              <SystemNode
                icon={Cloud}
                title="Google Drive"
                subtitle="The source library enumerated during folder ingestion."
                active={isIngestion}
              />
            </div>
          </Layer>

          <div className="flex justify-center md:pl-32" aria-hidden>
            <ArrowDown className="h-5 w-5 text-ochre" />
          </div>

          <Layer label="Application">
            <div className="grid gap-3 md:grid-cols-3">
              <SystemNode
                icon={Server}
                title="FastAPI"
                subtitle="Authentication, validation, ownership checks, and stable HTTP contracts."
                active
              />
              <SystemNode
                icon={Workflow}
                title="Background / Celery"
                subtitle="Durable production work and behaviorally equivalent local execution."
                active={isIngestion}
              />
              <SystemNode
                icon={BrainCircuit}
                title="InsightFace"
                subtitle="Face detection and embeddings shared by ingestion and search."
                active
              />
            </div>
          </Layer>

          <div className="flex justify-center md:pl-32" aria-hidden>
            <ArrowDown className="h-5 w-5 text-ochre" />
          </div>

          <Layer label="Persistence">
            <div className="rounded-2xl border border-primary/30 bg-primary/5 p-3">
              <div className="mb-3 flex items-center gap-2 px-1 text-xs font-medium text-primary">
                <ShieldCheck className="h-4 w-4" aria-hidden />
                User-scoped data boundary
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <SystemNode
                  icon={Database}
                  title="PostgreSQL"
                  subtitle="Users, folders, jobs, image metadata, faces, and search history."
                  active={!isIngestion}
                />
                <SystemNode
                  icon={Aperture}
                  title="Qdrant"
                  subtitle="One searchable vector per face, filtered by user before ranking."
                  active
                />
                <SystemNode
                  icon={Images}
                  title="Supabase Storage"
                  subtitle="Private originals served through short-lived signed URLs."
                  active={isIngestion}
                />
              </div>
            </div>
          </Layer>
        </div>
      </div>

      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-live="polite">
        {flows[activeFlow].map((step, index) => {
          const Icon = step.icon;
          return (
            <div
              key={step.title}
              className="relative rounded-2xl border border-border bg-paper p-5 shadow-soft"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs tracking-[0.16em] text-ochre">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <Icon className="h-4 w-4 text-clay" aria-hidden />
              </div>
              <h3 className="mt-4 font-serif text-xl">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.detail}</p>
              {index < flows[activeFlow].length - 1 && (
                <ArrowRight
                  className="absolute -right-2 top-1/2 z-10 hidden h-4 w-4 -translate-y-1/2 text-ochre lg:block"
                  aria-hidden
                />
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function AboutPage() {
  return (
    <div className="min-h-screen bg-background">
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-5 py-12 sm:py-20">
        <div className="max-w-3xl">
          <p className="text-xs uppercase tracking-[0.2em] text-ochre">About</p>
          <h1 className="mt-3 font-serif text-5xl leading-tight tracking-tight sm:text-6xl">
            A slower place for the photos that matter.
          </h1>
          <p className="mt-8 text-lg leading-relaxed text-muted-foreground">
            FaceSeek is a quiet photo archive built on the belief that images deserve more than an
            endless feed. We help you collect, keep, and rediscover your pictures—not perform them.
          </p>
        </div>

        <section className="mt-14 grid gap-8 md:grid-cols-3">
          {[
            {
              icon: Aperture,
              title: "Purpose",
              body: "Turn a photo collection into a searchable visual memory without relying on filenames or dates.",
            },
            {
              icon: Heart,
              title: "Mission",
              body: "Make looking back feel like flipping through an album—warm, deliberate, and easy to rediscover.",
            },
            {
              icon: Users,
              title: "Platform",
              body: "A React experience backed by modular Python services, durable jobs, and purpose-built data stores.",
            },
          ].map(({ icon: Icon, title, body }) => (
            <article
              key={title}
              className="rounded-2xl border border-border bg-paper p-6 shadow-soft"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                <Icon className="h-5 w-5" aria-hidden />
              </div>
              <h2 className="mt-5 font-serif text-2xl">{title}</h2>
              <p className="mt-2 leading-relaxed text-muted-foreground">{body}</p>
            </article>
          ))}
        </section>

        <ArchitectureMap />

        <div className="mt-16 rounded-2xl border border-border bg-paper p-8 shadow-soft">
          <p className="font-serif text-2xl leading-snug">
            &ldquo;Every picture is a time machine. We just built the doorbell.&rdquo;
          </p>
          <p className="mt-3 text-sm text-muted-foreground">— FaceSeek</p>
        </div>

        <section className="mt-8 rounded-2xl border border-border bg-paper p-8 shadow-soft">
          <p className="text-xs uppercase tracking-[0.2em] text-ochre">Creator</p>
          <h2 className="mt-3 font-serif text-3xl">Built by IENVYshanks</h2>
          <p className="mt-3 max-w-2xl leading-relaxed text-muted-foreground">
            FaceSeek is an open-source project exploring private, useful face-similarity search
            across personal photo collections.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <a
              href="https://github.com/IENVYshanks"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
            >
              <Github className="h-4 w-4" aria-hidden /> GitHub
            </a>
            <a
              href="mailto:sawaiyanronit12@gmail.com"
              className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
            >
              <Mail className="h-4 w-4" aria-hidden /> Contact
            </a>
          </div>
        </section>

        <div className="mt-12">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-sm font-medium text-primary underline-offset-4 hover:underline"
          >
            <ArrowLeft className="h-4 w-4" /> Back home
          </Link>
        </div>
      </main>
    </div>
  );
}
