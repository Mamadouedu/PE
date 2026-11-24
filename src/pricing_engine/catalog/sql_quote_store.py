"""SqlAlchemyQuoteStore : persistance SQL des quotes (Lot 4).

Implémente le même protocol `QuoteStore` que `InMemoryQuoteStore` en
écrivant dans PostgreSQL / SQLite. Pattern session courte par opération.

Les cascade deletes sont déclarées côté DB (quotes → quote_lines →
pricing_calculations), donc `delete_quote` suffit à tout nettoyer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from .db import (
    AppliedPricingRuleRow,
    PricingCalculationComponentRow,
    PricingCalculationRow,
    QuoteLineOptionRow,
    QuoteLineRow,
    QuoteRow,
)
from .quote import (
    AppliedPricingRule,
    PricingCalculation,
    PricingCalculationComponent,
    PricingRuleKind,
    Quote,
    QuoteLine,
    QuoteLineOption,
    QuoteStatus,
)


def _s(u):
    return str(u) if isinstance(u, UUID) else u


class SqlAlchemyQuoteStore:
    """Store SQL pour quotes, lignes, calculs, composants, options et
    règles appliquées. Tout est persisté en SQL avec CASCADE sur les FK :
    delete_quote nettoie tout en un seul coup."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sf = session_factory

    def next_quote_number(self) -> str:
        """Compteur séquentiel global. Query le max existant puis +1.

        En prod multi-instance, il faudrait un PostgreSQL SEQUENCE pour
        éviter les collisions ; ici on prend le max + 1 ce qui tient à
        charge faible."""
        with self._sf() as session:
            n = session.execute(
                select(func.count()).select_from(QuoteRow)
            ).scalar() or 0
            year = datetime.now(timezone.utc).year
            return f"Q-{year}-{(n + 1):06d}"

    # ---------------- Quotes ----------------

    def create_quote(self, q: Quote) -> Quote:
        with self._sf() as session:
            session.add(QuoteRow(
                quote_id=_s(q.quote_id),
                quote_number=q.quote_number,
                client_code=q.client_code,
                client_name=q.client_name,
                created_by=q.created_by,
                created_at=q.created_at,
                updated_at=q.updated_at,
                status=q.status.value,
                submitted_at=q.submitted_at,
                decision_at=q.decision_at,
                decided_by=q.decided_by,
                decision_comment=q.decision_comment,
                valid_until=q.valid_until,
                currency_iso=q.currency_iso,
                total_mensuel=q.total_mensuel,
                total_contrat=q.total_contrat,
                niveau_validation=q.niveau_validation,
                pipedrive_deal_id=q.pipedrive_deal_id,
            ))
            session.commit()
            return q

    def get_quote(self, qid: UUID) -> Quote | None:
        with self._sf() as session:
            row = session.get(QuoteRow, _s(qid))
            return self._row_to_quote(row) if row else None

    def get_quote_by_number(self, number: str) -> Quote | None:
        with self._sf() as session:
            row = session.execute(
                select(QuoteRow).where(QuoteRow.quote_number == number)
            ).scalar_one_or_none()
            return self._row_to_quote(row) if row else None

    def list_quotes(self, *, created_by: str | None = None,
                    status: QuoteStatus | None = None) -> list[Quote]:
        with self._sf() as session:
            stmt = select(QuoteRow)
            if created_by is not None:
                stmt = stmt.where(func.lower(QuoteRow.created_by) == created_by.lower())
            if status is not None:
                stmt = stmt.where(QuoteRow.status == status.value)
            rows = session.execute(stmt.order_by(QuoteRow.created_at.desc())).scalars().all()
            return [self._row_to_quote(r) for r in rows]

    def update_quote(self, q: Quote) -> Quote:
        with self._sf() as session:
            row = session.get(QuoteRow, _s(q.quote_id))
            if row is None:
                raise KeyError(q.quote_id)
            q.updated_at = datetime.now(timezone.utc)
            for attr in (
                "client_code", "client_name", "created_by",
                "submitted_at", "decision_at", "decided_by",
                "decision_comment", "valid_until", "currency_iso",
                "total_mensuel", "total_contrat", "niveau_validation",
                "pipedrive_deal_id",
            ):
                setattr(row, attr, getattr(q, attr))
            row.updated_at = q.updated_at
            row.status = q.status.value
            session.commit()
            return q

    def delete_quote(self, qid: UUID) -> bool:
        with self._sf() as session:
            row = session.get(QuoteRow, _s(qid))
            if row is None:
                return False
            session.delete(row)
            session.commit()
        return True

    @staticmethod
    def _row_to_quote(r: QuoteRow) -> Quote:
        return Quote(
            quote_id=UUID(r.quote_id),
            quote_number=r.quote_number,
            client_code=r.client_code,
            client_name=r.client_name,
            created_by=r.created_by,
            created_at=r.created_at,
            updated_at=r.updated_at,
            status=QuoteStatus(r.status),
            submitted_at=r.submitted_at,
            decision_at=r.decision_at,
            decided_by=r.decided_by,
            decision_comment=r.decision_comment,
            valid_until=r.valid_until,
            currency_iso=r.currency_iso,
            total_mensuel=r.total_mensuel,
            total_contrat=r.total_contrat,
            niveau_validation=r.niveau_validation,
            pipedrive_deal_id=r.pipedrive_deal_id,
        )

    # ---------------- Lines ----------------

    def add_quote_line(self, line: QuoteLine) -> QuoteLine:
        with self._sf() as session:
            if session.get(QuoteRow, _s(line.quote_id)) is None:
                raise ValueError(f"Quote {line.quote_id} inconnue")
            session.add(QuoteLineRow(
                quote_line_id=_s(line.quote_line_id),
                quote_id=_s(line.quote_id),
                line_number=line.line_number,
                technical_variant_id=_s(line.technical_variant_id),
                technical_variant_code=line.technical_variant_code,
                quantity=line.quantity,
                contract_duration_months=line.contract_duration_months,
                annual_mileage_km=line.annual_mileage_km,
                annual_engine_hours=line.annual_engine_hours,
                monthly_mileage_km=line.monthly_mileage_km,
                start_date=line.start_date,
                end_date=line.end_date,
                country_iso=line.country_iso,
                homologation_id=_s(line.homologation_id) if line.homologation_id else None,
                selected_ecm_provider_id=_s(line.selected_ecm_provider_id) if line.selected_ecm_provider_id else None,
                selected_service_level_id=_s(line.selected_service_level_id) if line.selected_service_level_id else None,
                fleet_asset_id=_s(line.fleet_asset_id) if line.fleet_asset_id else None,
                notes=line.notes,
            ))
            session.commit()
            return line

    def list_quote_lines(self, quote_id: UUID) -> list[QuoteLine]:
        with self._sf() as session:
            rows = session.execute(
                select(QuoteLineRow).where(QuoteLineRow.quote_id == _s(quote_id))
                .order_by(QuoteLineRow.line_number)
            ).scalars().all()
            return [self._row_to_line(r) for r in rows]

    def get_quote_line(self, lid: UUID) -> QuoteLine | None:
        with self._sf() as session:
            row = session.get(QuoteLineRow, _s(lid))
            return self._row_to_line(row) if row else None

    def delete_quote_line(self, lid: UUID) -> bool:
        with self._sf() as session:
            row = session.get(QuoteLineRow, _s(lid))
            if row is None:
                return False
            session.delete(row)
            session.commit()
        return True

    @staticmethod
    def _row_to_line(r: QuoteLineRow) -> QuoteLine:
        return QuoteLine(
            quote_line_id=UUID(r.quote_line_id),
            quote_id=UUID(r.quote_id),
            line_number=r.line_number,
            technical_variant_id=UUID(r.technical_variant_id),
            technical_variant_code=r.technical_variant_code,
            quantity=r.quantity,
            contract_duration_months=r.contract_duration_months,
            annual_mileage_km=r.annual_mileage_km,
            annual_engine_hours=r.annual_engine_hours,
            monthly_mileage_km=r.monthly_mileage_km,
            start_date=r.start_date,
            end_date=r.end_date,
            country_iso=r.country_iso,
            homologation_id=UUID(r.homologation_id) if r.homologation_id else None,
            selected_ecm_provider_id=UUID(r.selected_ecm_provider_id) if r.selected_ecm_provider_id else None,
            selected_service_level_id=UUID(r.selected_service_level_id) if r.selected_service_level_id else None,
            fleet_asset_id=UUID(r.fleet_asset_id) if r.fleet_asset_id else None,
            notes=r.notes,
        )

    # ---------------- Options (SQL) ----------------

    def add_quote_line_option(self, opt: QuoteLineOption) -> QuoteLineOption:
        with self._sf() as session:
            if session.get(QuoteLineRow, _s(opt.quote_line_id)) is None:
                raise ValueError(f"QuoteLine {opt.quote_line_id} inconnue")
            session.add(QuoteLineOptionRow(
                quote_line_option_id=_s(opt.quote_line_option_id),
                quote_line_id=_s(opt.quote_line_id),
                commercial_option_id=_s(opt.commercial_option_id),
                option_code=opt.option_code,
                quantity=opt.quantity,
                unit_price=opt.unit_price,
                billing_unit=opt.billing_unit,
                total_monthly_impact=opt.total_monthly_impact,
                is_included=opt.is_included,
            ))
            session.commit()
            return opt

    def list_quote_line_options(self, line_id: UUID) -> list[QuoteLineOption]:
        with self._sf() as session:
            rows = session.execute(
                select(QuoteLineOptionRow).where(QuoteLineOptionRow.quote_line_id == _s(line_id))
            ).scalars().all()
            return [
                QuoteLineOption(
                    quote_line_option_id=UUID(r.quote_line_option_id),
                    quote_line_id=UUID(r.quote_line_id),
                    commercial_option_id=UUID(r.commercial_option_id),
                    option_code=r.option_code,
                    quantity=r.quantity,
                    unit_price=r.unit_price,
                    billing_unit=r.billing_unit,
                    total_monthly_impact=r.total_monthly_impact,
                    is_included=r.is_included,
                )
                for r in rows
            ]

    # ---------------- PricingCalculation ----------------

    def save_pricing_calculation(self, calc: PricingCalculation) -> PricingCalculation:
        with self._sf() as session:
            # Un seul calcul par ligne (contrainte unique en DB)
            existing = session.execute(
                select(PricingCalculationRow).where(
                    PricingCalculationRow.quote_line_id == _s(calc.quote_line_id)
                )
            ).scalar_one_or_none()
            if existing:
                # Cascade DB supprime les composants + rules automatiquement
                session.delete(existing)
                session.flush()

            session.add(PricingCalculationRow(
                pricing_calculation_id=_s(calc.pricing_calculation_id),
                quote_line_id=_s(calc.quote_line_id),
                calculated_at=calc.calculated_at,
                dl_price_book_version_id=_s(calc.dl_price_book_version_id) if calc.dl_price_book_version_id else None,
                hm_price_book_version_id=_s(calc.hm_price_book_version_id) if calc.hm_price_book_version_id else None,
                om_price_book_version_id=_s(calc.om_price_book_version_id) if calc.om_price_book_version_id else None,
                dl_version_label=calc.dl_version_label,
                hm_version_label=calc.hm_version_label,
                om_version_label=calc.om_version_label,
                dl_monthly=calc.dl_monthly,
                hm_monthly_provisioned=calc.hm_monthly_provisioned,
                om_monthly=calc.om_monthly,
                options_monthly=calc.options_monthly,
                total_monthly=calc.total_monthly,
                total_contract=calc.total_contract,
                floor_applied=calc.floor_applied,
                cap_applied=calc.cap_applied,
                is_under_floor=calc.is_under_floor,
                niveau_validation=calc.niveau_validation,
                warnings=list(calc.warnings),
            ))
            session.commit()
            return calc

    def get_pricing_calculation_for_line(self, line_id: UUID) -> PricingCalculation | None:
        with self._sf() as session:
            row = session.execute(
                select(PricingCalculationRow).where(
                    PricingCalculationRow.quote_line_id == _s(line_id)
                )
            ).scalar_one_or_none()
            return self._row_to_calc(row) if row else None

    @staticmethod
    def _row_to_calc(r: PricingCalculationRow) -> PricingCalculation:
        return PricingCalculation(
            pricing_calculation_id=UUID(r.pricing_calculation_id),
            quote_line_id=UUID(r.quote_line_id),
            calculated_at=r.calculated_at,
            dl_price_book_version_id=UUID(r.dl_price_book_version_id) if r.dl_price_book_version_id else None,
            hm_price_book_version_id=UUID(r.hm_price_book_version_id) if r.hm_price_book_version_id else None,
            om_price_book_version_id=UUID(r.om_price_book_version_id) if r.om_price_book_version_id else None,
            dl_version_label=r.dl_version_label,
            hm_version_label=r.hm_version_label,
            om_version_label=r.om_version_label,
            dl_monthly=r.dl_monthly,
            hm_monthly_provisioned=r.hm_monthly_provisioned,
            om_monthly=r.om_monthly,
            options_monthly=r.options_monthly,
            total_monthly=r.total_monthly,
            total_contract=r.total_contract,
            floor_applied=r.floor_applied,
            cap_applied=r.cap_applied,
            is_under_floor=r.is_under_floor,
            niveau_validation=r.niveau_validation,
            warnings=list(r.warnings or []),
        )

    # ---------------- Components et Rules (SQL) ----------------

    def save_component(self, comp: PricingCalculationComponent) -> PricingCalculationComponent:
        with self._sf() as session:
            if session.get(PricingCalculationRow, _s(comp.pricing_calculation_id)) is None:
                raise ValueError(f"PricingCalculation {comp.pricing_calculation_id} inconnue")
            session.add(PricingCalculationComponentRow(
                component_id=_s(comp.component_id),
                pricing_calculation_id=_s(comp.pricing_calculation_id),
                component_type=comp.component_type,
                component_code=comp.component_code,
                description=comp.description,
                monthly_amount=comp.monthly_amount,
                annual_amount=comp.annual_amount,
                is_visible_to_client=comp.is_visible_to_client,
            ))
            session.commit()
            return comp

    def list_components(self, calc_id: UUID) -> list[PricingCalculationComponent]:
        with self._sf() as session:
            rows = session.execute(
                select(PricingCalculationComponentRow).where(
                    PricingCalculationComponentRow.pricing_calculation_id == _s(calc_id)
                )
            ).scalars().all()
            return [
                PricingCalculationComponent(
                    component_id=UUID(r.component_id),
                    pricing_calculation_id=UUID(r.pricing_calculation_id),
                    component_type=r.component_type,
                    component_code=r.component_code,
                    description=r.description,
                    monthly_amount=r.monthly_amount,
                    annual_amount=r.annual_amount,
                    is_visible_to_client=r.is_visible_to_client,
                )
                for r in rows
            ]

    def save_applied_rule(self, r: AppliedPricingRule) -> AppliedPricingRule:
        with self._sf() as session:
            if session.get(PricingCalculationRow, _s(r.pricing_calculation_id)) is None:
                raise ValueError(f"PricingCalculation {r.pricing_calculation_id} inconnue")
            session.add(AppliedPricingRuleRow(
                applied_rule_id=_s(r.applied_rule_id),
                pricing_calculation_id=_s(r.pricing_calculation_id),
                rule_kind=r.rule_kind.value,
                rule_code=r.rule_code,
                rule_description=r.rule_description,
                impact_percentage=r.impact_percentage,
                impact_monthly_amount=r.impact_monthly_amount,
                approved_by=r.approved_by,
                approved_at=r.approved_at,
                reference=r.reference,
            ))
            session.commit()
            return r

    def list_applied_rules(self, calc_id: UUID) -> list[AppliedPricingRule]:
        with self._sf() as session:
            rows = session.execute(
                select(AppliedPricingRuleRow).where(
                    AppliedPricingRuleRow.pricing_calculation_id == _s(calc_id)
                )
            ).scalars().all()
            from .quote import PricingRuleKind
            return [
                AppliedPricingRule(
                    applied_rule_id=UUID(r.applied_rule_id),
                    pricing_calculation_id=UUID(r.pricing_calculation_id),
                    rule_kind=PricingRuleKind(r.rule_kind),
                    rule_code=r.rule_code,
                    rule_description=r.rule_description,
                    impact_percentage=r.impact_percentage,
                    impact_monthly_amount=r.impact_monthly_amount,
                    approved_by=r.approved_by,
                    approved_at=r.approved_at,
                    reference=r.reference,
                )
                for r in rows
            ]
