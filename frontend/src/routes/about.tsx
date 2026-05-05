import { createFileRoute, Link } from "@tanstack/react-router";
import { SiteHeader } from "@/components/site-header";
import { Aperture, Heart, Users } from "lucide-react";

export const Route = createFileRoute("/about")({
  head: () => ({
    meta: [
      { title: "About — Atelier" },
      { name: "description", content: "The mission, motivation, and people behind Atelier." },
      { property: "og:title", content: "About — Atelier" },
      { property: "og:description", content: "The mission, motivation, and people behind Atelier." },
    ],
  }),
  component: AboutPage,
});

function AboutPage() {
  return (
    <div className="min-h-screen bg-background">
      <SiteHeader />
      <main className="mx-auto max-w-3xl px-5 py-16 sm:py-24">
        <p className="text-xs uppercase tracking-[0.2em] text-ochre">About</p>
        <h1 className="mt-3 font-serif text-5xl leading-tight tracking-tight sm:text-6xl">
          A slower place for the photos that matter.
        </h1>
        <p className="mt-8 text-lg leading-relaxed text-muted-foreground">
          Atelier is a quiet photo archive built on the belief that images deserve
          more than an endless feed. We help you collect, keep, and rediscover your
          pictures — not perform them.
        </p>

        <section className="mt-14 space-y-10">
          <div className="flex gap-5">
            <div className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Aperture className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-serif text-2xl">Purpose</h2>
              <p className="mt-2 leading-relaxed text-muted-foreground">
                Upload images from your device or Google Drive, track their arrival in
                real time, and later find any memory by simply showing us a single
                photograph — the service locates the visually similar ones.
              </p>
            </div>
          </div>

          <div className="flex gap-5">
            <div className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Heart className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-serif text-2xl">Mission &amp; motivation</h2>
              <p className="mt-2 leading-relaxed text-muted-foreground">
                Too many photos disappear into folders nobody re-opens. We wanted a
                tool that makes looking back feel like flipping through an album —
                warm, slow, and searchable by the way a thing looks, not just the
                date it was taken.
              </p>
            </div>
          </div>

          <div className="flex gap-5">
            <div className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Users className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-serif text-2xl">The platform</h2>
              <p className="mt-2 leading-relaxed text-muted-foreground">
                Built as a full-stack project with a React frontend and a modular
                backend (authentication, storage, and an image similarity query API).
                Designed and maintained by a small team that cares about craft.
              </p>
            </div>
          </div>
        </section>

        <div className="mt-16 rounded-2xl border border-border bg-paper p-8 shadow-soft">
          <p className="font-serif text-2xl leading-snug">
            &ldquo;Every picture is a time machine. We just built the doorbell.&rdquo;
          </p>
          <p className="mt-3 text-sm text-muted-foreground">— The Atelier team</p>
        </div>

        <div className="mt-12">
          <Link to="/" className="text-sm font-medium text-primary underline-offset-4 hover:underline">
            ← Back to sign in
          </Link>
        </div>
      </main>
    </div>
  );
}
