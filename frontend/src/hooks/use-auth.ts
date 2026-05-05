import { useEffect, useState } from "react";
import { getUser, type User } from "@/lib/auth";

export function useAuth() {
  const [user, setUser] = useState<User | null>(() => getUser());

  useEffect(() => {
    const sync = () => setUser(getUser());
    window.addEventListener("auth-change", sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("auth-change", sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return { user };
}
