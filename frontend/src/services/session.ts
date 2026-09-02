export interface UserSession {
  accessToken: string;
  userId: string;
  displayName: string;
  role: string;
  expiresAt: number;
}

const SESSION_KEY = "zero-carbon-park-session-v2";

export function readSession(): UserSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as UserSession;
    if (!session.accessToken || session.expiresAt <= Date.now()) {
      window.localStorage.removeItem(SESSION_KEY);
      return null;
    }
    return session;
  } catch {
    window.localStorage.removeItem(SESSION_KEY);
    return null;
  }
}

export function saveSession(payload: { access_token: string; expires_in: number; user: { userId: string; displayName: string; role: string } }) {
  const session: UserSession = {
    accessToken: payload.access_token,
    userId: payload.user.userId,
    displayName: payload.user.displayName,
    role: payload.user.role,
    expiresAt: Date.now() + payload.expires_in * 1000,
  };
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  return session;
}

export function clearSession() {
  if (typeof window !== "undefined") window.localStorage.removeItem(SESSION_KEY);
}
