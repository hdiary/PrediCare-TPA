import { useState, useRef } from 'react';
import {
  UploadCloud, FileText, Plus, Trash2, CheckCircle2,
  AlertTriangle, ArrowLeft, File, Calendar, Banknote, ClipboardList, Clock3,
} from 'lucide-react';
import { Card, Button, Input, Skeleton } from '@/components/ui';
import { api } from '@/lib/api';
import { formatMGA } from '@/lib/format';
import { useToast } from '@/components/ui/Toast';
import type { InvoiceSubmissionResult, InvoicePrescription } from '@/lib/types';

const INVOICE_TYPES = [
  { value: 'CONSULTATION', label: 'Consultation' },
  { value: 'DENTAIRE', label: 'Dentaire' },
  { value: 'HOSPITALISATION', label: 'Hospitalisation' },
  { value: 'IMAGERIE', label: 'Imagerie' },
  { value: 'KINESITHERAPIE', label: 'Kinésithérapie' },
  { value: 'LABORATOIRE', label: 'Laboratoire' },
  { value: 'MATERNITE', label: 'Maternité' },
  { value: 'OPTIQUE', label: 'Optique' },
  { value: 'PHARMACIE', label: 'Pharmacie' },
];

interface InvoiceLineForm {
  id: string;
  code: string;
  label: string;
  quantity: number;
  unit_price: number;
}

