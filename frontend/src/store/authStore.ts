import { create } from "zustand";

export type UserRole = "student" | "teacher";

export interface Session {
  token: string;
  role: UserRole;
  id: number;
  name: string;
}

interface AuthState {
  token: string | null;
  role: UserRole | null;
  id: number | null;
  name: string;
  isAuthenticated: boolean;
  login: (session: Session) => void;
  logout: () => void;
}

const STORAGE_KEY = "pea-session";

function load(): Pick<AuthState, "token" | "role" | "id" | "name" | "isAuthenticated"> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const s = JSON.parse(raw) as Session;
      if (s.token) return { token: s.token, role: s.role, id: s.id, name: s.name, isAuthenticated: true };
    }
  } catch {
    /* хранилище недоступно — начинаем без сессии */
  }
  return { token: null, role: null, id: null, name: "", isAuthenticated: false };
}

export const useAuthStore = create<AuthState>((set) => ({
  ...load(),
  login: (session) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    } catch {
      /* ignore */
    }
    set({ ...session, isAuthenticated: true });
  },
  logout: () => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
    set({ token: null, role: null, id: null, name: "", isAuthenticated: false });
  },
}));
