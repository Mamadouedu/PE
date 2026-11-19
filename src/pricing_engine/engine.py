"""Moteur de prix (M2) — section 6 du cahier des charges.

Le moteur est la seule logique de calcul du prix full service (Dry lease,
Heavy maintenance, Operation maintenance, Assurance). Il est appelé de façon
identique par tous les canaux (M2-06) : application KAM, Power BI, agent IA.

Chaque fonction de brique correspond au calcul décrit en section 6.1, la
valeur résiduelle à la section 6.2, le niveau de validation à la section 6.3
et les contrôles avant envoi à la section 6.4.
"""

from __future__ import annotations

from .models import (
    Brique,
    ConfigurationOffre,
    DetailBrique,
    DetailOffre,
    EtapeCalcul,
    Parametres,
    ResultatControle,
    Serie,
    StatutBrique,
    StatutLocomotive,
    Validateur,
)
from .referentiel import VersionReferentiel


def calculer_valeur_residuelle(
    serie: Serie,
    parametres: Parametres,
    age_ans: float,
    km_cumules: float,
    hm_8_realisee: bool,
    hm_16_realisee: bool,
) -> float:
    vn = serie.valeur_neuve
    plancher = vn * parametres.plancher_vr_taux
    usure = vn * (1 - (1 - serie.vr_fin_vie_taux) * min(1.0, age_ans / serie.duree_vie_ans))
    bonus = (parametres.bonus_vr_hm8 * vn if hm_8_realisee else 0.0) + (
        parametres.bonus_vr_hm16 * vn if hm_16_realisee else 0.0
    )
    perte_km = parametres.perte_valeur_par_km_hors_reference * max(
        0.0, km_cumules - serie.km_reference_annuel * age_ans
    )
    base = usure + bonus - perte_km
    return max(plancher, base)


def _prix_retenu(
    brique: Brique,
    config: ConfigurationOffre,
    cout: float,
    prix_catalogue: float,
    plancher: float,
) -> DetailBrique:
    if brique not in config.briques_incluses:
        return DetailBrique(
            brique=brique,
            cout=cout,
            prix_catalogue=prix_catalogue,
            plancher=plancher,
            prix_negocie=None,
            prix_retenu=0.0,
            statut=StatutBrique.EXCLUE,
        )

    prix_negocie = config.prix_negocies.get(brique)
    prix_retenu = prix_negocie if prix_negocie is not None else prix_catalogue

    if prix_retenu < plancher:
        statut = StatutBrique.SOUS_PLANCHER
    elif prix_negocie is not None and prix_negocie < prix_catalogue:
        statut = StatutBrique.ALERTE
    else:
        statut = StatutBrique.OK

    return DetailBrique(
        brique=brique,
        cout=cout,
        prix_catalogue=prix_catalogue,
        plancher=plancher,
        prix_negocie=prix_negocie,
        prix_retenu=prix_retenu,
        statut=statut,
    )


