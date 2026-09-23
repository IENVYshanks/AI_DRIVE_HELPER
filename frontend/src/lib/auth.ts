import { createGoogleSession } from "@/lib/api";
import { AUTH_STORAGE_KEY } from "@/lib/storage-keys";

export type User = {
  id: string;
  email: string;
  name: string;
  avatarUrl?: string;
  backendAccessToken?: string;
  backendRefreshToken?: string;
};

type GoogleCodeResponse = {
  code?: string;
  error?: string;
  error_description?: string;
};

type GoogleCodeClient = {
  requestCode: () => void;
};

declare global {
  interface Window {
    google?: {
      accounts?: {
        oauth2?: {
          initCodeClient: (config: {
            client_id: string;
            scope: string;
            ux_mode: "popup";
            redirect_uri: string;
            include_granted_scopes: boolean;
            callback: (response: GoogleCodeResponse) => void;
            error_callback?: (error: unknown) => void;
          }) => GoogleCodeClient;
        };
      };
    };
  }
}

const GOOGLE_SCRIPT_ID = "google-identity-services";
const GOOGLE_SCOPES = [
  "openid",
  "email",
  "profile",
  "https://www.googleapis.com/auth/drive.readonly",
].join(" ");

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

export function getUser(): User | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

function saveUser(user: User): User {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user));
  window.dispatchEvent(new Event("auth-change"));
  return user;
}

function loadGoogleIdentityServices(): Promise<void> {
  if (window.google?.accounts?.oauth2) return Promise.resolve();

  return new Promise((resolve, reject) => {
    const existingScript = document.getElementById(GOOGLE_SCRIPT_ID) as HTMLScriptElement | null;
    if (existingScript) {
      existingScript.addEventListener("load", () => resolve(), { once: true });
      existingScript.addEventListener(
        "error",
        () => reject(new Error("Google sign-in failed to load")),
        {
          once: true,
        },
      );
      return;
    }

    const script = document.createElement("script");
    script.id = GOOGLE_SCRIPT_ID;
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Google sign-in failed to load"));
    document.head.appendChild(script);
  });
}

async function requestGoogleAuthorizationCode(): Promise<{
  code: string;
  redirectUri: string;
}> {
  if (!GOOGLE_CLIENT_ID) {
    throw new Error("Set VITE_GOOGLE_CLIENT_ID in frontend/.env.local");
  }

  await loadGoogleIdentityServices();
  const redirectUri = window.location.origin;

  return new Promise((resolve, reject) => {
    const codeClient = window.google?.accounts?.oauth2?.initCodeClient({
      client_id: GOOGLE_CLIENT_ID,
      scope: GOOGLE_SCOPES,
      ux_mode: "popup",
      redirect_uri: redirectUri,
      include_granted_scopes: true,
      callback: (response) => {
        if (response.error || !response.code) {
          reject(
            new Error(
              response.error_description || response.error || "Google sign-in was cancelled",
            ),
          );
          return;
        }
        resolve({ code: response.code, redirectUri });
      },
      error_callback: (error) => reject(error),
    });

    if (!codeClient) {
      reject(new Error("Google sign-in is unavailable"));
      return;
    }

    codeClient.requestCode();
  });
}

export async function signInWithGoogle(): Promise<User> {
  const { code, redirectUri } = await requestGoogleAuthorizationCode();
  const tokenPayload = await createGoogleSession(code, redirectUri);

  return saveUser({
    id: tokenPayload.user.id,
    email: tokenPayload.user.email,
    name: tokenPayload.user.name || tokenPayload.user.email.split("@")[0],
    avatarUrl: tokenPayload.user.avatar_url || undefined,
    backendAccessToken: tokenPayload.access_token,
    backendRefreshToken: tokenPayload.refresh_token,
  });
}

export function signOut(): void {
  localStorage.removeItem(AUTH_STORAGE_KEY);
  window.dispatchEvent(new Event("auth-change"));
}
