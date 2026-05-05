// Mock client-side photo store. Replace with real API later.
export type StoredPhoto = {
  id: string;
  name: string;
  dataUrl: string;
  uploadedAt: number;
};

const KEY = "photovault.photos";

export function getPhotos(): StoredPhoto[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch {
    return [];
  }
}

export function savePhotos(photos: StoredPhoto[]) {
  // Keep storage small — cap at 24 most recent to avoid quota errors.
  const capped = photos.slice(-24);
  try {
    localStorage.setItem(KEY, JSON.stringify(capped));
  } catch {
    // ignore quota issues in mock
  }
}

export function addPhotos(newOnes: StoredPhoto[]) {
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
