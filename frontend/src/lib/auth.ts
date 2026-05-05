// Mock auth — replace with real JWT/MERN API calls later.
export type User = { id: string; email: string; name: string; avatarUrl?: string };

const KEY = "photovault.user";

export function getUser(): User | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export function signIn(email: string, _password: string): User {
  const user: User = {
    id: crypto.randomUUID(),
    email,
    name: email.split("@")[0].replace(/[._]/g, " "),
  };
  localStorage.setItem(KEY, JSON.stringify(user));
  window.dispatchEvent(new Event("auth-change"));
  return user;
}

export function signUp(name: string, email: string, _password: string): User {
  const user: User = { id: crypto.randomUUID(), email, name };
  localStorage.setItem(KEY, JSON.stringify(user));
  window.dispatchEvent(new Event("auth-change"));
  return user;
}

export function signInWithGoogle(): User {
  const user: User = {
    id: crypto.randomUUID(),
    email: "demo@google.com",
    name: "Google User",
  };
  localStorage.setItem(KEY, JSON.stringify(user));
  window.dispatchEvent(new Event("auth-change"));
  return user;
}

export function signOut() {
  localStorage.removeItem(KEY);
  window.dispatchEvent(new Event("auth-change"));
}
