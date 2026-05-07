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

type BackendTokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
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

const USER_KEY = "photovault.user";
const GOOGLE_SCRIPT_ID = "google-identity-services";
const GOOGLE_SCOPES = [
  "openid",
  "email",
  "profile",
  "https://www.googleapis.com/auth/drive.readonly",
].join(" ");

const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

export function getUser(): User | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

function saveUser(user: User): User {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  window.dispatchEvent(new Event("auth-change"));
  return user;
}

async function postBackendSession(googleAccessToken: string): Promise<BackendTokenResponse> {
  const response = await fetch(`${BACKEND_URL}/auth/google/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ drive_access_token: googleAccessToken }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || "Backend Google session failed");
  }

  return response.json() as Promise<BackendTokenResponse>;
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
  const response = await fetch(`${BACKEND_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });

  if (!response.ok) {
    throw new Error("User not found");
  }

  const tokenPayload = (await response.json()) as BackendTokenResponse;
  return saveUser({
    id: email,
    email,
    name: email.split("@")[0].replace(/[._]/g, " "),
    backendAccessToken: tokenPayload.access_token,
    backendRefreshToken: tokenPayload.refresh_token,
  });
}

export async function signUp(name: string, email: string, _password: string): Promise<User> {
  const response = await fetch(`${BACKEND_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, name }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || "Account creation failed");
  }

  const tokenPayload = (await response.json()) as BackendTokenResponse;
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
    postBackendSession(googleAccessToken),
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

export function signOut() {
  localStorage.removeItem(USER_KEY);
  window.dispatchEvent(new Event("auth-change"));
}
