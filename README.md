# Plateforme Pricing Akiem — Moteur de prix (Lot 1, Socle)

Ce dépôt implémente le socle logiciel décrit dans le cahier des charges
« Plateforme Pricing Akiem » : le **référentiel versionné** (M1) et le
**moteur de prix** (M2), exposés par une **API Python testée** (M2-06).

Akiem n'a pas de licence Power Apps ni de Dataverse : ce socle suit donc la
version **sur mesure** du cahier, pas l'option Power Platform initiale. Ce
qui ne change pas entre les deux versions : la logique de prix elle-même,
déjà écrite ici et indépendante de ce choix d'architecture.

## Ce qui est construit

| Module | Contenu | Exigences couvertes |
| --- | --- | --- |
| `pricing_engine/models.py` | Entités du référentiel (section 8.3) : Série, Grille Dry lease, Tranche de km, BP HM/OM, Client, Flotte, Paramètres, Délégation | M1-01 |
| `pricing_engine/referentiel.py` | Cycle de vie brouillon / publié / archivé, contrôles qualité avant publication, journal des modifications — orchestration pure, indépendante du stockage | M1-02 à M1-05 |
| `pricing_engine/db.py` | Backend PostgreSQL du référentiel (remplace Dataverse) : un instantané JSON versionné par table `referentiel_versions`, un journal relationnel requêtable | M1 (sur mesure) |
| `pricing_engine/engine.py` | Calcul par brique (Dry lease, HM, OM, Assurance), valeur résiduelle, km supplémentaire, détail explicable, niveau de validation, 8 contrôles avant envoi | M2-01 à M2-05, section 6.2, 6.3, 6.4 |
| `pricing_engine/derogation.py` | Circuit de dérogation : demande (justification obligatoire), webhook sortant vers Power Automate, décision via webhook entrant, registre central | M4-01 à M4-05 |
| `pricing_engine/api.py` | API FastAPI : chiffrage (`POST /api/v1/prix`), dérogations, administration minimale du référentiel ; bascule sur PostgreSQL si `DATABASE_URL` est défini | M2-06, M4, M10 (base) |
| `tests/` | 67 tests pytest : une formule de la section 6 par test, scénarios de non-régression par niveau de validation, contrôles avant envoi, cycle de vie du référentiel et des dérogations (mémoire et PostgreSQL), API | M2-07 |
| `frontend/` | Configurateur KAM (React + TypeScript) : saisie, prix par brique avec jauge de négociation, niveau de validation, 8 contrôles avant envoi, demande de validation avec suivi en direct — remplace Power Apps | M3-01 à M3-03, M3-07, M4 |

`referentiel.py` ne dépend jamais de SQLAlchemy : le stockage est un
`ReferentielBackend` pluggable (`InMemoryReferentielBackend` par défaut,
`db.SqlAlchemyReferentielBackend` dès que `DATABASE_URL` est défini). Les 44
tests qui ne portent pas sur la persistance continuent de tourner en
mémoire, sans base de données.

## Ce qui n'est pas dans ce dépôt (hors périmètre code pour l'instant)

- Dans le configurateur : comparateur de 3 scénarios (M3-04), génération de
  l'offre PDF (M3-05), journal des offres et écriture dans Pipedrive (M3-06),
  assistant conversationnel (M3-08). Pas d'authentification non plus : le
  configurateur suppose pour l'instant un KAM déjà identifié (son e-mail est
  saisi à la main au moment de demander une validation).
- Dans le circuit de dérogation : le flow Power Automate lui-même (carte
  d'approbation Teams, rappel après délai, escalade, suppléant — M4-03,
  M4-06). Ce dépôt expose le webhook sortant et le webhook entrant qui
  l'encadrent ; construire le flow revient à la DSI, dans Power Automate.
- Intégrations Pipedrive / Sage, flotte : jobs planifiés / webhooks vers ce backend.
- Analytique, cockpit, synthèse direction : Qlik Sense (conservé) à la place de Power BI / Fabric.
- Agent IA : serveur MCP maison autour de cette API, pas de Copilot Studio (licence Power Platform indisponible).
- Authentification SSO Entra ID (OIDC), chiffrement au repos, hébergement : à mettre en place côté infrastructure.

Ces briques appelleront ce moteur via son API ; elles s'ajouteront lot par
lot une fois le socle validé.

