import manifest from "@/lib/demo-data.json";

export type DemoPhoto = {
  id: string;
  src: string;
  alt: string;
  location?: string;
  date?: string;
};

export type DemoFace = {
  id: string;
  photoId: string;
  label: string;
  /** Percent-based bounds within the photo. */
  bounds: { x: number; y: number; width: number; height: number };
};

export type DemoMatch = {
  faceId: string;
  photoId: string;
  score: number;
};

export type DemoPerson = {
  id: string;
  name: string;
  portraits: string[];
  matches: Array<{ photoId: string; score: number }>;
};

/**
 * Add the approved public-demo photos and precomputed face data here.
 * The route intentionally performs no uploads or live face analysis.
 */
export const DEMO_PHOTOS: DemoPhoto[] = manifest.photos;
export const DEMO_FACES: DemoFace[] = manifest.faces;
export const DEMO_MATCHES: DemoMatch[] = manifest.matches;
export const DEMO_PEOPLE: DemoPerson[] = manifest.people;

export const DEMO_COLLECTION_SIZE = 20;
