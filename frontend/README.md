# Configurateur KAM — Akiem Pricing

Application React + TypeScript (Vite) qui chiffre une offre en appelant
`POST /api/v1/prix` sur le moteur de prix (`../src/pricing_engine`). Voir le
README du dépôt pour le contexte complet (section « Frontend — Configurateur
KAM ») ; en bref :

```bash
npm install
npm run dev     # http://localhost:5173
npm run test
npm run build
```

`src/api/offre.ts` filtre délibérément tout ce que l'API renvoie comme coût
ou marge avant que ça n'atteigne un composant — un KAM n'y a pas accès
(M3-07 du cahier des charges). `offre.test.ts` vérifie que ce filtre tient.
