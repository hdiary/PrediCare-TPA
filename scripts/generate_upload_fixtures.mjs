import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const count = 20;
const outputDirectory = resolve('tests/upload_fixtures/lot20');
const temporaryDirectory = mkdtempSync(join(tmpdir(), 'predicare-upload-fixtures-'));
const invoices = [];
const prescriptions = [];

const pad = (value) => String(value).padStart(2, '0');
const formatAmount = (value) => String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
const date = (day) => `2026-09-${pad(day)}`;

function documentHtml(title, firstLine, content, footer) {
  return `<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>${title}</title>
  <style>
    @page { size: A4; margin: 22mm; }
    body { color: #19363a; font: 12pt Arial, sans-serif; }
    h1 { color: #075e59; font-size: 24pt; margin-bottom: 4px; }
    .rule { border-top: 3px solid #16a394; margin: 18px 0; }
    pre { font: 12pt/1.8 "Liberation Mono", monospace; white-space: pre-wrap; }
    footer { border-top: 1px solid #9eb8b5; color: #526b68; margin-top: 32px; padding-top: 12px; }
  </style>
</head>
<body>
  <h1>${firstLine}</h1>
  <p>Document de test - donnees entierement fictives</p>
  <div class="rule"></div>
  <pre>${content}</pre>
  <footer>DOCUMENT FICTIF - TEST LOGICIEL UNIQUEMENT<br>${footer}</footer>
</body>
</html>
`;
}

try {
  mkdirSync(outputDirectory, { recursive: true });

  for (let index = 1; index <= count; index += 1) {
    const sequence = pad(index);
    const orderNumber = `ORD-9${String(100000 + index).padStart(6, '0')}`;
    const invoiceNumber = `PRE00001/2026/TEST${sequence}`;
    const careDate = date(index);
    const prescriptionDate = date(Math.max(1, index - 1));
    const quantity = (index % 3) + 1;
    const unitPrice = 4000 + (index % 4) * 500;
    const total = quantity * unitPrice;
    const invoiceFilename = `facture_${sequence}.html`;
    const prescriptionFilename = `ordonnance_${sequence}.html`;
    const label = 'Amlodipine 5 mg, boite de 30';

    const invoiceContent = [
      `FACTURE N° ${invoiceNumber}`,
      'N° assure ASS-9CAA1484E0',
      'NIF 1939042955',
      'Type PHARMACIE',
      `Date des soins ${careDate}`,
      `Date de facture ${careDate}`,
      'Heure 10:30',
      'Mode TIERS_PAYANT',
      'Devise MGA',
      `Ordonnance ${orderNumber}`,
      '',
      `MED-AMLO ${label} ${quantity} ${formatAmount(unitPrice)} MGA ${formatAmount(total)} MGA`,
      '',
      `TOTAL ${formatAmount(total)} MGA`,
    ].join('\n');

    const prescriptionContent = [
      'ORDONNANCE',
      `Ref. ${orderNumber}`,
      'Medecine generale - ONM-12345',
      'Patient : ASS-9CAA1484E0 - 42 ans',
      'Renseignement clinique : test fictif',
      '',
      `1. ${label} - Qte: ${quantity}`,
      `${quantity} prise(s) par jour pendant 1 jour`,
      '',
      `Date : Antananarivo, le ${prescriptionDate}`,
      'Validite : 30 jours',
    ].join('\n');

    writeFileSync(
      join(temporaryDirectory, invoiceFilename),
      documentHtml('Facture fictive', 'Pharmacie Vatolampy', invoiceContent, 'Facture de demonstration.'),
    );
    writeFileSync(
      join(temporaryDirectory, prescriptionFilename),
      documentHtml('Ordonnance fictive', 'Dr Demonstration', prescriptionContent, 'Ordonnance sans valeur medicale.'),
    );
    invoices.push(join(temporaryDirectory, invoiceFilename));
    prescriptions.push(join(temporaryDirectory, prescriptionFilename));
  }

  execFileSync('libreoffice', [
    '--headless',
    '--convert-to',
    'pdf',
    '--outdir',
    outputDirectory,
    ...invoices,
    ...prescriptions,
  ], { stdio: 'inherit' });

  writeFileSync(join(outputDirectory, 'README.md'), `# Lot de test : 20 factures et 20 ordonnances

Les documents de ce dossier sont entierement fictifs et sans valeur medicale.
Chaque facture_NN.pdf correspond a ordonnance_NN.pdf avec le meme numero
d'ordonnance ORD-91000NN.

Les documents reprennent les references confirmees dans la base de test :
prestataire PRE-00001, NIF 1939042955, assure ASS-9CAA1484E0 et medicament
MED-AMLO. Le mode de reglement est TIERS_PAYANT.

Televersez une facture comme document principal, cochez le lien avec une
ordonnance, puis joignez le PDF d'ordonnance portant le meme suffixe. Relancez
node scripts/generate_upload_fixtures.mjs pour regenerer le lot.
`);
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}