export function DepositInvoicePage() {
  const [step, setStep] = useState<'form' | 'result'>('form');
  const [mode, setMode] = useState<'upload' | 'manual'>('upload');
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<InvoiceSubmissionResult | null>(null);
  const [lines, setLines] = useState<InvoiceLineForm[]>([
    { id: crypto.randomUUID(), code: '', label: '', quantity: 1, unit_price: 0 },
  ]);
  const [insuredPseudo, setInsuredPseudo] = useState('');
  const [careDate, setCareDate] = useState('');
  const [careTime, setCareTime] = useState('08:00');
  const [contractId, setContractId] = useState('');
  const [invoiceNumber, setInvoiceNumber] = useState('');
  const [invoiceType, setInvoiceType] = useState('CONSULTATION');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [hasPrescription, setHasPrescription] = useState(false);
  const [rxId, setRxId] = useState('');
  const [rxDate, setRxDate] = useState('');
  const [rxPrescriber, setRxPrescriber] = useState('');
  const [rxDiagnosis, setRxDiagnosis] = useState('');
  const [rxScan, setRxScan] = useState<File | null>(null);
  const rxScanInputRef = useRef<HTMLInputElement>(null);
  const { showToast } = useToast();

  const total = lines.reduce((sum, l) => sum + l.quantity * l.unit_price, 0);

  const handleFile = (f: File) => {
    if (f.size > 10 * 1024 * 1024) {
      showToast('Le fichier ne doit pas dépasser 10 Mo', 'error');
      return;
    }
    if (!f.name.match(/\.pdf$/i)) {
      showToast('Seul le format PDF est accepté pour le moment (ou utilisez la saisie manuelle)', 'error');
      return;
    }
    setFile(f);
  };

  const handleRxScan = (f: File) => {
    if (f.size > 10 * 1024 * 1024) {
      showToast('Le scan ne doit pas dépasser 10 Mo', 'error');
      return;
    }
    if (!f.name.match(/\.pdf$/i)) {
      showToast("Seul le format PDF est accepté pour l'ordonnance", 'error');
      return;
    }
    setRxScan(f);
  };

  const today = new Date().toISOString().slice(0, 10);
  const rxWarning =
    rxDate && rxDate > today
      ? "La date de prescription est dans le futur."
      : rxDate && mode === 'manual' && careDate && rxDate > careDate
        ? "La date de prescription est postérieure à la date des soins."
        : null;

  const addLine = () => setLines([...lines, { id: crypto.randomUUID(), code: '', label: '', quantity: 1, unit_price: 0 }]);
  const removeLine = (id: string) => setLines(lines.filter((l) => l.id !== id));
  const updateLine = (id: string, field: keyof InvoiceLineForm, value: string | number) =>
    setLines(lines.map((l) => (l.id === id ? { ...l, [field]: value } : l)));

  const handleSubmit = async () => {
    if (mode === 'manual') {
      if (!insuredPseudo || !careDate || !contractId || !invoiceNumber) {
        showToast('Veuillez remplir tous les champs requis', 'error');
        return;
      }
      if (lines.some((l) => !l.code.trim() || l.quantity < 1 || l.unit_price <= 0)) {
        showToast('Chaque ligne doit avoir un code, une quantité et un tarif positifs', 'error');
        return;
      }
    } else if (!file) {
      showToast('Veuillez sélectionner un fichier', 'error');
      return;
    }

    if (hasPrescription && (!rxId.trim() || !rxDate || !rxPrescriber.trim())) {
      showToast("Renseignez le n° d'ordonnance, sa date et le prescripteur", 'error');
      return;
    }
    const prescription: InvoicePrescription | undefined = hasPrescription
      ? {
          prescription_id: rxId.trim(),
          prescription_date: rxDate,
          prescriber_pseudo: rxPrescriber.trim(),
          ...(rxDiagnosis.trim() ? { diagnosis: rxDiagnosis.trim() } : {}),
        }
      : undefined;

    setSubmitting(true);
    try {
      let res: InvoiceSubmissionResult;
      let invoicePrescription = prescription;
      if (mode === 'upload' && file) {
        const formData = new FormData();
        formData.append('file', file);
        if (prescription) formData.append('prescription', JSON.stringify(prescription));
        if (prescription && rxScan) formData.append('prescription_scan', rxScan);
        res = await api.submitInvoice(formData);
      } else {
        if (prescription && rxScan) {
          const ordonnanceId = await api.createPrescriptionFromScan(
            insuredPseudo.trim(),
            invoiceType,
            rxScan,
            prescription,
          );
          invoicePrescription = { ...prescription, prescription_id: ordonnanceId };
        }
        res = await api.submitInvoice({
          insured_pseudo: insuredPseudo,
          care_date: careDate,
          care_time: careTime,
          contract_id: contractId,
          invoice_number: invoiceNumber,
          invoice_type: invoiceType,
          lines,
          ...(invoicePrescription ? { prescription: invoicePrescription } : {}),
        });
      }
      setResult(res); // résultat réel : accepté, ou rejeté avec les motifs renvoyés par l'API
      setStep('result');
      if (res.status === 'accepted') showToast('Facture déposée avec succès', 'success');
      if (res.status === 'pending') showToast('Facture reçue, en attente de traitement', 'success');
    } catch (err) {
      // erreur technique (réseau, serveur indisponible...) : on reste sur le formulaire
      showToast(err instanceof Error ? err.message : 'Erreur lors du dépôt', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    setStep('form');
    setFile(null);
    setResult(null);
    setCareTime('08:00');
    setContractId('');
    setInvoiceNumber('');
    setInvoiceType('CONSULTATION');
    setLines([{ id: crypto.randomUUID(), code: '', label: '', quantity: 1, unit_price: 0 }]);
    setInsuredPseudo('');
    setCareDate('');
    setHasPrescription(false);
    setRxId('');
    setRxDate('');
    setRxPrescriber('');
    setRxDiagnosis('');
    setRxScan(null);
  };

  if (step === 'result' && result) {
    return (
      <div className="max-w-2xl mx-auto">
        {result.status === 'accepted' ? (
          <Card className="p-8 text-center animate-slide-up">
            <div className="w-20 h-20 rounded-full bg-success-50 dark:bg-success-900/30 flex items-center justify-center mx-auto mb-6">
              <CheckCircle2 className="w-12 h-12 text-success-600 animate-check" />
            </div>
            <h2 className="text-2xl font-bold text-surface-800 dark:text-surface-100 mb-2">Facture acceptée</h2>
            <p className="text-sm text-surface-500 dark:text-surface-400 mb-6">
              Votre facture a été reçue et sera traitée. Vous recevrez une notification dès qu'elle sera traitée.
            </p>
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-2xl bg-surface-50 dark:bg-surface-700 mb-6">
              <FileText className="w-4 h-4 text-surface-400" />
              <span className="text-sm font-mono font-medium text-surface-700 dark:text-surface-200">{result.invoice_id}</span>
            </div>
            {result.warnings?.length ? (
              <div role="status" className="rounded-xl border border-warning-300 bg-warning-50 px-4 py-3 text-left text-sm text-warning-800 dark:border-warning-800 dark:bg-warning-900/30 dark:text-warning-200 mb-6">
                {result.warnings.map((warning) => <p key={warning}>{warning}</p>)}
              </div>
            ) : null}
            <div>
              <Button variant="outline" onClick={reset}>
                <ArrowLeft className="w-4 h-4" /> Déposer une autre facture
              </Button>
            </div>
          </Card>
        ) : result.status === 'pending' ? (
          <Card className="p-8 text-center animate-slide-up">
            <div className="w-20 h-20 rounded-full bg-warning-50 dark:bg-warning-900/30 flex items-center justify-center mx-auto mb-6">
              <Clock3 className="w-12 h-12 text-warning-600" />
            </div>
            <h2 className="text-2xl font-bold text-surface-800 dark:text-surface-100 mb-2">
              Facture en attente de traitement
            </h2>
            <p className="text-sm text-surface-500 dark:text-surface-400 mb-6">
              Votre facture a été reçue et sera examinée par un gestionnaire.
            </p>
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-2xl bg-surface-50 dark:bg-surface-700 mb-6">
              <FileText className="w-4 h-4 text-surface-400" />
              <span className="text-sm font-mono font-medium text-surface-700 dark:text-surface-200">{result.invoice_id}</span>
            </div>
            {result.warnings?.length ? (
              <div role="status" className="rounded-xl border border-warning-300 bg-warning-50 px-4 py-3 text-left text-sm text-warning-800 dark:border-warning-800 dark:bg-warning-900/30 dark:text-warning-200 mb-6">
                {result.warnings.map((warning) => <p key={warning}>{warning}</p>)}
              </div>
            ) : null}
            <div>
              <Button variant="outline" onClick={reset}>
                <ArrowLeft className="w-4 h-4" /> Déposer une autre facture
              </Button>
            </div>
          </Card>
        ) : (
          <Card className="p-8 animate-slide-up">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 rounded-2xl bg-danger-50 dark:bg-danger-900/30 flex items-center justify-center">
                <AlertTriangle className="w-6 h-6 text-danger-600" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-surface-800 dark:text-surface-100">Facture rejetée</h2>
                <p className="text-sm text-surface-500 dark:text-surface-400">Des erreurs ont été détectées dans votre facture.</p>
              </div>
            </div>

            <div className="rounded-2xl bg-danger-50 dark:bg-danger-900/20 border border-danger-200 dark:border-danger-800 p-4 mb-6">
              <p className="text-sm font-medium text-danger-700 dark:text-danger-300 mb-3">Erreurs détectées :</p>
              <ul className="space-y-2">
                {result.errors.map((err, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-danger-600 dark:text-danger-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-danger-500 mt-2 flex-shrink-0" />
                    <span><span className="font-mono text-xs">{err.field}</span> — {err.message}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="flex gap-3">
              <Button variant="primary" onClick={reset}>
                <ArrowLeft className="w-4 h-4" /> Corriger et renvoyer
              </Button>
            </div>
          </Card>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h2 className="text-xl font-bold text-surface-800 dark:text-surface-100 mb-1">Déposer une facture</h2>
        <p className="text-sm text-surface-500 dark:text-surface-400">Téléversez un fichier ou saisissez les actes manuellement.</p>
      </div>

      {/* Mode tabs */}
      <div className="flex gap-2">
        <button
          onClick={() => setMode('upload')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-2xl text-sm font-medium transition-all ${
            mode === 'upload'
              ? 'bg-primary-700 text-white shadow-sm'
              : 'bg-white dark:bg-surface-800 text-surface-600 dark:text-surface-300 border border-surface-300 dark:border-surface-700 hover:bg-surface-100 dark:hover:bg-surface-700'
          }`}
        >
          <UploadCloud className="w-4 h-4" /> Téléverser un fichier
        </button>
        <button
          onClick={() => setMode('manual')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-2xl text-sm font-medium transition-all ${
            mode === 'manual'
              ? 'bg-primary-700 text-white shadow-sm'
              : 'bg-white dark:bg-surface-800 text-surface-600 dark:text-surface-300 border border-surface-300 dark:border-surface-700 hover:bg-surface-100 dark:hover:bg-surface-700'
          }`}
        >
          <FileText className="w-4 h-4" /> Saisie manuelle
        </button>
      </div>

      <Card className="p-8">
        {mode === 'upload' ? (
          <div>
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setDragOver(false); if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]); }}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-2xl p-12 bg-primary-50/40 text-center cursor-pointer transition-all ${
                dragOver
                  ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                  : 'border-primary-200 dark:border-surface-600 hover:border-primary-400 hover:bg-primary-50/70 dark:hover:border-primary-500'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
              />
              {file ? (
                <div className="flex items-center justify-center gap-3">
                  <div className="w-12 h-12 rounded-2xl bg-primary-100 dark:bg-primary-700 flex items-center justify-center">
                    <File className="w-6 h-6 text-primary-600 dark:text-primary-300" />
                  </div>
                  <div className="text-left">
                    <p className="text-sm font-medium text-surface-700 dark:text-surface-200">{file.name}</p>
                    <p className="text-xs text-surface-400">{(file.size / 1024).toFixed(0)} Ko</p>
                  </div>
                </div>
              ) : (
                <>
                  <UploadCloud className="w-12 h-12 text-surface-300 dark:text-surface-600 mx-auto mb-3" />
                  <p className="text-sm font-medium text-surface-700 dark:text-surface-200 mb-1">
                    Glissez votre fichier ici ou cliquez pour parcourir
                  </p>
                  <p className="text-xs text-surface-400">Fichier PDF · 10 Mo max</p>
                </>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="N° assuré (pseudonymisé)"
                value={insuredPseudo}
                onChange={(e) => setInsuredPseudo(e.target.value)}
                placeholder="ASS-004217"
                required
              />
              <Input
                label="N° de contrat"
                value={contractId}
                onChange={(e) => setContractId(e.target.value)}
                placeholder="CTR-000001"
                required
              />
              <Input
                label="N° de facture"
                value={invoiceNumber}
                onChange={(e) => setInvoiceNumber(e.target.value)}
                placeholder="PRE214/2026/00001"
                required
              />
              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">Type de facture</label>
                <select
                  value={invoiceType}
                  onChange={(e) => setInvoiceType(e.target.value)}
                  className="w-full rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-900 px-3.5 py-2.5 text-sm text-surface-800 dark:text-surface-100"
                >
                  {INVOICE_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <Input
                label="Date de soins"
                type="date"
                value={careDate}
                onChange={(e) => setCareDate(e.target.value)}
                required
              />
              <Input
                label="Heure de soins"
                type="time"
                value={careTime}
                onChange={(e) => setCareTime(e.target.value)}
                required
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm font-medium text-surface-700 dark:text-surface-300">Lignes d'actes</p>
                <Button variant="ghost" size="sm" onClick={addLine}>
                  <Plus className="w-4 h-4" /> Ajouter une ligne
                </Button>
              </div>

              <div className="space-y-2">
                {lines.map((line, idx) => (
                  <div key={line.id} className="flex items-start gap-2 p-3 rounded-xl border border-surface-300/80 dark:border-surface-600 bg-surface-100 dark:bg-surface-700/50">
                    <div className="flex-1 min-w-0 grid grid-cols-6 md:grid-cols-12 gap-2">
                      <div className="col-span-2">
                        <label className="text-xs text-surface-400">Code</label>
                        <input
                          value={line.code}
                          onChange={(e) => updateLine(line.id, 'code', e.target.value)}
                          placeholder="CSC"
                          className="w-full rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-900 px-3.5 py-1.5 text-sm focus:border-primary-500"
                        />
                      </div>
                      <div className="col-span-4 md:col-span-5">
                        <label className="text-xs text-surface-400">Libellé</label>
                        <input
                          value={line.label}
                          onChange={(e) => updateLine(line.id, 'label', e.target.value)}
                          placeholder="Consultation cardiologie"
                          className="w-full rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-900 px-3.5 py-1.5 text-sm focus:border-primary-500"
                        />
                      </div>
                      <div className="col-span-2">
                        <label className="text-xs text-surface-400">Qté</label>
                        <input
                          type="number"
                          min={1}
                          value={line.quantity}
                          onChange={(e) => updateLine(line.id, 'quantity', parseInt(e.target.value) || 1)}
                          className="w-full rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-900 px-3.5 py-1.5 text-sm tabular-nums focus:border-primary-500"
                        />
                      </div>
                      <div className="col-span-4 md:col-span-3">
                        <label className="text-xs text-surface-400">Tarif (MGA)</label>
                        <input
                          type="number"
                          step="0.01"
                          value={line.unit_price}
                          onChange={(e) => updateLine(line.id, 'unit_price', parseFloat(e.target.value) || 0)}
                          className="w-full rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-900 px-3.5 py-1.5 text-sm tabular-nums focus:border-primary-500"
                        />
                      </div>
                    </div>
                    <button
                      onClick={() => removeLine(line.id)}
                      className="mt-5 p-1.5 rounded-full text-surface-400 hover:text-danger-500 hover:bg-danger-50 dark:hover:bg-danger-900/30"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>

              <div className="flex justify-end">
                <div className="rounded-xl bg-surface-50 dark:bg-surface-700 px-[18px] py-4 flex items-center gap-2">
                  <Banknote className="w-4 h-4 text-surface-400" />
                  <span className="text-sm text-surface-500">Total :</span>
                  <span className="text-lg font-bold tabular-nums text-surface-800 dark:text-surface-100">{formatMGA(total)}</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </Card>

      <Card className="p-8">
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={hasPrescription}
            onChange={(e) => setHasPrescription(e.target.checked)}
            className="mt-1 w-4 h-4 accent-primary-700"
          />
          <div>
            <p className="text-sm font-medium text-surface-800 dark:text-surface-100 flex items-center gap-2">
              <ClipboardList className="w-4 h-4 text-surface-400" /> Cette facture est liée à une ordonnance
            </p>
            <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
              Requise pour les médicaments et les actes soumis à prescription.
            </p>
          </div>
        </label>

        {hasPrescription && (
          <div className="mt-6 space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="N° d'ordonnance"
                value={rxId}
                onChange={(e) => setRxId(e.target.value)}
                placeholder="ORD-0041872"
                required
              />
              <Input
                label="Date de prescription"
                type="date"
                value={rxDate}
                onChange={(e) => setRxDate(e.target.value)}
                required
              />
              <Input
                label="Prescripteur (pseudonymisé ou n° ONM)"
                value={rxPrescriber}
                onChange={(e) => setRxPrescriber(e.target.value)}
                placeholder="PRS-0078"
                required
              />
              <Input
                label="Diagnostic (facultatif)"
                value={rxDiagnosis}
                onChange={(e) => setRxDiagnosis(e.target.value)}
                placeholder="Hypertension artérielle"
              />
            </div>

            {rxWarning && (
              <p className="flex items-center gap-2 text-sm text-warning-700 dark:text-warning-200">
                <AlertTriangle className="w-4 h-4 shrink-0" /> {rxWarning} Vérifiez la saisie : l'ordonnance sera contrôlée.
              </p>
            )}

            <div>
              <p className="text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                Scan ou photo de l'ordonnance (facultatif)
              </p>
              <input
                ref={rxScanInputRef}
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleRxScan(e.target.files[0])}
              />
              {rxScan ? (
                <div className="flex items-center justify-between gap-3 p-3 rounded-xl border border-surface-300/80 dark:border-surface-600 bg-surface-100 dark:bg-surface-700/50">
                  <div className="flex items-center gap-3 min-w-0">
                    <File className="w-5 h-5 text-primary-600 dark:text-primary-300 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-surface-700 dark:text-surface-200 truncate">{rxScan.name}</p>
                      <p className="text-xs text-surface-400">{(rxScan.size / 1024).toFixed(0)} Ko</p>
                    </div>
                  </div>
                  <button
                    onClick={() => setRxScan(null)}
                    aria-label="Retirer le scan"
                    className="p-1.5 rounded-full text-surface-400 hover:text-danger-500 hover:bg-danger-50 dark:hover:bg-danger-900/30"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => rxScanInputRef.current?.click()}
                  className="w-full border-2 border-dashed border-primary-200 dark:border-surface-600 rounded-2xl p-6 text-center hover:border-primary-400 hover:bg-primary-50/70 dark:hover:border-primary-500 transition-all"
                >
                  <UploadCloud className="w-8 h-8 text-surface-300 dark:text-surface-600 mx-auto mb-2" />
                  <p className="text-sm text-surface-600 dark:text-surface-300">Ajouter le scan de l'ordonnance</p>
                  <p className="text-xs text-surface-400">PDF, JPG ou PNG · 10 Mo max · conservé comme justificatif</p>
                </button>
              )}
            </div>
          </div>
        )}
      </Card>

      <div className="flex justify-end">
        <Button size="lg" onClick={handleSubmit} disabled={submitting}>
          {submitting ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Dépôt en cours...
            </>
          ) : (
            'Déposer la facture'
          )}
        </Button>
      </div>
    </div>
  );
}
