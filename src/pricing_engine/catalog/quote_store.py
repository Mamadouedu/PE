"""Store Quote in-memory + service d'orchestration (Lot 4)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from .pricing_engine_v2 import DemandeChiffrage, MoteurPrixV2
from .quote import (
    AppliedPricingRule,
    PricingCalculation,
    PricingCalculationComponent,
    Quote,
    QuoteLine,
    QuoteLineOption,
    QuoteStatus,
)
from .store import CatalogStore


class QuoteStore(Protocol):
    def create_quote(self, q: Quote) -> Quote: ...
    def get_quote(self, qid: UUID) -> Quote | None: ...
    def get_quote_by_number(self, number: str) -> Quote | None: ...
    def list_quotes(self, *, created_by: str | None = None, status: QuoteStatus | None = None) -> list[Quote]: ...
    def update_quote(self, q: Quote) -> Quote: ...
    def delete_quote(self, qid: UUID) -> bool: ...

    def add_quote_line(self, line: QuoteLine) -> QuoteLine: ...
    def list_quote_lines(self, quote_id: UUID) -> list[QuoteLine]: ...
    def get_quote_line(self, lid: UUID) -> QuoteLine | None: ...
    def delete_quote_line(self, lid: UUID) -> bool: ...

    def add_quote_line_option(self, opt: QuoteLineOption) -> QuoteLineOption: ...
    def list_quote_line_options(self, line_id: UUID) -> list[QuoteLineOption]: ...

    def save_pricing_calculation(self, calc: PricingCalculation) -> PricingCalculation: ...
    def get_pricing_calculation_for_line(self, line_id: UUID) -> PricingCalculation | None: ...

    def save_component(self, comp: PricingCalculationComponent) -> PricingCalculationComponent: ...
    def list_components(self, calc_id: UUID) -> list[PricingCalculationComponent]: ...

    def save_applied_rule(self, r: AppliedPricingRule) -> AppliedPricingRule: ...
    def list_applied_rules(self, calc_id: UUID) -> list[AppliedPricingRule]: ...

    def next_quote_number(self) -> str: ...


class InMemoryQuoteStore:
    """Store in-memory des quotes + calculs + composants + règles appliquées."""

    def __init__(self) -> None:
        self._quotes: dict[UUID, Quote] = {}
        self._quote_by_number: dict[str, UUID] = {}
        self._lines: dict[UUID, QuoteLine] = {}
        self._lines_by_quote: dict[UUID, list[UUID]] = {}
        self._line_options: dict[UUID, QuoteLineOption] = {}
        self._options_by_line: dict[UUID, list[UUID]] = {}
        self._calculations: dict[UUID, PricingCalculation] = {}
        self._calc_by_line: dict[UUID, UUID] = {}
        self._components: dict[UUID, PricingCalculationComponent] = {}
        self._components_by_calc: dict[UUID, list[UUID]] = {}
        self._applied_rules: dict[UUID, AppliedPricingRule] = {}
        self._rules_by_calc: dict[UUID, list[UUID]] = {}
        self._quote_counter = 0

    # ---------------- Quotes ----------------

    def create_quote(self, q: Quote) -> Quote:
        if q.quote_number in self._quote_by_number:
            raise ValueError(f"Quote number {q.quote_number} déjà pris")
        self._quotes[q.quote_id] = q
        self._quote_by_number[q.quote_number] = q.quote_id
        self._lines_by_quote.setdefault(q.quote_id, [])
        return q

    def get_quote(self, qid: UUID) -> Quote | None:
        return self._quotes.get(qid)

    def get_quote_by_number(self, number: str) -> Quote | None:
        qid = self._quote_by_number.get(number)
        return self._quotes.get(qid) if qid else None

    def list_quotes(self, *, created_by: str | None = None, status: QuoteStatus | None = None) -> list[Quote]:
        items = list(self._quotes.values())
        if created_by is not None:
            email = created_by.lower()
            items = [q for q in items if q.created_by.lower() == email]
        if status is not None:
            items = [q for q in items if q.status == status]
        return sorted(items, key=lambda q: q.created_at, reverse=True)

    def update_quote(self, q: Quote) -> Quote:
        if q.quote_id not in self._quotes:
            raise KeyError(q.quote_id)
        q.updated_at = datetime.now(timezone.utc)
        self._quotes[q.quote_id] = q
        return q

    def delete_quote(self, qid: UUID) -> bool:
        q = self._quotes.pop(qid, None)
        if q is None:
            return False
        self._quote_by_number.pop(q.quote_number, None)
        for lid in list(self._lines_by_quote.get(qid, [])):
            self.delete_quote_line(lid)
        self._lines_by_quote.pop(qid, None)
        return True

    def next_quote_number(self) -> str:
        self._quote_counter += 1
        year = datetime.now(timezone.utc).year
        return f"Q-{year}-{self._quote_counter:06d}"

    # ---------------- Lines ----------------

    def add_quote_line(self, line: QuoteLine) -> QuoteLine:
        if line.quote_id not in self._quotes:
            raise ValueError(f"Quote {line.quote_id} inconnue")
        self._lines[line.quote_line_id] = line
        self._lines_by_quote.setdefault(line.quote_id, []).append(line.quote_line_id)
        self._options_by_line.setdefault(line.quote_line_id, [])
        return line

    def list_quote_lines(self, quote_id: UUID) -> list[QuoteLine]:
        line_ids = self._lines_by_quote.get(quote_id, [])
        return [self._lines[lid] for lid in line_ids if lid in self._lines]

    def get_quote_line(self, lid: UUID) -> QuoteLine | None:
        return self._lines.get(lid)

    def delete_quote_line(self, lid: UUID) -> bool:
        line = self._lines.pop(lid, None)
        if line is None:
            return False
        # Dérèférence
        ids = self._lines_by_quote.get(line.quote_id, [])
        if lid in ids:
            ids.remove(lid)
        # Nettoyer calculs + composants + règles
        calc_id = self._calc_by_line.pop(lid, None)
        if calc_id:
            self._calculations.pop(calc_id, None)
            for c_id in self._components_by_calc.pop(calc_id, []):
                self._components.pop(c_id, None)
            for r_id in self._rules_by_calc.pop(calc_id, []):
                self._applied_rules.pop(r_id, None)
        for opt_id in self._options_by_line.pop(lid, []):
            self._line_options.pop(opt_id, None)
        return True

    # ---------------- Options ----------------

    def add_quote_line_option(self, opt: QuoteLineOption) -> QuoteLineOption:
        if opt.quote_line_id not in self._lines:
            raise ValueError(f"QuoteLine {opt.quote_line_id} inconnue")
        self._line_options[opt.quote_line_option_id] = opt
        self._options_by_line.setdefault(opt.quote_line_id, []).append(opt.quote_line_option_id)
        return opt

    def list_quote_line_options(self, line_id: UUID) -> list[QuoteLineOption]:
        ids = self._options_by_line.get(line_id, [])
        return [self._line_options[oid] for oid in ids if oid in self._line_options]

    # ---------------- Pricing calculation ----------------

    def save_pricing_calculation(self, calc: PricingCalculation) -> PricingCalculation:
        # Un seul calcul courant par ligne : on remplace l'ancien
        existing_id = self._calc_by_line.get(calc.quote_line_id)
        if existing_id and existing_id != calc.pricing_calculation_id:
            self._calculations.pop(existing_id, None)
            for c_id in self._components_by_calc.pop(existing_id, []):
                self._components.pop(c_id, None)
        self._calculations[calc.pricing_calculation_id] = calc
        self._calc_by_line[calc.quote_line_id] = calc.pricing_calculation_id
        return calc

    def get_pricing_calculation_for_line(self, line_id: UUID) -> PricingCalculation | None:
        cid = self._calc_by_line.get(line_id)
        return self._calculations.get(cid) if cid else None

    def save_component(self, comp: PricingCalculationComponent) -> PricingCalculationComponent:
        self._components[comp.component_id] = comp
        self._components_by_calc.setdefault(comp.pricing_calculation_id, []).append(comp.component_id)
        return comp

    def list_components(self, calc_id: UUID) -> list[PricingCalculationComponent]:
        ids = self._components_by_calc.get(calc_id, [])
        return [self._components[cid] for cid in ids if cid in self._components]

    def save_applied_rule(self, r: AppliedPricingRule) -> AppliedPricingRule:
        self._applied_rules[r.applied_rule_id] = r
        self._rules_by_calc.setdefault(r.pricing_calculation_id, []).append(r.applied_rule_id)
        return r

    def list_applied_rules(self, calc_id: UUID) -> list[AppliedPricingRule]:
        ids = self._rules_by_calc.get(calc_id, [])
        return [self._applied_rules[rid] for rid in ids if rid in self._applied_rules]


# =========================================================================
# Service d'orchestration
# =========================================================================


class QuoteService:
    """Haut-niveau : enchaîne la création de quote, l'ajout de lignes,
    le chiffrage via le moteur v2, la persistance des calculs et composants,
    l'application des règles métier (volume, campagne, dérogation)."""

    def __init__(self, catalog: CatalogStore, quotes: QuoteStore) -> None:
        self._catalog = catalog
        self._quotes = quotes
        self._engine = MoteurPrixV2(catalog)

    def creer_quote(self, client_code: str, client_name: str, created_by: str) -> Quote:
        number = self._quotes.next_quote_number()
        q = Quote(
            quote_number=number, client_code=client_code, client_name=client_name,
            created_by=created_by,
        )
        return self._quotes.create_quote(q)

    def ajouter_ligne_et_chiffrer(
        self,
        quote_id: UUID,
        technical_variant_code: str,
        country_iso: str,
        duration_months: int,
        age_years: float,
        annual_mileage_km: int,
        annual_engine_hours: float = 0,
        quantity: int = 1,
        start_date=None,
        ecm_provider_code: str | None = None,
        service_level_code: str | None = None,
    ) -> tuple[QuoteLine, PricingCalculation]:
        """Ajoute une ligne à la quote, exécute le moteur v2, persiste
        le PricingCalculation + composants + met à jour les totaux.

        **Atomicité** : si le chiffrage échoue après insertion de la ligne,
        celle-ci est retirée (rollback applicatif). Garantit qu'on n'a
        jamais une QuoteLine sans PricingCalculation attaché. Pour un
        vrai `BEGIN;...COMMIT;` SQL multi-instructions, voir issue #ATOMIC
        — nécessite de passer la session au QuoteStore."""

        from datetime import date as _date, timedelta as _td
        if start_date is None:
            start_date = _date.today()

        # 1. Validations préalables : lèvent AVANT toute écriture
        variant = self._catalog.get_variant_by_code(technical_variant_code)
        if variant is None:
            raise ValueError(f"Variante {technical_variant_code} inconnue")

        quote = self._quotes.get_quote(quote_id)
        if quote is None:
            raise ValueError(f"Quote {quote_id} inconnue")

        # 2. Chiffrage AVANT insertion : si ça échoue (variante sans tarif,
        #    palier manquant...), on n'a rien écrit à nettoyer
        try:
            resultat = self._engine.chiffrer(DemandeChiffrage(
                technical_variant_code=variant.variant_code,
                country_iso=country_iso,
                duration_months=duration_months,
                age_years=age_years,
                annual_mileage_km=annual_mileage_km,
                annual_engine_hours=annual_engine_hours,
                ecm_provider_code=ecm_provider_code,
                service_level_code=service_level_code,
            ))
        except ValueError:
            # Rethrow tel quel : l'appelant verra l'erreur sans rollback
            raise

        # 3. Résolution versions (snapshot gelé)
        dl_v = self._catalog.get_current_published_version("DL_STANDARD")
        hm_v = self._catalog.get_current_published_version("HM_STANDARD")
        om_v = self._catalog.get_current_published_version("OM_STANDARD")
        niveau = self._calculer_niveau_validation(resultat)

        # 4. Écriture : ligne puis calcul. En cas d'échec sur le calc,
        #    on rollback la ligne pour éviter l'orphelin.
        lines = self._quotes.list_quote_lines(quote_id)
        line = QuoteLine(
            quote_id=quote_id,
            line_number=len(lines) + 1,
            technical_variant_id=variant.technical_variant_id,
            technical_variant_code=variant.variant_code,
            quantity=quantity,
            contract_duration_months=duration_months,
            annual_mileage_km=annual_mileage_km,
            annual_engine_hours=annual_engine_hours,
            start_date=start_date,
            end_date=start_date + _td(days=int(duration_months * 30.44)),
            country_iso=country_iso,
        )
        self._quotes.add_quote_line(line)

        try:
            calc = PricingCalculation(
                quote_line_id=line.quote_line_id,
                dl_price_book_version_id=dl_v.price_book_version_id if dl_v else None,
                hm_price_book_version_id=hm_v.price_book_version_id if hm_v else None,
                om_price_book_version_id=om_v.price_book_version_id if om_v else None,
                dl_version_label=resultat.versions_utilisees.get("DL_STANDARD"),
                hm_version_label=resultat.versions_utilisees.get("HM_STANDARD"),
                om_version_label=resultat.versions_utilisees.get("OM_STANDARD"),
                dl_monthly=resultat.dl_mensuel or 0,
                hm_monthly_provisioned=resultat.hm_mensuel_provisionne,
                om_monthly=resultat.om_mensuel,
                options_monthly=0,
                total_monthly=resultat.total_mensuel,
                total_contract=resultat.total_mensuel * duration_months,
                floor_applied=resultat.plancher_applique or 0,
                is_under_floor=(resultat.plancher_applique or 0) > 0,
                niveau_validation=niveau,
                warnings=resultat.warnings,
            )
            self._quotes.save_pricing_calculation(calc)
            self._persister_composants(calc, resultat)
            self._recalculer_totaux_quote(quote_id)
        except Exception:
            # Rollback applicatif : supprime la ligne orpheline
            try:
                self._quotes.delete_quote_line(line.quote_line_id)
            except Exception:
                pass  # Best-effort : on ne masque pas l'erreur originale
            raise

        return line, calc

    def _calculer_niveau_validation(self, resultat) -> int:
        """Règle simplifiée : >220k km → N2 (Head of Pricing),
        plancher appliqué → N1 (Manager)."""
        niveau = 0
        if resultat.plancher_applique and resultat.plancher_applique > 0:
            niveau = max(niveau, 1)
        if any("dérogation requise" in w for w in resultat.warnings):
            niveau = max(niveau, 2)
        if any("Direction" in w for w in resultat.warnings):
            niveau = max(niveau, 3)
        return niveau

    def _persister_composants(self, calc: PricingCalculation, resultat) -> None:
        # DL decomposition
        for code, libelle in [
            ("monthly_base_rent", "Loyer base mensuel (DL)"),
            ("insurance_amount", "Assurance (DL)"),
            ("risk_provision_amount", "Provision risque (DL)"),
        ]:
            montant = resultat.detail_dl.get(code, 0)
            if montant:
                self._quotes.save_component(PricingCalculationComponent(
                    pricing_calculation_id=calc.pricing_calculation_id,
                    component_type=f"dl_{code}",
                    component_code=code,
                    description=libelle,
                    monthly_amount=montant,
                    annual_amount=montant * 12,
                    is_visible_to_client=True,
                ))
        # OM decomposition
        for code, libelle in [
            ("monthly_fixed", "OM — Montant mensuel fixe"),
            ("mileage_component", "OM — Composante kilométrage"),
            ("engine_hours_component", "OM — Composante heures moteur"),
            ("ecm_monthly", "OM — ECM mensuel"),
            ("last_mile_monthly", "OM — Last-mile mensuel"),
        ]:
            montant = resultat.detail_om.get(code, 0)
            if montant:
                self._quotes.save_component(PricingCalculationComponent(
                    pricing_calculation_id=calc.pricing_calculation_id,
                    component_type=f"om_{code}",
                    component_code=code,
                    description=libelle,
                    monthly_amount=montant,
                    annual_amount=montant * 12,
                    is_visible_to_client=True,
                ))
        # HM decomposition
        for hm in resultat.detail_hm:
            if hm["monthly_provision"] > 0:
                self._quotes.save_component(PricingCalculationComponent(
                    pricing_calculation_id=calc.pricing_calculation_id,
                    component_type="hm_provision",
                    component_code=hm["operation_code"],
                    description=f"HM — {hm['operation_code']} (provision mensuelle)",
                    monthly_amount=hm["monthly_provision"],
                    annual_amount=hm["monthly_provision"] * 12,
                    is_visible_to_client=False,  # Détail interne, client voit total HM
                ))

    def _recalculer_totaux_quote(self, quote_id: UUID) -> None:
        quote = self._quotes.get_quote(quote_id)
        if not quote:
            return
        total_mensuel = 0.0
        max_niveau = 0
        for line in self._quotes.list_quote_lines(quote_id):
            calc = self._quotes.get_pricing_calculation_for_line(line.quote_line_id)
            if calc:
                total_mensuel += calc.total_monthly * line.quantity
                max_niveau = max(max_niveau, calc.niveau_validation)
        # Durée dominante : celle de la première ligne, ou moyenne pondérée
        lines = self._quotes.list_quote_lines(quote_id)
        if lines:
            duree = max(l.contract_duration_months for l in lines)
        else:
            duree = 0
        quote.total_mensuel = round(total_mensuel, 2)
        quote.total_contrat = round(total_mensuel * duree, 2)
        quote.niveau_validation = max_niveau
        self._quotes.update_quote(quote)

    def soumettre(self, quote_id: UUID, submitted_by: str) -> Quote:
        quote = self._quotes.get_quote(quote_id)
        if quote is None:
            raise ValueError(f"Quote {quote_id} inconnue")
        if quote.status != QuoteStatus.DRAFT:
            raise ValueError(f"Impossible de soumettre une quote au statut {quote.status.value}")
        quote.status = QuoteStatus.SUBMITTED
        quote.submitted_at = datetime.now(timezone.utc)
        return self._quotes.update_quote(quote)

    def decider(self, quote_id: UUID, decided_by: str, approved: bool, comment: str = "") -> Quote:
        quote = self._quotes.get_quote(quote_id)
        if quote is None:
            raise ValueError(f"Quote {quote_id} inconnue")
        if quote.status != QuoteStatus.SUBMITTED:
            raise ValueError(f"Impossible de décider sur une quote au statut {quote.status.value}")
        quote.status = QuoteStatus.APPROVED if approved else QuoteStatus.REJECTED
        quote.decided_by = decided_by
        quote.decision_at = datetime.now(timezone.utc)
        quote.decision_comment = comment
        return self._quotes.update_quote(quote)

    def marquer_gagne_ou_perdu(self, quote_id: UUID, gagne: bool, by: str, comment: str = "") -> Quote:
        quote = self._quotes.get_quote(quote_id)
        if quote is None:
            raise ValueError(f"Quote {quote_id} inconnue")
        quote.status = QuoteStatus.WON if gagne else QuoteStatus.LOST
        quote.decided_by = by
        quote.decision_at = datetime.now(timezone.utc)
        if comment:
            quote.decision_comment = (quote.decision_comment or "") + " | " + comment
        return self._quotes.update_quote(quote)
