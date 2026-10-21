import { useEffect, useState, type ChangeEvent } from 'react';
import { BookOpen, FileText, RefreshCw, Upload } from 'lucide-react';
import { Badge, Button, Card, ErrorState, Skeleton } from '@/components/ui';
import { useToast } from '@/components/ui/Toast';
import { ApiError, api } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import type { RagCorpusDocument } from '@/lib/types';

const SCOPE_LABELS: Record<RagCorpusDocument['scope'], string> = {
  global: 'Document général',
  formula: 'Formule',
  contract: 'Contrat',
};

export function ManagerRagCorpusPage() {
  const { showToast } = useToast();
  const [documents, setDocuments] = useState<RagCorpusDocument[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(false);

  const loadDocuments = async () => {
    setError(false);
    try {
      setDocuments(await api.getRagCorpus());
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDocuments();
  }, []);

  const selectFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    if (file && (file.type !== 'application/pdf' || file.size > 20 * 1024 * 1024)) {
      showToast('Sélectionnez un PDF de 20 Mo maximum.', 'error');
      event.target.value = '';
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
  };

  const upload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    try {
      const result = await api.addRagCorpusDocument(selectedFile);
      showToast(
        result.already_indexed
          ? 'Ce document est déjà indexé.'
          : `Document ajouté et indexé (${result.chunks} passages).`,
        'success',
      );
      setSelectedFile(null);
      await loadDocuments();
    } catch (exception) {
      showToast(
        exception instanceof ApiError ? exception.message : "Échec de l'indexation du document.",
        'error',
      );
    } finally {
      setUploading(false);
    }
  };

  if (loading) return <div className="space-y-4"><Skeleton className="h-20" /><Skeleton className="h-64" /></div>;
  if (error) return <ErrorState message="Impossible de charger le corpus documentaire." onRetry={() => void loadDocuments()} />;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-surface-800 dark:text-surface-100">Corpus documentaire RAG</h2>
          <p className="mt-1 text-sm text-surface-500 dark:text-surface-400">
            Ajoutez des PDF qui seront indexés et disponibles pour l’assistant.
          </p>
        </div>
        <Button variant="outline" onClick={() => void loadDocuments()}>
          <RefreshCw className="h-4 w-4" /> Actualiser
        </Button>
      </div>

      <Card className="p-6">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-primary-100 p-2 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300">
            <BookOpen className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold text-surface-800 dark:text-surface-100">Ajouter un document</h3>
            <p className="mt-1 text-sm text-surface-500 dark:text-surface-400">
              PDF de 20 Mo maximum. Un nom <code>CP_CTR-000123.pdf</code> rattache le document au contrat ;
              <code> Conditions_Generales_PREMIUM.pdf</code> le rattache à une formule. Les autres PDF sont généraux.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <input
                type="file"
                accept="application/pdf,.pdf"
                onChange={selectFile}
                aria-label="Choisir un document PDF"
                className="block max-w-full text-sm text-surface-600 file:mr-3 file:rounded-lg file:border-0 file:bg-surface-100 file:px-4 file:py-2 file:font-medium dark:text-surface-300 dark:file:bg-surface-700"
              />
              <Button disabled={!selectedFile || uploading} onClick={() => void upload()}>
                <Upload className="h-4 w-4" />
                {uploading ? 'Indexation en cours…' : 'Ajouter et indexer'}
              </Button>
            </div>
            {selectedFile && (
              <p className="mt-2 text-xs text-surface-400">
                {selectedFile.name} · {(selectedFile.size / (1024 * 1024)).toFixed(1)} Mo
              </p>
            )}
          </div>
        </div>
      </Card>

      <Card className="overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-surface-300/60 px-6 py-4 dark:border-surface-700">
          <div>
            <h3 className="font-semibold text-surface-800 dark:text-surface-100">Documents indexés</h3>
            <p className="text-xs text-surface-400">{documents.length} document(s) affiché(s), maximum 200</p>
          </div>
        </div>
        {documents.length === 0 ? (
          <p className="p-6 text-sm text-surface-500">Aucun document n’est indexé dans le corpus.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-surface-100 text-xs uppercase text-surface-500 dark:bg-surface-700/50 dark:text-surface-300">
                <tr>
                  <th className="px-6 py-3">Document</th>
                  <th className="px-6 py-3">Portée</th>
                  <th className="px-6 py-3 text-right">Pages</th>
                  <th className="px-6 py-3 text-right">Passages</th>
                  <th className="px-6 py-3">Indexé le</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-300/60 dark:divide-surface-700/60">
                {documents.map((document) => (
                  <tr key={document.id} className="text-sm text-surface-600 dark:text-surface-300">
                    <td className="px-6 py-4">
                      <span className="flex items-center gap-2 font-medium text-surface-800 dark:text-surface-100">
                        <FileText className="h-4 w-4 shrink-0 text-surface-400" />
                        {document.filename}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <Badge>{SCOPE_LABELS[document.scope]}</Badge>
                      {(document.contrat_id || document.formule) && (
                        <span className="ml-2 text-xs text-surface-400">{document.contrat_id || document.formule}</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right tabular-nums">{document.n_pages ?? '—'}</td>
                    <td className="px-6 py-4 text-right tabular-nums">{document.chunks}</td>
                    <td className="px-6 py-4 whitespace-nowrap">{formatDateTime(document.ingested_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
