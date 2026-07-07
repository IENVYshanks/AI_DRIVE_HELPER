import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { Upload, HardDrive, FolderOpen, X } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/use-auth";
import {
  startFolderIngestion,
  upsertDriveFolder,
  type IngestionJobResponse,
} from "@/lib/api";
import { fileToDataUrl } from "@/lib/photo-store";

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Upload - Atelier" },
      { name: "description", content: "Upload photos from your device or Google Drive." },
    ],
  }),
  component: DashboardPage,
});

type PendingFile = { file: File; previewUrl: string };

function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<PendingFile[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [driveFolderId, setDriveFolderId] = useState("");
  const [driveFolderName, setDriveFolderName] = useState("");
  const [driveJob, setDriveJob] = useState<IngestionJobResponse | null>(null);
  const [driveLoading, setDriveLoading] = useState(false);

  const addFiles = (list: FileList | File[]) => {
    const incoming = Array.from(list).filter((file) => file.type.startsWith("image/"));
    if (!incoming.length) {
      toast.error("Please choose image files");
      return;
    }
    const mapped = incoming.map((file) => ({ file, previewUrl: URL.createObjectURL(file) }));
    setFiles((prev) => [...prev, ...mapped]);
  };

  const removeAt = (index: number) => {
    setFiles((prev) => {
      const next = [...prev];
      URL.revokeObjectURL(next[index].previewUrl);
      next.splice(index, 1);
      return next;
    });
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    setDragOver(false);
    if (event.dataTransfer.files?.length) addFiles(event.dataTransfer.files);
  };

  const handleGoogleDrive = () => {
    folderInputRef.current?.focus();
  };

  const handleDriveIngestion = async () => {
    const folderId = driveFolderId.trim();
    if (!folderId) {
      toast.error("Enter a Google Drive folder ID");
      return;
    }
    if (!user?.backendAccessToken) {
      toast.error("Sign in with Google before starting Drive ingestion");
      return;
    }

    setDriveLoading(true);
    try {
      const folder = await upsertDriveFolder(
        user.backendAccessToken,
        folderId,
        driveFolderName.trim() || undefined,
      );
      const job = await startFolderIngestion(user.backendAccessToken, folder.id);
      setDriveJob(job);
      sessionStorage.setItem("photovault.ingestionJobId", job.id);
      toast.success("Drive ingestion started");
      navigate({ to: "/progress" });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not start Drive ingestion");
    } finally {
      setDriveLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!files.length) {
      toast.error("Select at least one photo");
      return;
    }
    const prepared = await Promise.all(
      files.map(async (item) => ({
        id: crypto.randomUUID(),
        name: item.file.name,
        dataUrl: await fileToDataUrl(item.file),
      })),
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
              Drop images below, or pull them in from Google Drive. The Drive path is connected to the FastAPI backend.
            </p>
          </div>

          <section className="mb-8 rounded-2xl border border-border bg-paper p-6 shadow-soft">
            <div className="flex items-start gap-3">
              <HardDrive className="mt-1 h-5 w-5 text-primary" />
              <div>
                <p className="font-serif text-xl">Google Drive ingestion</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Paste a Drive folder ID. The backend uses your Google token to ingest image files from that folder.
                </p>
              </div>
            </div>
            <div className="mt-5 grid gap-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
              <div className="space-y-2">
                <Label htmlFor="drive-folder-id">Folder ID</Label>
                <Input
                  ref={folderInputRef}
                  id="drive-folder-id"
                  value={driveFolderId}
                  onChange={(event) => setDriveFolderId(event.target.value)}
                  placeholder="Google Drive folder ID"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="drive-folder-name">Folder name</Label>
                <Input
                  id="drive-folder-name"
                  value={driveFolderName}
                  onChange={(event) => setDriveFolderName(event.target.value)}
                  placeholder="Optional"
                />
              </div>
              <Button onClick={handleDriveIngestion} disabled={driveLoading}>
                Start ingestion
              </Button>
            </div>
            {driveJob && (
              <p className="mt-4 text-sm text-muted-foreground">
                Job {driveJob.id} started with status {driveJob.status}.
              </p>
            )}
          </section>

          <div
            onDragOver={(event) => {
              event.preventDefault();
              setDragOver(true);
            }}
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
                  onChange={(event) => event.target.files && addFiles(event.target.files)}
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
                {files.map((item, index) => (
                  <div key={index} className="group relative aspect-square overflow-hidden rounded-lg border border-border shadow-soft">
                    <img src={item.previewUrl} alt={item.file.name} className="h-full w-full object-cover" loading="lazy" />
                    <button
                      onClick={() => removeAt(index)}
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
