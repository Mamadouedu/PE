# Plateforme Pricing Akiem — Moteur de prix (Lot 1, Socle)

Ce dépôt implémente le socle logiciel décrit dans le cahier des charges
« Plateforme Pricing Akiem » : le **référentiel versionné** (M1) et le
**moteur de prix** (M2), exposés par une **API Python testée** (M2-06),
conformément à l'architecture cible de la section 4 (« une seule logique de
prix, appelée par tous les canaux »).

Le reste du cahier (configurateur KAM, workflow de dérogation, intégrations
Pipedrive/Sage, analytique, agent IA) s'appuie sur des briques Microsoft
low-code (Power Apps, Power Automate, Dataverse, Fabric, Copilot Studio) qui
ne se développent pas dans un dépôt de code : ce socle est la pièce qui s'y
connecte, telle que décrite en section 10.3.

## Ce qui est construit

| Module | Contenu | Exigences couvertes |
| --- | --- | --- |
| `pricing_engine/models.py` | Entités du référentiel (section 8.3) : Série, Grille Dry lease, Tranche de km, BP HM/OM, Client, Flotte, Paramètres, Délégation | M1-01 |
| `pricing_engine/referentiel.py` | Dépôt versionné (brouillon / publié / archivé), un propriétaire par table, contrôles qualité avant publication, journal des modifications | M1-02 à M1-05 |
| `pricing_engine/engine.py` | Calcul par brique (Dry lease, HM, OM, Assurance), valeur résiduelle, km supplémentaire, détail explicable, niveau de validation, 8 contrôles avant envoi | M2-01 à M2-05, section 6.2, 6.3, 6.4 |
| `pricing_engine/api.py` | API FastAPI : chiffrage (`POST /api/v1/prix`) + administration minimale du référentiel | M2-06, M10 (base) |
| `tests/` | 44 tests pytest : une formule de la section 6 par test, scénarios de non-régression par niveau de validation, contrôles avant envoi, cycle de vie du référentiel, API | M2-07 |

## Ce qui n'est pas dans ce dépôt (hors périmètre code)

- Configurateur KAM (M3), workflow de dérogation Teams (M4) : Power Apps + Power Automate.
- Intégrations Pipedrive / Sage (M6), flotte (M1-08) : Power Automate / Azure Logic Apps.
- Analytique, cockpit, synthèse direction (M7, M8) : Microsoft Fabric + Power BI.
- Agent IA (M3-08, M7-08) : Copilot Studio + serveur MCP sur Dataverse et ce moteur.
- Authentification SSO / Entra ID, chiffrement au repos : configuration Azure, pas du code applicatif.

Ces briques consomment ce moteur via son API (section 4) ; elles s'ajouteront
lot par lot (section 11.1) une fois le socle validé par la Direction et la
DSI (lot 0).

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

## Lancer les tests (scénarios de non-régression, M2-07)

```bash
pytest -q
```

## Lancer l'API

```bash
uvicorn pricing_engine.api:app --reload
```

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
(brouillon → contrôles qualité → publication → chiffrage).

## Prochaines étapes (section 11.1)

1. Lot 0 : faire valider ces règles et ces hypothèses par Pricing et la
   Direction sur 3 à 5 offres réelles, face à l'outil Excel actuel.
2. Brancher ce moteur derrière Dataverse (stockage du référentiel en cible)
   et l'exposer en Azure Functions / Container Apps versionnées (section 10.3).
3. Lot 2 : construire le configurateur KAM (Power Apps) et le workflow de
   dérogation (Power Automate + Teams) au-dessus de cette API.
