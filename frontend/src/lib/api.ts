import { AUTH_STORAGE_KEY } from "@/lib/storage-keys";

export const API_BASE_URL =
  import.meta.env.VITE_BACKEND_URL?.replace(/\/$/, "") ||
  (typeof window === "undefined"
    ? "http://localhost:8000"
    : `${window.location.protocol}//${window.location.hostname}:8000`);

export type GoogleSessionResponse = {
  user: {
    id: string;
    email: string;
    name: string | null;
    avatar_url: string | null;
  };
};

export type FolderResponse = {
  id: string;
  drive_folder_id: string;
  folder_name: string | null;
  status: string;
  total_images: number;
  processed_images: number;
  failed_images: number;
  error_message: string | null;
};

export type DriveFolderItemResponse = {
  id: string;
  name: string;
  parent_id: string | null;
};

export type DriveFolderBrowserResponse = {
  current: DriveFolderItemResponse;
  folders: DriveFolderItemResponse[];
};

export type IngestionJobResponse = {
  id: string;
  folder_id: string | null;
  status: string;
  job_type: string;
  total: number;
  processed: number;
  failed: number;
  error_message: string | null;
  failed_file_ids: string[] | null;
};

export type IngestedImageResponse = {
  id: string;
  folder_id: string | null;
  drive_file_id: string;
  drive_file_name: string | null;
  mime_type: string | null;
  file_size_bytes: number | null;
  status: string;
  face_count: number;
  error_message: string | null;
  image_url: string | null;
};

export type SearchResultItemResponse = {
  id: string;
  image_id: string;
  face_id: string | null;
  similarity_score: number | null;
  rank: number | null;
  image_name: string | null;
  drive_file_id: string | null;
  image_url: string | null;
};

export type SearchQueryResponse = {
  id: string;
  face_detected: boolean;
  results_count: number;
  top_score: number | null;
  search_latency_ms: number | null;
  results: SearchResultItemResponse[];
};

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: BodyInit | object | null;
  retryAuth?: boolean;
};

const CSRF_COOKIE_NAME = "app_csrf";
const CSRF_HEADER_NAME = "X-CSRF-Token";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${encodeURIComponent(name)}=`;
  const cookie = document.cookie.split("; ").find((item) => item.startsWith(prefix));
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
}

function markSessionExpired(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(AUTH_STORAGE_KEY);
  window.dispatchEvent(new Event("auth-change"));
}

let refreshPromise: Promise<boolean> | null = null;

function performSessionRefresh(csrfToken: string): Promise<Response> {
  return fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    credentials: "include",
    headers: { [CSRF_HEADER_NAME]: csrfToken },
  });
}

function refreshSession(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;
  const initialCsrfToken = getCookie(CSRF_COOKIE_NAME);
  if (!initialCsrfToken) return Promise.resolve(false);

  const refresh = async () => {
    const currentCsrfToken = getCookie(CSRF_COOKIE_NAME);
    if (currentCsrfToken && currentCsrfToken !== initialCsrfToken) return true;
    const response = await performSessionRefresh(initialCsrfToken);
    return response.ok;
  };
  const task: Promise<boolean> =
    typeof navigator !== "undefined" && navigator.locks
      ? (navigator.locks.request("app-session-refresh", () =>
          refresh(),
        ) as unknown as Promise<boolean>)
      : refresh();
  const activeRefresh = task.finally(() => {
    refreshPromise = null;
  });
  refreshPromise = activeRefresh;
  return activeRefresh;
}

async function parseError(response: Response): Promise<string> {
  const text = await response.text();
  if (!text) return `Request failed with ${response.status}`;

  try {
    const payload = JSON.parse(text) as { detail?: unknown };
    if (typeof payload.detail === "string") return payload.detail;
    if (payload.detail) return JSON.stringify(payload.detail);
  } catch {
    return text;
  }

  return text;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body: requestBody, retryAuth = true, ...requestInit } = options;
  const headers = new Headers(options.headers);
  let body = requestBody ?? null;

  if (body && !(body instanceof FormData) && typeof body !== "string") {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(body);
  }

  const method = (requestInit.method || "GET").toUpperCase();
  if (!SAFE_METHODS.has(method) && !headers.has(CSRF_HEADER_NAME)) {
    const csrfToken = getCookie(CSRF_COOKIE_NAME);
    if (csrfToken) headers.set(CSRF_HEADER_NAME, csrfToken);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...requestInit,
    headers,
    body: body as BodyInit | null,
    credentials: "include",
  });

  if (response.status === 401 && !path.startsWith("/auth/")) {
    if (retryAuth && (await refreshSession())) {
      return apiRequest<T>(path, { ...options, retryAuth: false });
    }
    markSessionExpired();
  }

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function createGoogleSession(
  code: string,
  redirectUri: string,
): Promise<GoogleSessionResponse> {
  return apiRequest<GoogleSessionResponse>("/auth/google/session", {
    method: "POST",
    headers: { "X-Requested-With": "XMLHttpRequest" },
    body: { code, redirect_uri: redirectUri },
  });
}

export function logoutSession(): Promise<void> {
  return apiRequest<void>("/auth/logout", { method: "POST", retryAuth: false });
}

export function upsertDriveFolder(
  driveFolderId: string,
  folderName?: string,
): Promise<FolderResponse> {
  return apiRequest<FolderResponse>("/ingestion/folders", {
    method: "POST",
    body: {
      drive_folder_id: driveFolderId,
      folder_name: folderName || null,
    },
  });
}

export function browseDriveFolders(parentId = "root"): Promise<DriveFolderBrowserResponse> {
  const query = new URLSearchParams({ parent_id: parentId });
  return apiRequest<DriveFolderBrowserResponse>(`/ingestion/drive/folders?${query}`);
}

export function startFolderIngestion(folderId: string): Promise<IngestionJobResponse> {
  return apiRequest<IngestionJobResponse>(`/ingestion/folders/${folderId}/start`, {
    method: "POST",
    body: { job_type: "full" },
  });
}

export function getIngestionJob(jobId: string): Promise<IngestionJobResponse> {
  return apiRequest<IngestionJobResponse>(`/ingestion/jobs/${jobId}`);
}

export function getIngestedImages(): Promise<IngestedImageResponse[]> {
  return apiRequest<IngestedImageResponse[]>("/ingestion/images");
}

export function searchFaces(
  image: File | Blob,
  limit: number,
  filename = "query.jpg",
): Promise<SearchQueryResponse> {
  const formData = new FormData();
  formData.append("image", image, image instanceof File ? image.name : filename);

  return apiRequest<SearchQueryResponse>(`/search?limit=${limit}`, {
    method: "POST",
    body: formData,
  });
}
