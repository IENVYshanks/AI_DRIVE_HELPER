import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import {
  Check,
  Copy,
  Images,
  MapPin,
  RotateCcw,
  Search,
  Share2,
  SlidersHorizontal,
  Sparkles,
  UserRoundSearch,
} from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import {
  DEMO_COLLECTION_SIZE,
  DEMO_FACES,
  DEMO_MATCHES,
  DEMO_PEOPLE,
  DEMO_PHOTOS,
  type DemoFace,
  type DemoPerson,
  type DemoPhoto,
} from "@/lib/demo-data";

export const Route = createFileRoute("/demo")({
  head: () => ({
    meta: [
      { title: "Face search demo — FaceSeek" },
      {
        name: "description",
        content: "Explore how FaceSeek finds the same person across a fixed photo collection.",
      },
    ],
  }),
  component: DemoPage,
});

type DemoResult = { photo: DemoPhoto; score: number };

function facesForPhoto(photoId: string): DemoFace[] {
  return DEMO_FACES.filter((face) => face.photoId === photoId);
}

function PhotoCard({
  photo,
  selected,
  onSelect,
}: {
  photo: DemoPhoto;
  selected: boolean;
  onSelect: () => void;
}) {
  const faceCount = facesForPhoto(photo.id).length;

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`group overflow-hidden rounded-xl border bg-paper text-left shadow-soft transition-all hover:-translate-y-0.5 hover:shadow-editorial focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
        selected ? "border-primary ring-2 ring-primary/25" : "border-border"
      }`}
    >
      <div className="relative aspect-[4/5] overflow-hidden bg-muted">
        <img
          src={photo.src}
          alt={photo.alt}
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          loading="lazy"
        />
        <span className="absolute bottom-2 right-2 rounded-full bg-background/90 px-2 py-1 text-[11px] font-medium backdrop-blur-sm">
          {faceCount} {faceCount === 1 ? "face" : "faces"}
        </span>
      </div>
      <div className="p-3">
        <p className="line-clamp-1 text-sm font-medium">{photo.alt}</p>
        {(photo.location || photo.date) && (
          <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">
            {[photo.location, photo.date].filter(Boolean).join(" · ")}
          </p>
        )}
      </div>
    </button>
  );
}

function PersonCard({
  person,
  selected,
  onSelect,
}: {
  person: DemoPerson;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`group flex items-center gap-3 rounded-2xl border bg-paper p-3 text-left shadow-soft transition-all hover:-translate-y-0.5 hover:shadow-editorial focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
        selected ? "border-primary ring-2 ring-primary/25" : "border-border"
      }`}
    >
      <img
        src={person.portraits[0]}
        alt={person.name}
        className="h-16 w-16 rounded-xl object-cover object-top"
      />
      <span className="min-w-0">
        <span className="block truncate font-serif text-lg">{person.name}</span>
        <span className="mt-0.5 block text-xs text-muted-foreground">
          {person.matches.length} matched photos
        </span>
      </span>
    </button>
  );
}

