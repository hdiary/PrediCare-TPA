import { Component, type ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-surface-50 dark:bg-surface-900 px-4">
          <div className="text-center max-w-md">
            <div className="w-20 h-20 rounded-3xl bg-danger-50 dark:bg-danger-900/30 flex items-center justify-center mx-auto mb-6">
              <AlertTriangle className="w-10 h-10 text-danger-500" />
            </div>
            <h1 className="text-xl font-bold text-surface-800 dark:text-surface-100 mb-2">Une erreur est survenue</h1>
            <p className="text-sm text-surface-500 dark:text-surface-400 mb-6">
              Une erreur inattendue s'est produite. Veuillez recharger la page.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-primary-700 hover:bg-primary-800 text-white font-medium text-sm transition-all"
            >
              Recharger la page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
