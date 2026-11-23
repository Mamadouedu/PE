# Moteur de pricing Akiem — version Excel

`Moteur_Pricing_Akiem.xlsx` porte, formule à formule, le moteur de prix de
PricingHub (.NET) tel qu'il existe à ce stade : les 4 briques (Dry lease,
Heavy maintenance, Operating maintenance, Assurance), la valeur résiduelle
VR(âge, km), le prix du km supplémentaire, le niveau de validation (0 à 3)
et les 8 contrôles avant envoi C1-C8 (section 6 du cahier des charges).
Aucune valeur n'est câblée en dur : tout vient des onglets de référentiel
(catalogue, référentiel pricing, clients, campagnes, délégation), à
l'image de la base PostgreSQL de PricingHub.

Voir l'onglet **Lisez-moi** du classeur pour la structure complète, le
mode d'emploi et les écarts de périmètre assumés (notamment : le contrôle
C1 utilise la durée max. de campagne GLOBALE, pas celle propre à chaque
campagne — à l'identique du comportement réel de PricingHub.Api
aujourd'hui).

## Régénérer le classeur

`build_excel.py` génère `Moteur_Pricing_Akiem.xlsx` à partir de rien
(toutes les formules, tous les onglets). À relancer si le moteur de
PricingHub évolue (nouveau calculateur, nouveau contrôle, nouveau
paramètre) pour que la version Excel reste alignée :

```bash
pip install openpyxl   # si besoin
python3 outils/build_excel.py
```

Le script écrit sur `outils/Moteur_Pricing_Akiem.xlsx`. Après l'avoir relancé,
revalidez avec LibreOffice headless (recalcule les formules — openpyxl
n'écrit aucune valeur en cache) :

```bash
soffice --headless --convert-to xlsx --outdir /tmp/verif outils/Moteur_Pricing_Akiem.xlsx
```

puis comparez quelques cellules clés (`Configurateur!B23`, `B40`, `B38`…)
aux valeurs de référence connues (voir les tests PricingHub.DomainTests /
PricingHub.InfrastructureTests, ou un appel direct à
`POST /api/quotes/calculate`).
