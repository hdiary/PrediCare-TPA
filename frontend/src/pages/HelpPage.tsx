import { useParams, Link } from 'react-router-dom';
import { HelpCircle, MessageSquare, Receipt, FileText, AlertTriangle, Settings, Server } from 'lucide-react';
import { Card } from '@/components/ui';
import type { Role } from '@/lib/types';

const HELP_CONTENT: Record<Role, { title: string; icon: React.ReactNode; tips: { title: string; description: string }[] }[]> = {
  insured: [
    {
      title: 'Mon assistant',
      icon: <MessageSquare className="w-5 h-5" />,
      tips: [
        { title: 'Posez des questions', description: 'L\'assistant IA peut répondre aux questions sur votre contrat, vos plafonds, les exclusions et l\'état de vos dossiers.' },
        { title: 'Consultez les sources', description: 'Chaque réponse est accompagnée de sources citées. Cliquez sur une source pour voir l\'excerpt du document.' },
        { title: 'Évaluez les réponses', description: 'Utilisez les pouces levés/baissés pour indiquer si une réponse vous a été utile.' },
        { title: 'Nouvelle conversation', description: 'Cliquez sur "Nouvelle conversation" pour repartir de zéro. Vos conversations passées sont conservées.' },
      ],
    },
    {
      title: 'Mes remboursements',
      icon: <Receipt className="w-5 h-5" />,
      tips: [
        { title: 'Filtrez par statut', description: 'Utilisez les filtres pour voir uniquement les factures payées, en cours ou rejetées.' },
        { title: 'Détail d\'une facture', description: 'Cliquez sur une ligne pour voir le détail : montants, actes, reste à charge et suivi.' },
      ],
    },
  ],
  provider: [
    {
      title: 'Déposer une facture',
      icon: <FileText className="w-5 h-5" />,
      tips: [
        { title: 'Téléversement ou saisie', description: 'Déposez un fichier CSV, JSON ou PDF, ou saisissez les actes manuellement avec le formulaire.' },
        { title: 'Lignes d\'actes', description: 'Ajoutez ou supprimez des lignes. Le total se calcule automatiquement.' },
        { title: 'Confirmation', description: 'Après le dépôt, vous recevez un numéro de facture et le statut (acceptée ou rejetée avec erreurs).' },
      ],
    },
    {
      title: 'Mes factures',
      icon: <Receipt className="w-5 h-5" />,
      tips: [
        { title: 'Suivi du statut', description: 'Consultez le statut de chaque facture : reçue, en cours de contrôle, acceptée, rejetée, payée.' },
        { title: 'Recherche', description: 'Recherchez par numéro de facture ou par assuré pour retrouver rapidement une facture.' },
      ],
    },
  ],
  manager: [
    {
      title: 'Tableau de bord',
      icon: <AlertTriangle className="w-5 h-5" />,
      tips: [
        { title: 'KPIs en temps réel', description: 'Suivez les factures traitées, le montant économisé, le taux de détection et les alertes en attente.' },
        { title: 'Graphiques', description: 'Visualisez l\'évolution hebdomadaire des factures, alertes et montants économisés.' },
        { title: 'Alertes prioritaires', description: 'Accédez directement aux alertes les plus récentes en attente de traitement.' },
      ],
    },
    {
      title: 'Alertes',
      icon: <AlertTriangle className="w-5 h-5" />,
      tips: [
        { title: 'Tri et filtrage', description: 'Triez par score, montant ou date. Filtrez par statut et recherchez par prestataire ou assuré.' },
        { title: 'Détail de l\'alerte', description: 'Cliquez sur une ligne pour voir l\'explication complète : score, facteurs SHAP, contrôles de prescription.' },
        { title: 'Décision tracée', description: 'Chaque décision (valider/rejeter) nécessite un commentaire et est enregistrée dans le journal d\'audit.' },
      ],
    },
  ],
  admin: [
    {
      title: 'Supervision',
      icon: <Server className="w-5 h-5" />,
      tips: [
        { title: 'État des services', description: 'Vérifiez en temps réel l\'état de l\'API, de la base de données, du modèle, de n8n et de la base vectorielle.' },
        { title: 'Métriques', description: 'Surveillez la latence p95, le taux de requêtes, le taux d\'erreur et la dérive du modèle (PSI).' },
        { title: 'Alerte de dérive', description: 'Une bannière d\'alerte s\'affiche si le PSI dépasse le seuil de 0,10.' },
      ],
    },
    {
      title: 'Configuration',
      icon: <Settings className="w-5 h-5" />,
      tips: [
        { title: 'Seuil d\'alerte', description: 'Ajustez le score minimum de déclenchement. L\'impact estimé s\'affiche en temps réel.' },
        { title: 'Notifications', description: 'Activez et configurez les canaux Slack et Email pour recevoir les alertes.' },
      ],
    },
    {
      title: 'Modèles et audit',
      icon: <FileText className="w-5 h-5" />,
      tips: [
        { title: 'Gestion des versions', description: 'Activez, archivez et comparez les versions du modèle. Le retour arrière est inclus.' },
        { title: 'Journal d\'audit', description: 'Consultez et exportez toutes les actions effectuées sur la plateforme.' },
      ],
    },
  ],
};

const ROLE_HOME: Record<Role, string> = {
  insured: '/assurant',
  provider: '/professionnel',
  manager: '/gestionnaire',
  admin: '/admin',
};

export function HelpPage() {
  const params = useParams<{ role: string }>();
  const role = (params.role || 'insured') as Role;
  const sections = HELP_CONTENT[role] || [];
  const home = ROLE_HOME[role] || '/';

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h2 className="text-xl font-bold text-surface-800 dark:text-surface-100 mb-1">Aide</h2>
        <p className="text-sm text-surface-500 dark:text-surface-400">Guides d'utilisation pour votre espace.</p>
      </div>

      {sections.map((section) => (
        <Card key={section.title} className="p-6">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-10 h-10 rounded-lg bg-primary-50 dark:bg-primary-900/30 flex items-center justify-center text-primary-600">
              {section.icon}
            </div>
            <h3 className="font-semibold text-surface-800 dark:text-surface-100">{section.title}</h3>
          </div>
          <div className="space-y-4">
            {section.tips.map((tip) => (
              <div key={tip.title} className="flex gap-3">
                <div className="w-6 h-6 rounded-full bg-kraft-100 dark:bg-kraft-800 flex items-center justify-center flex-shrink-0">
                  <HelpCircle className="w-3.5 h-3.5 text-kraft-700" />
                </div>
                <div>
                  <p className="text-sm font-medium text-surface-700 dark:text-surface-200">{tip.title}</p>
                  <p className="text-sm text-surface-500 dark:text-surface-400 mt-0.5">{tip.description}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      ))}

      <div className="flex justify-center">
        <Link to={home} className="text-sm text-primary-600 hover:text-primary-700 font-medium">
          ← Retour à mon espace
        </Link>
      </div>
    </div>
  );
}
