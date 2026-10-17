import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import type { Role, User } from './types';
import { api } from './api';

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
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
      setUser({ ...data, email: '' });
      setLoading(false);
    }).catch(() => {
      localStorage.removeItem('predicare_token');
      setLoading(false);
    });
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password);
    localStorage.setItem('predicare_token', res.access_token);
    setUser({ role: res.role, display_name: res.display_name, pseudonym: res.pseudonym, email });
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('predicare_token');
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