def _controles_avant_envoi(
    version: VersionReferentiel,
    config: ConfigurationOffre,
    briques: dict[Brique, DetailBrique],
    perte_valeur_mensuelle: float,
) -> list[ResultatControle]:
    """Les 8 contrôles avant envoi — section 6.4."""

    parametres = version.parametres
    client = version.clients.get(config.client_code)
    locomotive = (
        version.flotte.get(config.locomotive_numero) if config.locomotive_numero else None
    )

    controles: list[ResultatControle] = []

    if config.campagne:
        ok = config.duree_mois <= parametres.duree_max_campagne_mois
        detail = f"{config.duree_mois} mois (max campagne {parametres.duree_max_campagne_mois})"
    else:
        ok, detail = True, "non applicable (offre hors campagne)"
    controles.append(
        ResultatControle(code="C1_DUREE_CAMPAGNE", libelle="Durée ≤ durée maximale de campagne", ok=ok, detail=detail)
    )

    ok = config.quantite <= parametres.max_locos_par_contrat
    controles.append(
        ResultatControle(
            code="C2_NB_LOCOS",
            libelle="Nombre de locos ≤ maximum par contrat",
            ok=ok,
            detail=f"{config.quantite} loco(s) (max {parametres.max_locos_par_contrat})",
        )
    )

    if client is None:
        controles.append(
            ResultatControle(
                code="C3_CLIENT_RATING",
                libelle="Client à rating élevé : durée courte et paiement d'avance",
                ok=False,
                detail=f"Client {config.client_code} introuvable au référentiel",
            )
        )
    else:
        if client.rating > parametres.seuil_rating_garantie:
            ok = (
                config.duree_mois <= parametres.duree_max_rating_eleve_mois
                and client.paiement_avance
            )
            detail = f"rating {client.rating} > seuil {parametres.seuil_rating_garantie}"
        else:
            ok, detail = True, f"rating {client.rating} ≤ seuil {parametres.seuil_rating_garantie}"
        controles.append(
            ResultatControle(
                code="C3_CLIENT_RATING",
                libelle="Client à rating élevé : durée courte et paiement d'avance",
                ok=ok,
                detail=detail,
            )
        )

    ok = Brique.ASSURANCE in config.briques_incluses
    controles.append(
        ResultatControle(code="C4_ASSURANCE_INCLUSE", libelle="Assurance incluse", ok=ok, detail=str(ok))
    )

    if client is None:
        ok, detail = False, f"Client {config.client_code} introuvable au référentiel"
    else:
        ok = client.cash_deposit > 0 or client.paiement_avance
        detail = f"cash_deposit={client.cash_deposit}, paiement_avance={client.paiement_avance}"
    controles.append(
        ResultatControle(
            code="C5_GARANTIE_PAIEMENT",
            libelle="Garantie de paiement (cash deposit ou paiement d'avance)",
            ok=ok,
            detail=detail,
        )
    )

    hm_detail = briques.get(Brique.HEAVY_MAINTENANCE)
    om_detail = briques.get(Brique.OPERATION_MAINTENANCE)
    ok = (hm_detail is None or hm_detail.statut != StatutBrique.SOUS_PLANCHER) and (
        om_detail is None or om_detail.statut != StatutBrique.SOUS_PLANCHER
    )
    controles.append(
        ResultatControle(
            code="C6_AUCUN_PRIX_SOUS_PLANCHER_BP",
            libelle="Aucun prix sous le plancher BP",
            ok=ok,
            detail="HM/OM comparés au BP",
        )
    )

    dl_detail = briques.get(Brique.DRY_LEASE)
    if dl_detail is None or dl_detail.statut == StatutBrique.EXCLUE:
        ok, detail = True, "Dry lease exclu de l'offre"
    else:
        ok = dl_detail.prix_retenu >= perte_valeur_mensuelle
        detail = f"DL retenu {dl_detail.prix_retenu:.2f} vs perte de valeur mensuelle {perte_valeur_mensuelle:.2f}"
    controles.append(
        ResultatControle(
            code="C7_DL_COUVRE_PERTE_VALEUR",
            libelle="Le Dry lease couvre la perte de valeur mensuelle",
            ok=ok,
            detail=detail,
        )
    )

    if locomotive is None:
        ok, detail = True, "Aucune locomotive de flotte affectée (hors contrôle)"
    else:
        ok = (
            locomotive.statut == StatutLocomotive.DISPONIBLE
            and locomotive.serie_code == config.serie_code
        )
        detail = f"statut={locomotive.statut.value}, série={locomotive.serie_code}"
    controles.append(
        ResultatControle(
            code="C8_LOCO_DISPONIBLE_BONNE_SERIE",
            libelle="Locomotive disponible et de la bonne série",
            ok=ok,
            detail=detail,
        )
    )

    return controles


