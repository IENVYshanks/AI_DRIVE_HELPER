import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { toast } from "sonner";
import {
  ArrowLeft,
  ChevronRight,
  Folder,
  FolderOpen,
  HardDrive,
  Loader2,
  Upload,
  X,
} from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAuth } from "@/hooks/use-auth";
import {
  browseDriveFolders,
  startFolderIngestion,
  upsertDriveFolder,
  type DriveFolderItemResponse,
  type IngestionJobResponse,
} from "@/lib/api";
import { fileToDataUrl } from "@/lib/photo-store";

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Upload — FaceSeek" },
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
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerLoading, setPickerLoading] = useState(false);
  const [pickerError, setPickerError] = useState<string | null>(null);
  const [pickerCurrent, setPickerCurrent] = useState<DriveFolderItemResponse | null>(null);
  const [pickerFolders, setPickerFolders] = useState<DriveFolderItemResponse[]>([]);
  const [pickerPath, setPickerPath] = useState<DriveFolderItemResponse[]>([]);

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

  const loadDriveLocation = async (
    folderId: string,
    pathBeforeFolder: DriveFolderItemResponse[],
  ) => {
    setPickerLoading(true);
    setPickerError(null);
    try {
      const response = await browseDriveFolders(folderId);
      setPickerCurrent(response.current);
      setPickerFolders(response.folders);
      setPickerPath([...pathBeforeFolder, response.current]);
    } catch (error) {
      setPickerError(error instanceof Error ? error.message : "Could not load Drive folders");
    } finally {
      setPickerLoading(false);
    }
  };

  const handlePickerOpenChange = (open: boolean) => {
    setPickerOpen(open);
    if (open) void loadDriveLocation("root", []);
  };

  const chooseCurrentDriveFolder = () => {
    if (!pickerCurrent) return;
    setDriveFolderId(pickerCurrent.id);
    setDriveFolderName(pickerCurrent.name);
    setPickerOpen(false);
    toast.success(`${pickerCurrent.name} selected`);
  };

  const handleDriveIngestion = async () => {
    const folderId = driveFolderId.trim();
    if (!folderId) {
      toast.error("Enter a Google Drive folder ID");
      return;
    }
    if (!user) {
      toast.error("Sign in with Google before starting Drive ingestion");
      return;
    }

    setDriveLoading(true);
    try {
      const folder = await upsertDriveFolder(folderId, driveFolderName.trim() || undefined);
      const job = await startFolderIngestion(folder.id);
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
        <main className="mx-auto max-w-6xl px-5 py-10 sm:px-8 sm:py-16">
          <div className="mb-10">
            <p className="text-xs uppercase tracking-[0.2em] text-ochre">Upload</p>
            <h1 className="mt-2 max-w-[12ch] font-serif text-6xl leading-[0.95] sm:text-8xl">
              Bring your photos home.
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-muted-foreground">
              Drop images below, or pull them in from Google Drive. The Drive path is connected to
              the FastAPI backend.
            </p>
          </div>

          <section className="mb-8 border-t-2 border-foreground bg-paper p-6 shadow-soft">
            <div className="flex items-start gap-3">
              <HardDrive className="mt-1 h-5 w-5 text-primary" />
              <div>
                <p className="font-serif text-xl">Google Drive ingestion</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Browse your Drive or paste a folder ID. The backend securely loads images from the
                  folder you choose.
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
            <Button
              type="button"
              variant="outline"
              className="mt-4"
              onClick={() => handlePickerOpenChange(true)}
            >
              <FolderOpen className="mr-2 h-4 w-4" />
              Browse Google Drive
            </Button>
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
            className={`relative overflow-hidden border-2 border-dashed p-10 text-center transition-all ${
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
                <Button variant="outline" onClick={() => handlePickerOpenChange(true)}>
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
                  <div
                    key={index}
                    className="group relative aspect-square overflow-hidden rounded-lg border border-border shadow-soft"
                  >
                    <img
                      src={item.previewUrl}
                      alt={item.file.name}
                      className="h-full w-full object-cover"
                      loading="lazy"
                    />
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

        <Dialog open={pickerOpen} onOpenChange={handlePickerOpenChange}>
          <DialogContent className="max-w-2xl overflow-hidden border-border/80 bg-paper p-0 shadow-editorial backdrop-blur-2xl">
            <DialogHeader className="border-b border-border/70 px-6 py-5 pr-12">
              <DialogTitle className="flex items-center gap-2 font-serif text-2xl">
                <HardDrive className="h-5 w-5 text-primary" />
                Choose a Drive folder
              </DialogTitle>
              <DialogDescription>
                Navigate your Google Drive and select the folder whose photos you want to ingest.
              </DialogDescription>
            </DialogHeader>

            <div className="px-6 pt-4">
              <div className="flex min-h-9 items-center gap-1 overflow-x-auto text-sm">
                {pickerPath.length > 1 && (
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Go back"
                    onClick={() => {
                      const targetIndex = pickerPath.length - 2;
                      const target = pickerPath[targetIndex];
                      void loadDriveLocation(target.id, pickerPath.slice(0, targetIndex));
                    }}
                  >
                    <ArrowLeft className="h-4 w-4" />
                  </Button>
                )}
                {pickerPath.map((folder, index) => (
                  <div key={folder.id} className="flex shrink-0 items-center gap-1">
                    {index > 0 && <ChevronRight className="h-4 w-4 text-muted-foreground" />}
                    <button
                      type="button"
                      className="rounded-md px-2 py-1 text-muted-foreground transition-colors hover:bg-primary/10 hover:text-foreground disabled:text-foreground"
                      disabled={index === pickerPath.length - 1}
                      onClick={() => void loadDriveLocation(folder.id, pickerPath.slice(0, index))}
                    >
                      {folder.name}
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div className="min-h-72 px-6 py-4">
              {pickerLoading ? (
                <div className="flex h-64 flex-col items-center justify-center gap-3 text-muted-foreground">
                  <Loader2 className="h-7 w-7 animate-spin text-primary" />
                  <span className="text-sm">Loading Drive folders...</span>
                </div>
              ) : pickerError ? (
                <div className="flex h-64 flex-col items-center justify-center gap-4 text-center">
                  <p className="max-w-sm text-sm text-destructive">{pickerError}</p>
                  <Button
                    variant="outline"
                    onClick={() =>
                      void loadDriveLocation(pickerCurrent?.id || "root", pickerPath.slice(0, -1))
                    }
                  >
                    Try again
                  </Button>
                </div>
              ) : pickerFolders.length ? (
                <div className="grid max-h-72 grid-cols-1 gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
                  {pickerFolders.map((folder) => (
                    <button
                      key={folder.id}
                      type="button"
                      className="group flex items-center gap-3 rounded-xl border border-border/70 bg-background/25 p-3 text-left transition-all hover:-translate-y-0.5 hover:border-primary/60 hover:bg-primary/10 hover:shadow-soft"
                      onClick={() => void loadDriveLocation(folder.id, pickerPath)}
                    >
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/15 text-primary">
                        <Folder className="h-5 w-5" />
                      </span>
                      <span className="min-w-0 flex-1 truncate text-sm font-medium">
                        {folder.name}
                      </span>
                      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                    </button>
                  ))}
                </div>
              ) : (
                <div className="flex h-64 flex-col items-center justify-center gap-3 text-center text-muted-foreground">
                  <FolderOpen className="h-9 w-9 text-primary" />
                  <div>
                    <p className="text-sm font-medium text-foreground">No folders inside</p>
                    <p className="mt-1 text-xs">You can still choose this folder for ingestion.</p>
                  </div>
                </div>
              )}
            </div>

            <DialogFooter className="border-t border-border/70 bg-background/20 px-6 py-4 sm:items-center sm:justify-between">
              <p className="truncate text-xs text-muted-foreground">
                Selecting: {pickerCurrent?.name || "My Drive"}
              </p>
              <Button onClick={chooseCurrentDriveFolder} disabled={pickerLoading || !pickerCurrent}>
                Choose this folder
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </RequireAuth>
  );
}
