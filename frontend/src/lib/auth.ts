import type { User, LoginRequest, RegisterRequest, AuthResponse } from "@/types/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOKEN_KEY = "ei_token";
const USER_KEY = "ei_user";

// Token storage (safe for SSR — guard with typeof window)
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

export function getCurrentUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

function saveAuth(token: string, user: User): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function logout(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

// Authenticated fetch wrapper — adds Bearer token when available
export async function authFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "요청에 실패했습니다.");
  }
  return res.json();
}

// Auth API calls
export async function login(req: LoginRequest): Promise<AuthResponse> {
  const data = await authFetch<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(req),
  });
  saveAuth(data.token, data.user);
  return data;
}

export async function register(req: RegisterRequest): Promise<AuthResponse> {
  const data = await authFetch<AuthResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(req),
  });
  saveAuth(data.token, data.user);
  return data;
}
