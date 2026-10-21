import { useState, useEffect } from 'react';
import { Settings, Save, Slack, Mail, AlertTriangle, Info } from 'lucide-react';
import { Card, Button, Skeleton, ErrorState } from '@/components/ui';
import { useToast } from '@/components/ui/Toast';
import { api, userErrorMessage } from '@/lib/api';
import type { AdminSettings } from '@/lib/types';

export function AdminConfig() {
  const { showToast } = useToast();
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [original, setOriginal] = useState<AdminSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testingEmail, setTestingEmail] = useState(false);

  useEffect(() => {
    api.getAdminSettings().then((data) => {
      setSettings(data);
      setOriginal(data);
      setLoading(false);
    }).catch(() => { setError(true); setLoading(false); });
  }, []);

  if (loading) return <div className="space-y-5"><Skeleton className="h-96" /></div>;
  if (error || !settings) return <ErrorState message="Impossible de charger la configuration." />;

  const hasChanges = JSON.stringify(settings) !== JSON.stringify(original);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.updateAdminSettings(settings);
      setOriginal(settings);
      showToast('Configuration enregistrée', 'success');
    } catch (err) {
      showToast(userErrorMessage(err, 'La configuration n’a pas pu être enregistrée. Réessayez.'), 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleTestEmail = async () => {
    setTestingEmail(true);
    try {
      const result = await api.sendAdminEmailTest();
      showToast(result.detail, 'success');
    } catch (err) {
      showToast(userErrorMessage(err, "Le message de test n’a pas pu être envoyé. Vérifiez l’adresse puis réessayez."), 'error');
    } finally {
      setTestingEmail(false);
    }
  };

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h2 className="text-xl font-bold text-surface-800 dark:text-surface-100 mb-1">Configuration</h2>
        <p className="text-sm text-surface-500 dark:text-surface-400">Paramètres de détection et notifications.</p>
      </div>

      {/* Unsaved changes warning */}
      {hasChanges && (
        <div className="flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-warning-50 dark:bg-warning-900/30 border border-warning-200 dark:border-warning-800 animate-fade-in">
          <AlertTriangle className="w-4 h-4 text-warning-600 flex-shrink-0" />
          <p className="text-sm text-warning-700 dark:text-warning-300">Vous avez des modifications non enregistrées.</p>
        </div>
      )}

      {/* Alert threshold */}
      <Card className="p-8">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-lg bg-primary-50 dark:bg-primary-900/30 flex items-center justify-center">
            <Settings className="w-5 h-5 text-primary-700 dark:text-primary-400" />
          </div>
          <div>
            <h3 className="font-semibold text-surface-800 dark:text-surface-100">Seuil d'alerte</h3>
            <p className="text-xs text-surface-400">Score minimum pour déclencher une alerte</p>
          </div>
        </div>

        <div className="space-y-5">
          <div className="flex items-center gap-4">
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={settings.alert_threshold}
              onChange={(e) => setSettings({ ...settings, alert_threshold: parseFloat(e.target.value) })}
              className="flex-1 accent-primary-600"
            />
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={0}
                max={1}
                step={0.01}
                value={settings.alert_threshold}
                onChange={(e) => setSettings({ ...settings, alert_threshold: parseFloat(e.target.value) || 0 })}
                className="w-20 rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-900 px-3.5 py-1.5 text-sm tabular-nums text-center focus:border-primary-500"
              />
            </div>
          </div>

          <div className="flex items-start gap-2 p-3 rounded-2xl bg-kraft-50 dark:bg-kraft-900/20 border border-kraft-200 dark:border-kraft-800">
            <Info className="w-4 h-4 text-kraft-700 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-kraft-700 dark:text-kraft-300">Les modifications s'appliquent immédiatement.</p>
          </div>
        </div>
      </Card>

      {/* Notification channels */}
      <Card className="p-8">
        <h3 className="font-semibold text-surface-800 dark:text-surface-100 mb-5">Canaux de notification</h3>

        {/* Slack */}
        <div className="space-y-3 pb-5 border-b border-surface-300/60 dark:border-surface-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-surface-100 dark:bg-surface-700 flex items-center justify-center">
                <Slack className="w-4 h-4 text-surface-500" />
              </div>
              <div>
                <p className="text-sm font-medium text-surface-700 dark:text-surface-200">Slack</p>
                <p className="text-xs text-surface-400">Notifications envoyées sur un canal Slack</p>
              </div>
            </div>
            <button
              onClick={() => setSettings({
                ...settings,
                channels: { ...settings.channels, slack: { ...settings.channels.slack, enabled: !settings.channels.slack.enabled } },
              })}
              className={`relative w-11 h-6 rounded-full transition-all ${settings.channels.slack.enabled ? 'bg-primary-600' : 'bg-surface-300 dark:bg-surface-600'}`}
            >
              <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all ${settings.channels.slack.enabled ? 'left-5.5' : 'left-0.5'}`} style={{ left: settings.channels.slack.enabled ? '22px' : '2px' }} />
            </button>
          </div>
          {settings.channels.slack.enabled && (
            <div className="ml-12">
              <label className="text-xs text-surface-400 mb-1 block">Canal Slack (ex. #predicare-alertes)</label>
              <input
                type="text"
                value={settings.channels.slack.channel}
                onChange={(e) => setSettings({
                  ...settings,
                  channels: { ...settings.channels, slack: { ...settings.channels.slack, channel: e.target.value } },
                })}
                placeholder="#predicare-alertes"
                className="w-full rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-900 px-3 py-2 text-sm focus:border-primary-500"
              />
            </div>
          )}
        </div>

        {/* Email */}
        <div className="space-y-3 pt-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-surface-100 dark:bg-surface-700 flex items-center justify-center">
                <Mail className="w-4 h-4 text-surface-500" />
              </div>
              <div>
                <p className="text-sm font-medium text-surface-700 dark:text-surface-200">Email</p>
                <p className="text-xs text-surface-400">Résumé des alertes envoyé par email</p>
              </div>
            </div>
            <button
              onClick={() => setSettings({
                ...settings,
                channels: { ...settings.channels, email: { ...settings.channels.email, enabled: !settings.channels.email.enabled } },
              })}
              className={`relative w-11 h-6 rounded-full transition-all ${settings.channels.email.enabled ? 'bg-primary-600' : 'bg-surface-300 dark:bg-surface-600'}`}
            >
              <span className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all" style={{ left: settings.channels.email.enabled ? '22px' : '2px' }} />
            </button>
          </div>
          {settings.channels.email.enabled && (
            <div className="ml-12">
              <label className="text-xs text-surface-400 mb-1 block">Adresses de réception (séparées par des virgules)</label>
              <input
                type="text"
                inputMode="email"
                value={settings.channels.email.address}
                onChange={(e) => setSettings({
                  ...settings,
                  channels: { ...settings.channels, email: { ...settings.channels.email, address: e.target.value } },
                })}
                placeholder="gestion@exemple.mg, alertes@exemple.mg"
                className="w-full rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-900 px-3 py-2 text-sm focus:border-primary-500"
              />
              <div className="mt-3 flex justify-end">
                <Button
                  variant="outline"
                  onClick={handleTestEmail}
                  disabled={testingEmail || saving || hasChanges || !settings.channels.email.address.trim()}
                >
                  <Mail className="w-4 h-4" />
                  {testingEmail ? 'Envoi du test...' : 'Tester l’envoi'}
                </Button>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Save button */}
      {/* Save button */}
      <div className="flex justify-end gap-3 pt-2">
        <Button variant="ghost" onClick={() => setSettings(original)} disabled={!hasChanges || saving}>
          Annuler
        </Button>
        <Button onClick={handleSave} disabled={!hasChanges || saving}>
          <Save className="w-4 h-4" />
          {saving ? 'Enregistrement...' : 'Enregistrer'}
        </Button>
      </div>
    </div>
  );
}
