import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import type { Role, User } from './types';
import { api } from './api';

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (identifier: string, password: string) => Promise<User>;
  refreshUser: () => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const ROLE_HOME: Record<Role, string> = {
  insured: '/assurant',
  provider: '/professionnel',
  manager: '/gestionnaire',
  admin: '/admin',
};

export function getRoleHome(role: Role): string {
  return ROLE_HOME[role];
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('predicare_token');
    if (!token) {
      setLoading(false);
      return;
    }
    api.getMe().then((data) => {
      setUser(data);
      setLoading(false);
    }).catch(() => {
      localStorage.removeItem('predicare_token');
      setLoading(false);
    });
  }, []);

  const login = useCallback(async (identifier: string, password: string) => {
    const res = await api.login(identifier, password);
    localStorage.setItem('predicare_token', res.access_token);
    if (res.refresh_token) {
      localStorage.setItem('predicare_refresh_token', res.refresh_token);
    }
    const loggedIn: User = {
      role: res.role,
      display_name: res.display_name,
      pseudonym: res.pseudonym,
      email: res.email,
      must_change_password: res.must_change_password,
    };
    setUser(loggedIn);
    return loggedIn;
  }, []);

  const logout = useCallback(() => {
    void api.logout().catch((error: unknown) => {
      console.error('La révocation de la session a échoué.', error);
    });
    localStorage.removeItem('predicare_token');
    localStorage.removeItem('predicare_refresh_token');
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    const data = await api.getMe();
    const refreshed: User = {
      role: data.role,
      display_name: data.display_name,
      pseudonym: data.pseudonym,
      email: data.email,
      must_change_password: data.must_change_password,
    };
    setUser(refreshed);
    return refreshed;
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, refreshUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