function DemoPage() {
  const [filter, setFilter] = useState("");
  const [selectedPhotoId, setSelectedPhotoId] = useState<string | null>(null);
  const [selectedFaceId, setSelectedFaceId] = useState<string | null>(null);
  const [selectedPersonId, setSelectedPersonId] = useState<string | null>(null);
  const [threshold, setThreshold] = useState(72);
  const [hasSearched, setHasSearched] = useState(false);

  const selectedPhoto = DEMO_PHOTOS.find((photo) => photo.id === selectedPhotoId) ?? null;
  const selectedFace = DEMO_FACES.find((face) => face.id === selectedFaceId) ?? null;
  const selectedPerson = DEMO_PEOPLE.find((person) => person.id === selectedPersonId) ?? null;
  const selectedPhotoFaces = selectedPhoto ? facesForPhoto(selectedPhoto.id) : [];

  const visiblePhotos = useMemo(() => {
    const query = filter.trim().toLocaleLowerCase();
    if (!query) return DEMO_PHOTOS;
    return DEMO_PHOTOS.filter((photo) =>
      [photo.alt, photo.location, photo.date]
        .filter(Boolean)
        .some((value) => value?.toLocaleLowerCase().includes(query)),
    );
  }, [filter]);

  const results = useMemo<DemoResult[]>(() => {
    if (!hasSearched) return [];
    const sourceMatches = selectedPerson
      ? selectedPerson.matches
      : DEMO_MATCHES.filter((match) => match.faceId === selectedFaceId);
    return sourceMatches
      .filter((match) => match.score >= threshold / 100)
      .map((match) => ({
        photo: DEMO_PHOTOS.find((photo) => photo.id === match.photoId),
        score: match.score,
      }))
      .filter((result): result is DemoResult => Boolean(result.photo))
      .sort((left, right) => right.score - left.score);
  }, [hasSearched, selectedFaceId, selectedPerson, threshold]);

  const selectPhoto = (photoId: string) => {
    setSelectedPhotoId(photoId);
    setSelectedFaceId(null);
    setSelectedPersonId(null);
    setHasSearched(false);
  };

  const selectFace = (faceId: string) => {
    setSelectedFaceId(faceId);
    setSelectedPersonId(null);
    setHasSearched(false);
  };

  const selectPerson = (personId: string) => {
    setSelectedPersonId(personId);
    setSelectedPhotoId(null);
    setSelectedFaceId(null);
    setHasSearched(true);
  };

  const reset = () => {
    setFilter("");
    setSelectedPhotoId(null);
    setSelectedFaceId(null);
    setSelectedPersonId(null);
    setThreshold(72);
    setHasSearched(false);
  };

  const copyShareLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      toast.success("Demo link copied");
    } catch {
      toast.error("Could not copy the link");
    }
  };

  const shareDemo = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: "FaceSeek face search demo",
          text: "Try FaceSeek's private, precomputed face search demo.",
          url: window.location.href,
        });
        return;
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
      }
    }
    await copyShareLink();
  };

  return (
    <div className="min-h-screen bg-background">
      <SiteHeader />
      <main className="mx-auto max-w-[90rem] px-5 py-8 sm:px-8 sm:py-12">
        <section className="relative overflow-hidden border-y border-foreground bg-background px-0 py-10 sm:py-14">
          <div
            className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-ochre/10 blur-3xl"
            aria-hidden
          />
          <div className="relative flex flex-col justify-between gap-8 lg:flex-row lg:items-end">
            <div className="max-w-3xl">
              <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-ochre">
                <Sparkles className="h-3.5 w-3.5" aria-hidden />
                Public demo
              </div>
              <h1 className="mt-3 max-w-[13ch] font-serif text-5xl leading-[0.95] sm:text-7xl lg:text-8xl">
                Pick a face. Find every moment.
              </h1>
              <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground">
                Explore a fixed collection with precomputed matches. Nothing is uploaded and no live
                face analysis runs in your browser.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={shareDemo}>
                <Share2 className="mr-2 h-4 w-4" /> Share
              </Button>
              <Button variant="outline" onClick={reset}>
                <RotateCcw className="mr-2 h-4 w-4" /> Start over
              </Button>
            </div>
          </div>
        </section>

        <section className="mt-8 grid gap-4 sm:grid-cols-3" aria-label="Demo steps">
          {[
            ["01", "Choose a person", selectedPerson ? "Complete" : "Use a named portrait"],
            ["02", "Or pick a face", selectedFace ? "Complete" : "Explore a group photo"],
            ["03", "Reveal matches", hasSearched ? "Complete" : "Run the precomputed search"],
          ].map(([step, title, detail], index) => {
            const complete = [Boolean(selectedPerson), Boolean(selectedFace), hasSearched][index];
            return (
              <div
                key={step}
                className="flex items-center gap-4 rounded-2xl border border-border bg-paper p-4 shadow-soft"
              >
                <span
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm ${complete ? "bg-primary text-primary-foreground" : "bg-background text-muted-foreground"}`}
                >
                  {complete ? <Check className="h-4 w-4" /> : step}
                </span>
                <div>
                  <p className="font-serif text-lg">{title}</p>
                  <p className="text-xs text-muted-foreground">{detail}</p>
                </div>
              </div>
            );
          })}
        </section>

        <section className="mt-10">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-ochre">Featured people</p>
            <h2 className="mt-2 font-serif text-3xl">Who are you looking for?</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Choose a named portrait to reveal their strongest matches across the collection.
            </p>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {DEMO_PEOPLE.map((person) => (
              <PersonCard
                key={person.id}
                person={person}
                selected={person.id === selectedPersonId}
                onSelect={() => selectPerson(person.id)}
              />
            ))}
          </div>
        </section>

        <div className="mt-10 grid gap-8 lg:grid-cols-[minmax(0,1fr)_21rem]">
          <div>
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-ochre">Demo collection</p>
                <h2 className="mt-2 font-serif text-3xl">Choose a starting photo</h2>
              </div>
              <div className="relative w-full sm:w-64">
                <Search
                  className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                  aria-hidden
                />
                <Input
                  value={filter}
                  onChange={(event) => setFilter(event.target.value)}
                  placeholder="Filter photos..."
                  className="pl-9"
                  disabled={!DEMO_PHOTOS.length}
                  aria-label="Filter demo photos"
                />
              </div>
            </div>

            {DEMO_PHOTOS.length ? (
              <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
                {visiblePhotos.map((photo) => (
                  <PhotoCard
                    key={photo.id}
                    photo={photo}
                    selected={photo.id === selectedPhotoId}
                    onSelect={() => selectPhoto(photo.id)}
                  />
                ))}
              </div>
            ) : (
              <div className="mt-5 rounded-2xl border border-dashed border-border bg-paper px-6 py-14 text-center shadow-soft">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-background">
                  <Images className="h-6 w-6 text-clay" aria-hidden />
                </div>
                <h3 className="mt-4 font-serif text-2xl">
                  The collection is ready for your photos
                </h3>
                <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
                  Add the approved images and precomputed face manifest to activate this demo. The
                  complete selection and matching experience is already wired.
                </p>
                <span className="mt-5 inline-flex rounded-full border border-border bg-background px-3 py-1 text-xs text-muted-foreground">
                  0 of {DEMO_COLLECTION_SIZE} photos added
                </span>
              </div>
            )}

            {DEMO_PHOTOS.length > 0 && !visiblePhotos.length && (
              <div className="mt-5 rounded-2xl border border-dashed border-border py-12 text-center text-sm text-muted-foreground">
                No photos match “{filter}”.
              </div>
            )}
          </div>

          <aside className="h-fit border-t-2 border-foreground bg-paper p-5 shadow-soft lg:sticky lg:top-24">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-ochre">Search studio</p>
                <h2 className="mt-1 font-serif text-2xl">Find this person</h2>
              </div>
              <UserRoundSearch className="h-5 w-5 text-clay" aria-hidden />
            </div>

            {selectedPerson ? (
              <div className="mt-5">
                <div className="grid grid-cols-2 gap-2">
                  {selectedPerson.portraits.map((portrait, index) => (
                    <img
                      key={portrait}
                      src={portrait}
                      alt={`${selectedPerson.name} portrait ${index + 1}`}
                      className="aspect-[4/5] w-full rounded-xl object-cover object-top"
                    />
                  ))}
                </div>
                <p className="mt-3 font-serif text-xl">{selectedPerson.name}</p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  A centroid from both portraits is matched against the demo collection.
                </p>
              </div>
            ) : !selectedPhoto ? (
              <div className="mt-5 rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                Choose a collection photo to begin.
              </div>
            ) : (
              <>
                <div className="relative mt-5 aspect-[4/5] overflow-hidden rounded-xl bg-muted">
                  <img
                    src={selectedPhoto.src}
                    alt={selectedPhoto.alt}
                    className="h-full w-full object-cover"
                  />
                  {selectedPhotoFaces.map((face) => (
                    <button
                      key={face.id}
                      type="button"
                      aria-label={`Select ${face.label}`}
                      aria-pressed={face.id === selectedFaceId}
                      onClick={() => selectFace(face.id)}
                      className={`absolute rounded-md border-2 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-background ${
                        face.id === selectedFaceId
                          ? "border-primary bg-primary/20 shadow-[0_0_0_2px_var(--color-background)]"
                          : "border-foreground/80 bg-background/10 hover:bg-foreground/15"
                      }`}
                      style={{
                        left: `${face.bounds.x}%`,
                        top: `${face.bounds.y}%`,
                        width: `${face.bounds.width}%`,
                        height: `${face.bounds.height}%`,
                      }}
                    >
                      <span className="sr-only">{face.label}</span>
                    </button>
                  ))}
                </div>

                <div className="mt-4">
                  <p className="text-sm font-medium">Select a detected face</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {selectedPhotoFaces.map((face, index) => (
                      <Button
                        key={face.id}
                        size="sm"
                        variant={face.id === selectedFaceId ? "default" : "outline"}
                        onClick={() => selectFace(face.id)}
                      >
                        Person {index + 1}
                      </Button>
                    ))}
                    {!selectedPhotoFaces.length && (
                      <p className="text-xs text-muted-foreground">
                        No faces are mapped in this photo.
                      </p>
                    )}
                  </div>
                </div>
              </>
            )}

            <div className="mt-6 border-t border-border pt-5">
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2 font-medium">
                  <SlidersHorizontal className="h-4 w-4" /> Match confidence
                </span>
                <span className="tabular-nums text-muted-foreground">{threshold}%+</span>
              </div>
              <Slider
                className="mt-4"
                min={50}
                max={95}
                step={1}
                value={[threshold]}
                onValueChange={([value]) => {
                  setThreshold(value);
                  setHasSearched(Boolean(selectedPerson));
                }}
                aria-label="Minimum match confidence"
              />
              <div className="mt-2 flex justify-between text-[11px] text-muted-foreground">
                <span>More results</span>
                <span>Closer matches</span>
              </div>
            </div>

            <Button
              className="mt-6 w-full"
              size="lg"
              disabled={!selectedFace && !selectedPerson}
              onClick={() => setHasSearched(true)}
            >
              <Search className="mr-2 h-4 w-4" /> Reveal matches
            </Button>
          </aside>
        </div>

        {hasSearched && (
          <section className="mt-12 border-t border-border pt-10" aria-live="polite">
            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-ochre">Search results</p>
                <h2 className="mt-2 font-serif text-3xl">
                  {results.length} {results.length === 1 ? "moment" : "moments"} found
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Matches for {selectedPerson?.name ?? selectedFace?.label ?? "the selected face"}{" "}
                  at {threshold}% confidence or higher.
                </p>
              </div>
              <Button variant="outline" onClick={copyShareLink}>
                <Copy className="mr-2 h-4 w-4" /> Copy demo link
              </Button>
            </div>

            {results.length ? (
              <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                {results.map(({ photo, score }, index) => (
                  <article
                    key={`${selectedFaceId}-${photo.id}`}
                    className="overflow-hidden rounded-xl border border-border bg-paper shadow-soft"
                  >
                    <div className="relative aspect-[4/5] overflow-hidden bg-muted">
                      <img
                        src={photo.src}
                        alt={photo.alt}
                        className="h-full w-full object-cover"
                        loading="lazy"
                      />
                      <span className="absolute left-2 top-2 rounded-full bg-background/90 px-2 py-1 text-xs font-semibold tabular-nums backdrop-blur-sm">
                        {Math.round(score * 100)}%
                      </span>
                    </div>
                    <div className="p-3">
                      <p className="text-xs uppercase tracking-wider text-muted-foreground">
                        Match {String(index + 1).padStart(2, "0")}
                      </p>
                      <p className="mt-1 line-clamp-1 text-sm font-medium">{photo.alt}</p>
                      {photo.location && (
                        <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                          <MapPin className="h-3 w-3" /> {photo.location}
                        </p>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="mt-6 rounded-2xl border border-dashed border-border py-12 text-center">
                <p className="font-serif text-xl">No matches at this confidence.</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Lower the threshold and search again.
                </p>
              </div>
            )}
          </section>
        )}

        <footer className="mt-14 border-t border-border py-8 text-sm text-muted-foreground">
          <p>This demo uses only approved, fixed photos and precomputed results.</p>
        </footer>
      </main>
    </div>
  );
}