## Hypothèses prises en l'absence de valeurs figées par la Direction

Le cahier précise que les valeurs entre parenthèses (marges, seuils...) sont
« à confirmer par la direction ». Elles sont toutes dans `Parametres`
(`models.py`), modifiables sans développement, avec les valeurs par défaut du
cahier (marge HM 15 %, OM 12 %, assurance 5 %, remise max 10 %, etc.).

Quelques points du cahier laissés ouverts (section 12.2) ont nécessité un
choix d'implémentation documenté ici, à valider avec l'équipe Pricing :

- **Bonus HM 8/16 ans dans la VR** : appliqué comme un montant fixe (4 % de
  VN chacun) dès que la révision est marquée réalisée sur la locomotive,
  sans dégressivité dans le temps.
- **Contrôle C1 (durée ≤ durée max de campagne)** : appliqué uniquement si
  la configuration est explicitement marquée comme rattachée à une campagne
  (champ `campagne`), une offre spot n'étant pas bornée à 3 mois par le texte.
- **Seuil de durée pour client à rating élevé (C3)** : paramètre dédié
  `duree_max_rating_eleve_mois` (1 mois par défaut), le cahier ne chiffrant
  que le seuil de rating (7).
- **Règle R1 de conformité des deals gagnés (section 6.5)** : explicitement
  signalée « à reformuler avec l'équipe » dans le cahier — non implémentée.

## Installation

```bash
pip install -e ".[dev]"
```

## Base de données (PostgreSQL, remplace Dataverse)

Sans base, l'API fonctionne quand même : elle retombe sur un référentiel en
mémoire (pratique en local, perdu à chaque redémarrage). Pour une vraie
persistance :

```bash
# une fois, en local : créer le rôle et les bases dev/test
sudo -u postgres psql -c "CREATE ROLE pricing LOGIN PASSWORD 'pricing';"
sudo -u postgres psql -c "CREATE DATABASE pricing_dev OWNER pricing;"
sudo -u postgres psql -c "CREATE DATABASE pricing_test OWNER pricing;"

export DATABASE_URL="postgresql+psycopg://pricing:pricing@localhost/pricing_dev"
```

Les tables (`referentiel_versions`, `journal_entries`) sont créées
automatiquement au premier démarrage (`db.create_all`). Il n'y a pas encore
d'Alembic : à mettre en place avant la mise en production, dès qu'un second
changement de schéma sera nécessaire.

Chaque version du référentiel est stockée comme un instantané JSON (pas huit
tables normalisées) — voir l'en-tête de `db.py` pour le choix et ses
limites. Le journal, lui, est une vraie table relationnelle, interrogeable
indépendamment des versions.

## Lancer les tests (scénarios de non-régression, M2-07)

```bash
pytest -q
```

Les tests de persistance (`tests/test_db_postgres.py`) ont besoin de
`pricing_test` (ci-dessus) ; sans elle, ils sont ignorés automatiquement.
Tous les autres tournent en mémoire, sans base.

## Lancer l'API

```bash
uvicorn pricing_engine.api:app --reload
```

Avec `DATABASE_URL` exporté comme ci-dessus, l'API persiste dans
`pricing_dev` ; sans, elle garde tout en mémoire pour la durée du process.

Documentation interactive : http://127.0.0.1:8000/docs

### Chiffrer une offre

```bash
curl -X POST http://127.0.0.1:8000/api/v1/prix \
  -H "Content-Type: application/json" \
  -d '{
    "client_code": "CLIENTOK",
    "serie_code": "VECTRON",
    "km_annuel": 120000,
    "duree_mois": 24,
    "quantite": 1,
    "date_debut": "2026-01-01",
    "age_debut_ans": 5,
    "km_cumules_debut": 600000
  }'
```

La réponse contient le prix de chaque brique (catalogue, plancher, retenu),
l'explicabilité du calcul (`etapes_calcul`, équivalent de l'onglet Calc du
prototype), le niveau de validation (0 à 3) et le résultat des 8 contrôles
avant envoi — jamais choisi par le KAM (section 7).

Avant de chiffrer, le référentiel doit avoir une version **publiée** : voir
les tests `tests/test_api.py` pour un exemple complet de cycle de vie
(brouillon → contrôles qualité → publication → chiffrage), ou le script de
seed ci-dessous pour en publier une en local en une commande.

