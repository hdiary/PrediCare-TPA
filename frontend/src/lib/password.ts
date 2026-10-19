/** Règles de mot de passe côté interface. Le serveur DOIT les revalider : ce n'est qu'une aide à la saisie. */
export interface PasswordCheck {
  label: string;
  ok: boolean;
}

export const PASSWORD_MIN_LENGTH = 12;

export function passwordChecks(password: string, email = ''): PasswordCheck[] {
  const local = email.split('@')[0]?.toLowerCase() ?? '';
  const checks: PasswordCheck[] = [
    { label: `${PASSWORD_MIN_LENGTH} caractères minimum`, ok: password.length >= PASSWORD_MIN_LENGTH },
    { label: 'Une majuscule', ok: /[A-Z]/.test(password) },
    { label: 'Une minuscule', ok: /[a-z]/.test(password) },
    { label: 'Un chiffre', ok: /\d/.test(password) },
  ];
  if (local.length >= 4) {
    checks.push({ label: "Ne contient pas votre adresse e-mail", ok: !password.toLowerCase().includes(local) });
  }
  return checks;
}

export const isPasswordValid = (password: string, email = ''): boolean =>
  passwordChecks(password, email).every((c) => c.ok);
