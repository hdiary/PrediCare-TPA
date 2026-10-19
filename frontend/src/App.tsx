import { Suspense, lazy, type ComponentType } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth, getRoleHome } from '@/lib/auth';
import { ThemeProvider } from '@/lib/theme';
import { ToastProvider } from '@/components/ui/Toast';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { AppLayout } from '@/components/AppLayout';
import { PageLoader } from '@/components/PageLoader';

/** Charge une page à la demande : son code n'est téléchargé que lorsqu'on la visite. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function lazyPage<M extends Record<string, ComponentType<any>>, K extends keyof M>(load: () => Promise<M>, name: K) {
  return lazy(() => load().then((m) => ({ default: m[name] })));
}

const LoginPage = lazyPage(() => import('@/pages/LoginPage'), 'LoginPage');
const NotFoundPage = lazyPage(() => import('@/pages/NotFound'), 'NotFoundPage');
const AccessDeniedPage = lazyPage(() => import('@/pages/AccessDenied'), 'AccessDeniedPage');
const HelpPage = lazyPage(() => import('@/pages/HelpPage'), 'HelpPage');

// Insured pages
const ChatPage = lazyPage(() => import('@/pages/insured/ChatPage'), 'ChatPage');
const ReimbursementsPage = lazyPage(() => import('@/pages/insured/ReimbursementsPage'), 'ReimbursementsPage');

// Provider pages
const DepositInvoicePage = lazyPage(() => import('@/pages/provider/DepositInvoicePage'), 'DepositInvoicePage');
const ProviderInvoicesPage = lazyPage(() => import('@/pages/provider/ProviderInvoicesPage'), 'ProviderInvoicesPage');

// Manager pages
const ManagerDashboard = lazyPage(() => import('@/pages/manager/ManagerDashboard'), 'ManagerDashboard');
const AlertsListPage = lazyPage(() => import('@/pages/manager/AlertsListPage'), 'AlertsListPage');
const AlertDetailPage = lazyPage(() => import('@/pages/manager/AlertDetailPage'), 'AlertDetailPage');
const PrescriptionAlertsPage = lazyPage(() => import('@/pages/manager/PrescriptionAlertsPage'), 'PrescriptionAlertsPage');

// Admin pages
const AdminSupervision = lazyPage(() => import('@/pages/admin/AdminSupervision'), 'AdminSupervision');
const AdminConfig = lazyPage(() => import('@/pages/admin/AdminConfig'), 'AdminConfig');
const AdminModels = lazyPage(() => import('@/pages/admin/AdminModels'), 'AdminModels');
const AdminAuditLog = lazyPage(() => import('@/pages/admin/AdminAuditLog'), 'AdminAuditLog');
const AdminUsers = lazyPage(() => import('@/pages/admin/AdminUsers'), 'AdminUsers');
const RegisterPage = lazyPage(() => import('@/pages/RegisterPage'), 'RegisterPage');
const ForgotPasswordPage = lazyPage(() => import('@/pages/ForgotPasswordPage'), 'ForgotPasswordPage');
const ResetPasswordPage = lazyPage(() => import('@/pages/ResetPasswordPage'), 'ResetPasswordPage');

function RootRedirect() {
  const { user, loading } = useAuth();
  if (loading) return <PageLoader fullscreen />;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={getRoleHome(user.role)} replace />;
}

function LoginRoute() {
  const { user, loading } = useAuth();
  if (loading) return <PageLoader fullscreen />;
  if (user) return <Navigate to={getRoleHome(user.role)} replace />;
  return <LoginPage />;
}

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          <ToastProvider>
            <BrowserRouter>
              <Suspense fallback={<PageLoader fullscreen />}>
              <Routes>
                <Route path="/" element={<RootRedirect />} />
                <Route path="/login" element={<LoginRoute />} />
                <Route path="/inscription" element={<RegisterPage />} />
                <Route path="/mot-de-passe-oublie" element={<ForgotPasswordPage />} />
                <Route path="/reinitialiser-mot-de-passe" element={<ResetPasswordPage />} />
                <Route path="/acces-refuse" element={<AccessDeniedPage />} />

                {/* Insured routes */}
                <Route path="/assurant" element={<AppLayout allowedRoles={['insured']}><ChatPage /></AppLayout>} />
                <Route path="/assurant/remboursements" element={<AppLayout allowedRoles={['insured']}><ReimbursementsPage /></AppLayout>} />
                <Route path="/assurant/aide" element={<AppLayout allowedRoles={['insured']}><HelpPage /></AppLayout>} />

                {/* Provider routes */}
                <Route path="/professionnel" element={<AppLayout allowedRoles={['provider']}><DepositInvoicePage /></AppLayout>} />
                <Route path="/professionnel/factures" element={<AppLayout allowedRoles={['provider']}><ProviderInvoicesPage /></AppLayout>} />
                <Route path="/professionnel/aide" element={<AppLayout allowedRoles={['provider']}><HelpPage /></AppLayout>} />

                {/* Manager routes */}
                <Route path="/gestionnaire" element={<AppLayout allowedRoles={['manager']}><ManagerDashboard /></AppLayout>} />
                <Route path="/gestionnaire/alertes" element={<AppLayout allowedRoles={['manager']}><AlertsListPage /></AppLayout>} />
                <Route path="/gestionnaire/alertes/:id" element={<AppLayout allowedRoles={['manager']}><AlertDetailPage /></AppLayout>} />
                <Route path="/gestionnaire/ordonnances" element={<AppLayout allowedRoles={['manager']}><PrescriptionAlertsPage /></AppLayout>} />
                <Route path="/gestionnaire/aide" element={<AppLayout allowedRoles={['manager']}><HelpPage /></AppLayout>} />

                {/* Admin routes */}
                <Route path="/admin" element={<AppLayout allowedRoles={['admin']}><AdminSupervision /></AppLayout>} />
                <Route path="/admin/configuration" element={<AppLayout allowedRoles={['admin']}><AdminConfig /></AppLayout>} />
                <Route path="/admin/modeles" element={<AppLayout allowedRoles={['admin']}><AdminModels /></AppLayout>} />
                <Route path="/admin/audit" element={<AppLayout allowedRoles={['admin']}><AdminAuditLog /></AppLayout>} />
                <Route path="/admin/utilisateurs" element={<AppLayout allowedRoles={['admin']}><AdminUsers /></AppLayout>} />
                <Route path="/admin/aide" element={<AppLayout allowedRoles={['admin']}><HelpPage /></AppLayout>} />

                <Route path="*" element={<NotFoundPage />} />
              </Routes>
              </Suspense>
            </BrowserRouter>
          </ToastProvider>
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