### Peupler une base de démonstration

```bash
DATABASE_URL="postgresql+psycopg://pricing:pricing@localhost/pricing_dev" \
    python3 scripts/seed_dev.py
```

Publie un référentiel minimal (série VECTRON, grille, BP, 3 clients, 1
locomotive, délégations) — les mêmes données que `tests/conftest.py`, pour
que ce qui marche dans les tests marche aussi dans le configurateur.

## Circuit de dérogation (M4, section 7)

Le niveau de validation reste calculé par le moteur, jamais choisi par le
KAM (M4-01). Ce qui change avec le sur-mesure : le transport entre le KAM
et le validateur passe par deux webhooks plutôt que par Power Apps.

```bash
export POWER_AUTOMATE_WEBHOOK_URL="https://.../votre-flow"       # sortant : notifie Power Automate
export POWER_AUTOMATE_CALLBACK_SECRET="un-secret-partage"        # entrant : protège la décision
```

- `POST /api/v1/derogations` — le configurateur crée la demande
  (justification obligatoire, M4-02). Le niveau et le validateur sont
  recalculés côté serveur, jamais transmis par le client. Si
  `POWER_AUTOMATE_WEBHOOK_URL` est défini, une notification best-effort part
  vers Power Automate (payload : id, niveau, validateur, demandeur,
  montant, justification) ; sans l'URL, la demande se crée quand même —
  pratique en local et pour les tests.
- `GET /api/v1/derogations` — le registre central (M4-05).
- `POST /api/v1/derogations/{id}/decision` — le webhook entrant, appelé par
  Power Automate une fois la carte Teams décidée. Protégé par l'en-tête
  `X-Webhook-Secret` : sans `POWER_AUTOMATE_CALLBACK_SECRET` configuré,
  l'endpoint refuse tout appel (501) plutôt que d'accepter sans vérification.

Une dérogation gèle la configuration exacte qui l'a déclenchée : toute
modification après coup ne l'invalide pas automatiquement (pas d'étape
d'envoi d'offre construite pour l'instant, M3-05/M3-06), mais la caducité
décrite en M4-04 est déjà représentable — voir l'en-tête de `derogation.py`.

Pour simuler une décision sans Power Automate (démo, debug) :

```bash
curl -X POST http://127.0.0.1:8000/api/v1/derogations/1/decision \
  -H "Content-Type: application/json" -H "X-Webhook-Secret: un-secret-partage" \
  -d '{"decision": "approuvee", "decideur": "head@akiem.com", "commentaire": "ok"}'
```

Le configurateur suit la demande en direct (sondage toutes les 4 secondes,
`frontend/src/components/DemandeValidation.tsx`) : la décision apparaît sans
recharger la page.

## Frontend — Configurateur KAM

Application React + TypeScript (Vite) qui remplace Power Apps (M3) : elle ne
fait qu'appeler `POST /api/v1/prix` et afficher le résultat. Les coûts et
marges que l'API renvoie (`cout` par brique, `etapes_calcul`,
`cout_reference_mensuel`) sont délibérément filtrés avant l'affichage
(`frontend/src/api/offre.ts`, testé par `offre.test.ts`) : un KAM n'y a pas
accès (M3-07).

```bash
cd frontend
npm install
npm run dev       # http://localhost:5173, API par défaut http://127.0.0.1:8000
npm run test      # vitest
npm run build      # vérifie aussi les types (tsc -b)
```

`VITE_API_BASE_URL` (voir `.env.example`) pointe vers une autre API si
besoin. Le `CORS_ORIGINS` de l'API (`api.py`) doit alors inclure l'origine
du frontend — `http://localhost:5173` par défaut.

## Prochaines étapes

1. Lot 0 : faire valider ces règles et ces hypothèses par Pricing et la
   Direction sur 3 à 5 offres réelles, face à l'outil Excel actuel.
2. Mettre en place Alembic avant toute évolution de schéma en production.
3. Authentification du configurateur (SSO Entra ID), comparateur de
   scénarios (M3-04), offre PDF (M3-05), écriture dans Pipedrive (M3-06).
4. Construire le flow Power Automate lui-même (carte Teams, rappel,
   escalade, suppléant) — ce dépôt fournit les deux webhooks qui l'encadrent.
