import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Mail, User, Building2, CheckCircle2, AlertCircle, ShieldCheck } from 'lucide-react';
import { AuthLayout } from '@/components/AuthLayout';
import { PasswordField, PasswordRules } from '@/components/PasswordField';
import { Button, Input, Spinner } from '@/components/ui';
import { api } from '@/lib/api';
import { isPasswordValid, passwordChecks } from '@/lib/password';
import type { RegisterPayload, SignupRole } from '@/lib/types';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function ageFrom(iso: string): number {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return -1;
  const t = new Date();
  let age = t.getFullYear() - d.getFullYear();
  const m = t.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && t.getDate() < d.getDate())) age--;
  return age;
}

export function RegisterPage() {
  const navigate = useNavigate();
  const [role, setRole] = useState<SignupRole>('insured');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [policyNumber, setPolicyNumber] = useState('');
  const [birthDate, setBirthDate] = useState('');
  const [organization, setOrganization] = useState('');
  const [providerCode, setProviderCode] = useState('');
  const [taxId, setTaxId] = useState('');
  const [onm, setOnm] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [consent, setConsent] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const validate = (): Record<string, string> => {
    const e: Record<string, string> = {};
    if (!EMAIL_RE.test(email)) e.email = "Adresse e-mail invalide";
    if (role === 'insured') {
      if (!firstName.trim()) e.firstName = "Prénom requis";
      if (!lastName.trim()) e.lastName = "Nom requis";
      if (!/^POL-\d{4}-\d{4}$/i.test(policyNumber.trim())) e.policyNumber = "Format attendu : POL-2019-1084";
      const age = ageFrom(birthDate);
      if (age < 0) e.birthDate = "Date de naissance requise";
      else if (age < 18) e.birthDate = "Vous devez avoir 18 ans ou plus";
    } else {
      if (!organization.trim()) e.organization = "Nom de l'établissement requis";
      if (!/^PRE-\d{5}$/i.test(providerCode.trim())) e.providerCode = "Format attendu : PRE-00001";
      if (!/^\d{10}$/.test(taxId.trim())) e.taxId = "Le NIF comporte 10 chiffres";
      if (onm.trim() && !/^ONM-\d{5}$/i.test(onm.trim())) e.onm = "Format attendu : ONM-12345";
    }
    if (!isPasswordValid(password, email)) e.password = "Le mot de passe ne respecte pas toutes les règles";
    if (confirm !== password) e.confirm = "Les mots de passe ne correspondent pas";
    if (!consent) e.consent = "Vous devez accepter pour créer un compte";
    return e;
  };

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setServerError('');
    const e = validate();
    setErrors(e);
    if (Object.keys(e).length > 0) return;

    const base = { role, email: email.trim(), password, consent };
    const payload: RegisterPayload =
      role === 'insured'
        ? { ...base, first_name: firstName.trim(), last_name: lastName.trim(), policy_number: policyNumber.trim().toUpperCase(), birth_date: birthDate }
        : {
            ...base,
            organization_name: organization.trim(),
            provider_code: providerCode.trim().toUpperCase(),
            tax_id: taxId.trim(),
            ...(onm.trim() ? { onm_number: onm.trim().toUpperCase() } : {}),
          };

    setLoading(true);
    try {
      await api.register(payload);
      setDone(true);
    } catch (err) {
      setServerError(err instanceof Error ? err.message : "Impossible de créer le compte");
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <AuthLayout title="Demande envoyée">
        <div className="flex flex-col items-center text-center gap-4">
          <CheckCircle2 className="w-12 h-12 text-success-600 dark:text-success-300" />
          <p className="text-sm text-surface-600 dark:text-surface-300">
            Votre demande de création de compte est enregistrée. Nous vérifions votre rattachement, puis vous recevrez un e-mail à l'adresse{' '}
            <strong>{email}</strong> dès que votre compte sera activé.
          </p>
          <Button className="w-full" size="lg" onClick={() => navigate('/login')}>
            Retour à la connexion
          </Button>
        </div>
      </AuthLayout>
    );
  }

  const roleButton = (value: SignupRole, label: string, icon: React.ReactNode) => (
    <button
      type="button"
      aria-pressed={role === value}
      onClick={() => { setRole(value); setErrors({}); }}
      className={`flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all ${
        role === value
          ? 'bg-primary-700 text-white'
          : 'bg-white dark:bg-surface-800 text-surface-600 dark:text-surface-300 border border-surface-300 dark:border-surface-700 hover:bg-surface-100 dark:hover:bg-surface-700'
      }`}
    >
      {icon} {label}
    </button>
  );

  return (
    <AuthLayout
      title="Créer un compte"
      subtitle="Rejoignez PrediCare TPA en quelques minutes."
      footer={
        <>
          Déjà un compte ?{' '}
          <Link to="/login" className="text-primary-700 dark:text-primary-400 underline">Se connecter</Link>
        </>
      }
    >
      {serverError && (
        <div className="mb-4 flex items-start gap-2 p-3 rounded-2xl bg-danger-50 dark:bg-danger-900/30 border border-danger-200 dark:border-danger-800 text-sm text-danger-700 dark:text-danger-300">
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>{serverError}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        <div>
          <p className="block text-sm font-medium text-surface-700 dark:text-surface-200 mb-2">Je suis</p>
          <div className="flex gap-2">
            {roleButton('insured', 'Assuré', <User className="w-4 h-4" />)}
            {roleButton('provider', 'Professionnel de santé', <Building2 className="w-4 h-4" />)}
          </div>
          <p className="mt-2 text-xs text-surface-500 dark:text-surface-400">
            Les comptes gestionnaire et administrateur sont créés par un administrateur.
          </p>
        </div>

        {role === 'insured' ? (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input label="Prénom" value={firstName} onChange={(e) => setFirstName(e.target.value)} error={errors.firstName} required />
              <Input label="Nom" value={lastName} onChange={(e) => setLastName(e.target.value)} error={errors.lastName} required />
            </div>
            <Input label="Numéro de police du contrat" value={policyNumber} onChange={(e) => setPolicyNumber(e.target.value)} placeholder="POL-2019-1084" error={errors.policyNumber} required />
            <Input label="Date de naissance" type="date" value={birthDate} onChange={(e) => setBirthDate(e.target.value)} error={errors.birthDate} required />
          </>
        ) : (
          <>
            <Input label="Nom de l'établissement ou du cabinet" value={organization} onChange={(e) => setOrganization(e.target.value)} error={errors.organization} required />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input label="Code prestataire" value={providerCode} onChange={(e) => setProviderCode(e.target.value)} placeholder="PRE-00001" error={errors.providerCode} required />
              <Input label="NIF" value={taxId} onChange={(e) => setTaxId(e.target.value)} placeholder="10 chiffres" error={errors.taxId} required />
            </div>
            <Input label="N° ONM (médecins, facultatif)" value={onm} onChange={(e) => setOnm(e.target.value)} placeholder="ONM-12345" error={errors.onm} />
          </>
        )}

        <Input label="Adresse e-mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="vous@exemple.fr" error={errors.email} required icon={<Mail className="w-4 h-4" />} />

        <div>
          <PasswordField id="password" label="Mot de passe" value={password} onChange={setPassword} autoComplete="new-password" error={errors.password} />
          <PasswordRules checks={passwordChecks(password, email)} visible={password.length > 0} />
        </div>
        <PasswordField id="confirm" label="Confirmer le mot de passe" value={confirm} onChange={setConfirm} autoComplete="new-password" error={errors.confirm} />

        <div>
          <label className="flex items-start gap-3 cursor-pointer">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1 w-4 h-4 accent-primary-700 shrink-0" />
            <span className="text-xs text-surface-600 dark:text-surface-300">
              J'accepte que mes données soient traitées pour gérer mon compte. Les identités sont chiffrées et séparées du reste des données.
            </span>
          </label>
          {errors.consent && <p className="mt-1.5 text-xs text-danger-600 dark:text-danger-300">{errors.consent}</p>}
        </div>

        <Button type="submit" className="w-full" size="lg" disabled={loading}>
          {loading ? (<><Spinner className="w-4 h-4" /> Envoi...</>) : (<><ShieldCheck className="w-4 h-4" /> Créer mon compte</>)}
        </Button>
      </form>
    </AuthLayout>
  );
}
