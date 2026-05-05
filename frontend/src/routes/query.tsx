import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { QRCodeCanvas } from "qrcode.react";
import { toast } from "sonner";
import { Share2, Camera, ImagePlus, Copy, Sparkles } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { RequireAuth } from "@/components/require-auth";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { fileToDataUrl, getPhotos, type StoredPhoto } from "@/lib/photo-store";

export const Route = createFileRoute("/query")({
  head: () => ({
    meta: [
      { title: "Find by photo — Atelier" },
      { name: "description", content: "Show us a photo, find the ones that look like it." },
    ],
  }),
  component: QueryPage,
});

function QueryPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [queryImage, setQueryImage] = useState<string | null>(null);
  const [count, setCount] = useState<number>(6);
  const [results, setResults] = useState<StoredPhoto[] | null>(null);
  const [library, setLibrary] = useState<StoredPhoto[]>([]);
  const [shareOpen, setShareOpen] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [shareUrl, setShareUrl] = useState("");

  useEffect(() => {
    setLibrary(getPhotos());
    if (typeof window !== "undefined") setShareUrl(window.location.href);
  }, []);

  const handlePick = async (file: File) => {
    const url = await fileToDataUrl(file);
    setQueryImage(url);
    setResults(null);
  };

  const startCamera = async () => {
    setCameraOpen(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch {
      toast.error("Camera not available");
      setCameraOpen(false);
    }
  };

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setCameraOpen(false);
  };

  const captureFrame = () => {
    const video = videoRef.current;
    if (!video) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
    setQueryImage(dataUrl);
    setResults(null);
    stopCamera();
  };

  useEffect(() => () => stopCamera(), []);

  const runSearch = () => {
    if (!queryImage) {
      toast.error("Add a photo first");
      return;
    }
    if (!library.length) {
      toast.error("Upload some photos first");
      return;
    }
    // Mock similarity: shuffled subset. Real backend returns vector-similar results.
    const shuffled = [...library].sort(() => Math.random() - 0.5);
    setResults(shuffled.slice(0, Math.min(count, shuffled.length)));
  };

  const copyShare = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      toast.success("Link copied");
    } catch {
      toast.error("Copy failed");
    }
  };

  return (
    <RequireAuth>
      <div className="min-h-screen bg-background">
        <SiteHeader />
        <main className="mx-auto max-w-5xl px-5 py-10 sm:py-14">
          <div className="mb-8 flex items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-ochre">Find by photo</p>
              <h1 className="mt-2 font-serif text-4xl sm:text-5xl">Show us a frame.</h1>
              <p className="mt-2 text-muted-foreground">We'll find the ones that look like it.</p>
            </div>

            <Dialog open={shareOpen} onOpenChange={setShareOpen}>
              <DialogTrigger asChild>
                <Button variant="outline">
                  <Share2 className="mr-2 h-4 w-4" />
                  Share
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle className="font-serif">Share this page</DialogTitle>
                  <DialogDescription>
                    Scan the QR code or copy the link.
                  </DialogDescription>
                </DialogHeader>
                <div className="flex flex-col items-center gap-4 py-2">
                  <div className="rounded-lg border border-border bg-background p-4 shadow-soft">
                    <QRCodeCanvas value={shareUrl || "https://example.com"} size={176} />
                  </div>
                  <div className="flex w-full items-center gap-2 rounded-md border border-border bg-paper p-2">
                    <span className="truncate text-sm text-muted-foreground">{shareUrl}</span>
                    <Button size="sm" variant="ghost" onClick={copyShare}>
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          {/* Upload / preview */}
          <section className="grid gap-6 md:grid-cols-[1fr_1fr]">
            <div className="rounded-2xl border border-border bg-paper p-6 shadow-soft">
              <p className="font-serif text-xl">Your query image</p>
              <div className="mt-4 aspect-square overflow-hidden rounded-xl border border-border bg-background">
                {queryImage ? (
                  <img src={queryImage} alt="Query" className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                    No photo yet
                  </div>
                )}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => fileInputRef.current?.click()}>
                  <ImagePlus className="mr-2 h-4 w-4" />
                  Upload
                </Button>
                <Button variant="outline" onClick={startCamera}>
                  <Camera className="mr-2 h-4 w-4" />
                  Camera
                </Button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && handlePick(e.target.files[0])}
                />
                <input
                  ref={cameraInputRef}
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="hidden"
                />
              </div>
            </div>

            <div className="rounded-2xl border border-border bg-paper p-6 shadow-soft">
              <p className="font-serif text-xl">How many results?</p>
              <p className="mt-1 text-sm text-muted-foreground">Between 1 and 24 photos.</p>
              <div className="mt-6 flex items-baseline gap-3">
                <span className="font-serif text-5xl text-clay">{count}</span>
                <span className="text-sm text-muted-foreground">photos</span>
              </div>
              <div className="mt-4">
                <Slider
                  value={[count]}
                  min={1}
                  max={24}
                  step={1}
                  onValueChange={(v) => setCount(v[0])}
                />
              </div>
              <Button size="lg" className="mt-8 w-full" onClick={runSearch}>
                <Sparkles className="mr-2 h-4 w-4" />
                Find similar
              </Button>
              <p className="mt-3 text-center text-xs text-muted-foreground">
                Wire your MERN backend's similarity API into <code className="text-foreground">runSearch()</code>.
              </p>
            </div>
          </section>

          {/* Results */}
          {results && (
            <section className="mt-12">
              <div className="mb-4 flex items-end justify-between">
                <h2 className="font-serif text-2xl">Matches</h2>
                <span className="text-sm text-muted-foreground">{results.length} results</span>
              </div>
              {results.length === 0 ? (
                <p className="text-muted-foreground">No photos in your library yet.</p>
              ) : (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                  {results.map((p) => (
                    <div key={p.id} className="group aspect-square overflow-hidden rounded-lg border border-border shadow-soft">
                      <img src={p.dataUrl} alt={p.name} className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" loading="lazy" />
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* Camera dialog */}
          <Dialog open={cameraOpen} onOpenChange={(o) => !o && stopCamera()}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle className="font-serif">Capture a photo</DialogTitle>
              </DialogHeader>
              <div className="overflow-hidden rounded-lg border border-border bg-background">
                <video ref={videoRef} className="h-full w-full" playsInline muted />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={stopCamera}>Cancel</Button>
                <Button onClick={captureFrame}>Capture</Button>
              </div>
            </DialogContent>
          </Dialog>
        </main>
      </div>
    </RequireAuth>
  );
}
