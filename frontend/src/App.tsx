import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth, getRoleHome } from '@/lib/auth';
import { ThemeProvider } from '@/lib/theme';
import { ToastProvider } from '@/components/ui/Toast';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { AppLayout } from '@/components/AppLayout';
import { LoginPage } from '@/pages/LoginPage';
import { NotFoundPage } from '@/pages/NotFound';
import { AccessDeniedPage } from '@/pages/AccessDenied';
import { HelpPage } from '@/pages/HelpPage';

// Insured pages
import { ChatPage } from '@/pages/insured/ChatPage';
import { ReimbursementsPage } from '@/pages/insured/ReimbursementsPage';

// Provider pages
import { DepositInvoicePage } from '@/pages/provider/DepositInvoicePage';
import { ProviderInvoicesPage } from '@/pages/provider/ProviderInvoicesPage';

// Manager pages
import { ManagerDashboard } from '@/pages/manager/ManagerDashboard';
import { AlertsListPage } from '@/pages/manager/AlertsListPage';
import { AlertDetailPage } from '@/pages/manager/AlertDetailPage';

// Admin pages
import { AdminSupervision } from '@/pages/admin/AdminSupervision';
import { AdminConfig } from '@/pages/admin/AdminConfig';
import { AdminModels } from '@/pages/admin/AdminModels';
import { AdminAuditLog } from '@/pages/admin/AdminAuditLog';
import { AdminUsers } from '@/pages/admin/AdminUsers';

function RootRedirect() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={getRoleHome(user.role)} replace />;
}

function LoginRoute() {
  const { user, loading } = useAuth();
  if (loading) return null;
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
              <Routes>
                <Route path="/" element={<RootRedirect />} />
                <Route path="/login" element={<LoginRoute />} />
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
            </BrowserRouter>
          </ToastProvider>
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
