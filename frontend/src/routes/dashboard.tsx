import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { Upload, HardDrive, FolderOpen, X } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { fileToDataUrl } from "@/lib/photo-store";

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Upload — Atelier" },
      { name: "description", content: "Upload photos from your device or Google Drive." },
    ],
  }),
  component: DashboardPage,
});

type PendingFile = { file: File; previewUrl: string };

function DashboardPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<PendingFile[]>([]);
  const [dragOver, setDragOver] = useState(false);

  const addFiles = (list: FileList | File[]) => {
    const incoming = Array.from(list).filter((f) => f.type.startsWith("image/"));
    if (!incoming.length) {
      toast.error("Please choose image files");
      return;
    }
    const mapped = incoming.map((file) => ({ file, previewUrl: URL.createObjectURL(file) }));
    setFiles((prev) => [...prev, ...mapped]);
  };

  const removeAt = (i: number) => {
    setFiles((prev) => {
      const next = [...prev];
      URL.revokeObjectURL(next[i].previewUrl);
      next.splice(i, 1);
      return next;
    });
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
  };

  const handleGoogleDrive = () => {
    // Mock: real implementation would use Google Picker API.
    toast.info("Google Drive picker — wire up Google API on your MERN backend.");
  };

  const handleSubmit = async () => {
    if (!files.length) {
      toast.error("Select at least one photo");
      return;
    }
    // Convert to data URLs so the progress page can persist them client-side.
    const prepared = await Promise.all(
      files.map(async (p) => ({
        id: crypto.randomUUID(),
        name: p.file.name,
        dataUrl: await fileToDataUrl(p.file),
      }))
    );
    sessionStorage.setItem("photovault.pending", JSON.stringify(prepared));
    navigate({ to: "/progress" });
  };

  return (
    <RequireAuth>
      <div className="min-h-screen bg-background">
        <SiteHeader />
        <main className="mx-auto max-w-4xl px-5 py-10 sm:py-16">
          <div className="mb-10">
            <p className="text-xs uppercase tracking-[0.2em] text-ochre">Upload</p>
            <h1 className="mt-2 font-serif text-4xl sm:text-5xl">Bring your photos home.</h1>
            <p className="mt-3 max-w-xl text-muted-foreground">
              Drop images below, or pull them in from Google Drive. We'll process them
              one by one on the next screen.
            </p>
          </div>

          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={`relative overflow-hidden rounded-2xl border-2 border-dashed p-10 text-center transition-all ${
              dragOver ? "border-primary bg-primary/5" : "border-border bg-paper"
            }`}
          >
            <div className="flex flex-col items-center gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-gradient-sunset text-primary-foreground shadow-soft">
                <Upload className="h-7 w-7" />
              </div>
              <div>
                <p className="font-serif text-2xl">Drag photos here</p>
                <p className="mt-1 text-sm text-muted-foreground">or pick a source below</p>
              </div>
              <div className="mt-2 flex flex-wrap justify-center gap-3">
                <Button onClick={() => inputRef.current?.click()}>
                  <FolderOpen className="mr-2 h-4 w-4" />
                  From this device
                </Button>
                <Button variant="outline" onClick={handleGoogleDrive}>
                  <HardDrive className="mr-2 h-4 w-4" />
                  From Google Drive
                </Button>
                <input
                  ref={inputRef}
                  type="file"
                  multiple
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => e.target.files && addFiles(e.target.files)}
                />
              </div>
            </div>
          </div>

          {files.length > 0 && (
            <section className="mt-10">
              <div className="mb-4 flex items-center justify-between">
                <p className="font-serif text-xl">
                  {files.length} {files.length === 1 ? "photo" : "photos"} selected
                </p>
                <Button size="lg" onClick={handleSubmit}>
                  Submit &amp; upload
                </Button>
              </div>
              <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6">
                {files.map((f, i) => (
                  <div key={i} className="group relative aspect-square overflow-hidden rounded-lg border border-border shadow-soft">
                    <img src={f.previewUrl} alt={f.file.name} className="h-full w-full object-cover" loading="lazy" />
                    <button
                      onClick={() => removeAt(i)}
                      aria-label="Remove"
                      className="absolute right-1.5 top-1.5 rounded-full bg-background/90 p-1 opacity-0 shadow-soft transition-opacity group-hover:opacity-100 focus:opacity-100"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </section>
          )}
        </main>
      </div>
    </RequireAuth>
  );
}
