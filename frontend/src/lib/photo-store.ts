import { PHOTO_STORAGE_KEY } from "@/lib/storage-keys";

/** A lightweight local photo used by the browser-only upload flow. */
export type StoredPhoto = {
  id: string;
  name: string;
  dataUrl: string;
  uploadedAt: number;
};

export function getPhotos(): StoredPhoto[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(PHOTO_STORAGE_KEY) || "[]") as StoredPhoto[];
  } catch {
    return [];
  }
}

export function savePhotos(photos: StoredPhoto[]): void {
  // Keep storage small — cap at 24 most recent to avoid quota errors.
  const capped = photos.slice(-24);
  try {
    localStorage.setItem(PHOTO_STORAGE_KEY, JSON.stringify(capped));
  } catch {
    // A full localStorage quota should not break the upload flow.
  }
}

export function addPhotos(newOnes: StoredPhoto[]): void {
  const existing = getPhotos();
  savePhotos([...existing, ...newOnes]);
}

export function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