def calculer_offre(version: VersionReferentiel, config: ConfigurationOffre) -> DetailOffre:
    """Calcule une offre complète, brique par brique, avec explicabilité
    (M2-01 à M2-04) et niveau de validation (6.3)."""

    parametres = version.parametres
    serie = version.series[config.serie_code]
    tranche_km = version.tranche_km_pour(config.km_annuel)
    grille = version.grille_pour(config.serie_code, config.duree_mois)
    bp = version.bp_pour(config.serie_code, config.km_annuel)

    if config.locomotive_numero is not None:
        locomotive = version.flotte[config.locomotive_numero]
        age_debut = locomotive.age_ans(config.date_debut)
        km_debut = locomotive.km_cumules
        hm_8 = locomotive.hm_8_realisee
        hm_16 = locomotive.hm_16_realisee
    else:
        age_debut = config.age_debut_ans or 0.0
        km_debut = config.km_cumules_debut or 0.0
        hm_8 = config.hm_8_realisee
        hm_16 = config.hm_16_realisee

    duree_ans = config.duree_mois / 12
    age_fin = age_debut + duree_ans
    km_fin = km_debut + config.km_annuel * duree_ans

    vr_debut = calculer_valeur_residuelle(serie, parametres, age_debut, km_debut, hm_8, hm_16)
    vr_fin = calculer_valeur_residuelle(serie, parametres, age_fin, km_fin, hm_8, hm_16)
    perte_valeur_totale = vr_debut - vr_fin
    perte_valeur_mensuelle = perte_valeur_totale / config.duree_mois
    vr_moyenne_contrat = (vr_debut + vr_fin) / 2

    # Dry lease
    prix_catalogue_dl = grille.loyer_mensuel * tranche_km.coefficient_dl
    plancher_dl = prix_catalogue_dl * (1 - parametres.remise_maximale)
    detail_dl = _prix_retenu(Brique.DRY_LEASE, config, grille.loyer_mensuel, prix_catalogue_dl, plancher_dl)

    # Heavy maintenance
    cout_mensuel_hm = serie.cout_hm_par_km * config.km_annuel / 12 * tranche_km.coefficient_hm
    prix_catalogue_hm = max(cout_mensuel_hm * (1 + parametres.marge_hm), bp.bp_hm)
    plancher_hm = bp.bp_hm
    detail_hm = _prix_retenu(
        Brique.HEAVY_MAINTENANCE, config, cout_mensuel_hm, prix_catalogue_hm, plancher_hm
    )

    # Operation maintenance
    cout_mensuel_om = (
        (serie.om_fixe + serie.om_variable_eur_par_km * config.km_annuel)
        / 12
        * tranche_km.coefficient_om
    )
    prix_catalogue_om = max(cout_mensuel_om * (1 + parametres.marge_om), bp.bp_om)
    plancher_om = bp.bp_om
    detail_om = _prix_retenu(
        Brique.OPERATION_MAINTENANCE, config, cout_mensuel_om, prix_catalogue_om, plancher_om
    )

    # Assurance
    prime = vr_moyenne_contrat * serie.taux_assurance_annuel / 12
    prix_catalogue_assurance = prime * (1 + parametres.marge_assurance)
    plancher_assurance = prime
    detail_assurance = _prix_retenu(
        Brique.ASSURANCE, config, prime, prix_catalogue_assurance, plancher_assurance
    )

    par_brique = {
        Brique.DRY_LEASE: detail_dl,
        Brique.HEAVY_MAINTENANCE: detail_hm,
        Brique.OPERATION_MAINTENANCE: detail_om,
        Brique.ASSURANCE: detail_assurance,
    }

    # Km supplémentaire — section 6.1
    prix_km_supplementaire = (
        serie.cout_hm_par_km * tranche_km.coefficient_hm
        + serie.om_variable_eur_par_km * tranche_km.coefficient_om
    ) * (1 + parametres.majoration_km_supplementaire)

    inclues = config.briques_incluses
    total_catalogue_par_loco = sum(d.prix_catalogue for b, d in par_brique.items() if b in inclues)
    total_retenu_par_loco = sum(d.prix_retenu for d in par_brique.values())
    total_plancher_par_loco = sum(d.plancher for b, d in par_brique.items() if b in inclues)

    remise_globale = (
        1 - total_retenu_par_loco / total_catalogue_par_loco if total_catalogue_par_loco else 0.0
    )

    cout_reference_mensuel = perte_valeur_mensuelle + cout_mensuel_hm + cout_mensuel_om + prime

    controles = _controles_avant_envoi(version, config, par_brique, perte_valeur_mensuelle)

    niveau = 0
    motifs: list[str] = []
    if remise_globale > parametres.seuil_remise_kam:
        niveau = max(niveau, 1)
        motifs.append(
            f"Remise globale {remise_globale:.1%} > seuil KAM {parametres.seuil_remise_kam:.1%}"
        )
    if any(d.statut == StatutBrique.SOUS_PLANCHER for d in par_brique.values()):
        niveau = max(niveau, 2)
        motifs.append("Au moins une brique sous son plancher")
    controles_en_echec = [c for c in controles if not c.ok]
    if controles_en_echec:
        niveau = max(niveau, 2)
        motifs.append(
            "Contrôle(s) avant envoi en échec : " + ", ".join(c.code for c in controles_en_echec)
        )
    if total_retenu_par_loco < cout_reference_mensuel:
        niveau = max(niveau, 3)
        motifs.append(
            f"Prix retenu {total_retenu_par_loco:.2f} < coût de référence {cout_reference_mensuel:.2f}"
        )
    if not motifs:
        motifs.append("Dans les règles : validation KAM (niveau 0)")

    etapes = [
        EtapeCalcul(libelle="Coût HM / km", valeur=serie.cout_hm_par_km),
        EtapeCalcul(libelle="Coût mensuel HM (avant marge)", valeur=cout_mensuel_hm),
        EtapeCalcul(libelle="Coût mensuel OM (avant marge)", valeur=cout_mensuel_om),
        EtapeCalcul(libelle="Valeur résiduelle début", valeur=vr_debut),
        EtapeCalcul(libelle="Valeur résiduelle fin", valeur=vr_fin),
        EtapeCalcul(libelle="Valeur résiduelle moyenne (base prime assurance)", valeur=vr_moyenne_contrat),
        EtapeCalcul(libelle="Perte de valeur totale sur le contrat", valeur=perte_valeur_totale),
        EtapeCalcul(libelle="Perte de valeur mensuelle", valeur=perte_valeur_mensuelle),
        EtapeCalcul(libelle="Prime d'assurance (coût)", valeur=prime),
        EtapeCalcul(libelle="Prix du km supplémentaire", valeur=prix_km_supplementaire),
        EtapeCalcul(libelle="Coût de référence mensuel (Direction)", valeur=cout_reference_mensuel),
    ]

    return DetailOffre(
        version_referentiel=version.numero,
        par_brique=par_brique,
        etapes_calcul=etapes,
        valeur_residuelle_debut=vr_debut,
        valeur_residuelle_fin=vr_fin,
        perte_valeur_totale=perte_valeur_totale,
        perte_valeur_mensuelle=perte_valeur_mensuelle,
        prix_km_supplementaire=prix_km_supplementaire,
        total_catalogue_par_loco_mensuel=total_catalogue_par_loco,
        total_retenu_par_loco_mensuel=total_retenu_par_loco,
        total_plancher_par_loco_mensuel=total_plancher_par_loco,
        total_retenu_mensuel=total_retenu_par_loco * config.quantite,
        total_retenu_contrat=total_retenu_par_loco * config.quantite * config.duree_mois,
        remise_globale=remise_globale,
        cout_reference_mensuel=cout_reference_mensuel,
        niveau_validation=niveau,
        motifs_niveau_validation=motifs,
        controles=controles,
        tous_controles_ok=not controles_en_echec,
    )


def validateur_requis(version: VersionReferentiel, offre: DetailOffre) -> Validateur | None:
    """Le validateur associé au niveau calculé (section 7 : jamais choisi par le KAM)."""

    if offre.niveau_validation == 0:
        return None
    return version.validateur_pour(offre.niveau_validation)
