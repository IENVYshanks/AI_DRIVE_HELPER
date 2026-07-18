import { AUTH_STORAGE_KEY } from "@/lib/storage-keys";

export const API_BASE_URL =
  import.meta.env.VITE_BACKEND_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export type BackendTokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
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
  token?: string;
};

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
  const headers = new Headers(options.headers);
  let body = options.body ?? null;

  if (body && !(body instanceof FormData) && typeof body !== "string") {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(body);
  }

  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    body: body as BodyInit | null,
  });

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function getStoredBackendToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const user = JSON.parse(raw) as { backendAccessToken?: string };
    return user.backendAccessToken || null;
  } catch {
    return null;
  }
}

export function registerUser(email: string, name: string): Promise<BackendTokenResponse> {
  return apiRequest<BackendTokenResponse>("/auth/register", {
    method: "POST",
    body: { email, name },
  });
}

export function loginUser(email: string): Promise<BackendTokenResponse> {
  return apiRequest<BackendTokenResponse>("/auth/login", {
    method: "POST",
    body: { email },
  });
}

export function createGoogleSession(googleAccessToken: string): Promise<BackendTokenResponse> {
  return apiRequest<BackendTokenResponse>("/auth/google/session", {
    method: "POST",
    body: { drive_access_token: googleAccessToken },
  });
}

export function upsertDriveFolder(
  token: string,
  driveFolderId: string,
  folderName?: string,
): Promise<FolderResponse> {
  return apiRequest<FolderResponse>("/ingestion/folders", {
    method: "POST",
    token,
    body: {
      drive_folder_id: driveFolderId,
      folder_name: folderName || null,
    },
  });
}

export function startFolderIngestion(
  token: string,
  folderId: string,
): Promise<IngestionJobResponse> {
  return apiRequest<IngestionJobResponse>(`/ingestion/folders/${folderId}/start`, {
    method: "POST",
    token,
    body: { job_type: "full" },
  });
}

export function getIngestionJob(token: string, jobId: string): Promise<IngestionJobResponse> {
  return apiRequest<IngestionJobResponse>(`/ingestion/jobs/${jobId}`, { token });
}

export function getIngestedImages(token: string): Promise<IngestedImageResponse[]> {
  return apiRequest<IngestedImageResponse[]>("/ingestion/images", { token });
}

export function searchFaces(
  token: string,
  image: File | Blob,
  limit: number,
  filename = "query.jpg",
): Promise<SearchQueryResponse> {
  const formData = new FormData();
  formData.append("image", image, image instanceof File ? image.name : filename);

  return apiRequest<SearchQueryResponse>(`/search?limit=${limit}`, {
    method: "POST",
    token,
    body: formData,
  });
}
