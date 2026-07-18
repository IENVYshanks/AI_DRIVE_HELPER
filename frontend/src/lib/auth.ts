import {
  createGoogleSession,
  loginUser,
  registerUser,
  type BackendTokenResponse,
} from "@/lib/api";
import { AUTH_STORAGE_KEY } from "@/lib/storage-keys";

export type User = {
  id: string;
  email: string;
  name: string;
  avatarUrl?: string;
  backendAccessToken?: string;
  backendRefreshToken?: string;
  googleAccessToken?: string;
};

type GoogleTokenResponse = {
  access_token?: string;
  error?: string;
  error_description?: string;
};

type GoogleUserInfo = {
  sub: string;
  email: string;
  name?: string;
  picture?: string;
};

type GoogleTokenClient = {
  requestAccessToken: (options?: { prompt?: string }) => void;
};

declare global {
  interface Window {
    google?: {
      accounts?: {
        oauth2?: {
          initTokenClient: (config: {
            client_id: string;
            scope: string;
            callback: (response: GoogleTokenResponse) => void;
            error_callback?: (error: unknown) => void;
          }) => GoogleTokenClient;
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

async function fetchGoogleUserInfo(accessToken: string): Promise<GoogleUserInfo> {
  const response = await fetch("https://www.googleapis.com/oauth2/v3/userinfo", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!response.ok) {
    throw new Error("Could not read Google profile");
  }

  return response.json() as Promise<GoogleUserInfo>;
}

function loadGoogleIdentityServices(): Promise<void> {
  if (window.google?.accounts?.oauth2) return Promise.resolve();

  return new Promise((resolve, reject) => {
    const existingScript = document.getElementById(GOOGLE_SCRIPT_ID) as HTMLScriptElement | null;
    if (existingScript) {
      existingScript.addEventListener("load", () => resolve(), { once: true });
      existingScript.addEventListener("error", () => reject(new Error("Google sign-in failed to load")), {
        once: true,
      });
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

async function requestGoogleAccessToken(): Promise<string> {
  if (!GOOGLE_CLIENT_ID) {
    throw new Error("Set VITE_GOOGLE_CLIENT_ID in frontend/.env.local");
  }

  await loadGoogleIdentityServices();

  return new Promise((resolve, reject) => {
    const tokenClient = window.google?.accounts?.oauth2?.initTokenClient({
      client_id: GOOGLE_CLIENT_ID,
      scope: GOOGLE_SCOPES,
      callback: (response) => {
        if (response.error || !response.access_token) {
          reject(new Error(response.error_description || response.error || "Google sign-in was cancelled"));
          return;
        }
        resolve(response.access_token);
      },
      error_callback: (error) => reject(error),
    });

    if (!tokenClient) {
      reject(new Error("Google sign-in is unavailable"));
      return;
    }

    tokenClient.requestAccessToken({ prompt: "consent" });
  });
}

export async function signIn(email: string, _password: string): Promise<User> {
  const tokenPayload = await loginUser(email);
  return saveUser({
    id: email,
    email,
    name: email.split("@")[0].replace(/[._]/g, " "),
    backendAccessToken: tokenPayload.access_token,
    backendRefreshToken: tokenPayload.refresh_token,
  });
}

export async function signUp(name: string, email: string, _password: string): Promise<User> {
  const tokenPayload = await registerUser(email, name);
  return saveUser({
    id: email,
    email,
    name,
    backendAccessToken: tokenPayload.access_token,
    backendRefreshToken: tokenPayload.refresh_token,
  });
}

export async function signInWithGoogle(): Promise<User> {
  const googleAccessToken = await requestGoogleAccessToken();
  const [googleUser, tokenPayload] = await Promise.all([
    fetchGoogleUserInfo(googleAccessToken),
    createGoogleSession(googleAccessToken),
  ]);

  return saveUser({
    id: googleUser.sub,
    email: googleUser.email,
    name: googleUser.name || googleUser.email.split("@")[0],
    avatarUrl: googleUser.picture,
    googleAccessToken,
    backendAccessToken: tokenPayload.access_token,
    backendRefreshToken: tokenPayload.refresh_token,
  });
}

export function signOut(): void {
  localStorage.removeItem(AUTH_STORAGE_KEY);
  window.dispatchEvent(new Event("auth-change"));
}
