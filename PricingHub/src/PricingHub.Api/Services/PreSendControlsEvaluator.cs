using PricingHub.Api.Contracts;
using PricingHub.Domain.Pricing;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.Api.Services;

/// <summary>
/// Les 8 contrôles avant envoi — section 6.4 du cahier des charges.
/// Porté depuis <c>engine._controles_avant_envoi</c> (Python). Vit dans
/// l'API, pas dans le domaine : il traverse Sales (Quote, Customer) et n'a
/// pas de notion de flotte (pas de <c>Locomotive</c> dans ce domaine pour
/// l'instant — C8 reste donc toujours "hors contrôle").
///
/// Appelé AVANT <see cref="Quote.ApplyCalculation"/>, sur les
/// <see cref="QuoteLine"/> que <see cref="QuoteCalculationService"/>
/// construit lui-même en amont (mêmes briques, même prix négocié) : C6 et
/// C7 ont besoin du statut des lignes et de la perte de valeur mensuelle,
/// que seul un calcul déjà fait peut donner.
/// </summary>
public static class PreSendControlsEvaluator
{
    public static IReadOnlyList<ControlResultResponse> Evaluate(
        bool isCampaign,
        int contractDurationMonths,
        int quantity,
        CustomerCode customerCode,
        Customer? customer,
        IReadOnlySet<PriceLine> includedLines,
        IReadOnlyDictionary<PriceLine, QuoteLine> lines,
        Money monthlyValueLoss,
        PricingParameters parameters)
    {
        var controls = new List<ControlResultResponse>
        {
            EvaluateCampaignDuration(isCampaign, contractDurationMonths, parameters),
            EvaluateLocomotiveCount(quantity, parameters),
            EvaluateCustomerRating(contractDurationMonths, customerCode, customer, parameters),
            EvaluateInsuranceIncluded(includedLines),
            EvaluatePaymentGuarantee(customerCode, customer),
            EvaluateNoLineBelowFloor(lines),
            EvaluateDryLeaseCoversValueLoss(lines, monthlyValueLoss),
            EvaluateFleetAssignment(),
        };

        return controls;
    }

    private static ControlResultResponse EvaluateCampaignDuration(bool isCampaign, int contractDurationMonths, PricingParameters parameters)
    {
        if (!isCampaign)
        {
            return new ControlResultResponse(
                "C1_DUREE_CAMPAGNE", "Durée ≤ durée maximale de campagne", true, "non applicable (offre hors campagne)");
        }

        var ok = contractDurationMonths <= parameters.MaxCampaignDurationMonths;
        return new ControlResultResponse(
            "C1_DUREE_CAMPAGNE", "Durée ≤ durée maximale de campagne", ok,
            $"{contractDurationMonths} mois (max campagne {parameters.MaxCampaignDurationMonths})");
    }

    private static ControlResultResponse EvaluateLocomotiveCount(int quantity, PricingParameters parameters)
    {
        var ok = quantity <= parameters.MaxLocomotivesPerContract;
        return new ControlResultResponse(
            "C2_NB_LOCOS", "Nombre de locos ≤ maximum par contrat", ok,
            $"{quantity} loco(s) (max {parameters.MaxLocomotivesPerContract})");
    }

    private static ControlResultResponse EvaluateCustomerRating(
        int contractDurationMonths, CustomerCode customerCode, Customer? customer, PricingParameters parameters)
    {
        const string label = "Client à rating élevé : durée courte et paiement d'avance";

        if (customer is null)
        {
            return new ControlResultResponse("C3_CLIENT_RATING", label, false, $"Client {customerCode} introuvable au référentiel");
        }

        if (customer.HasHighCreditRisk(parameters.HighRatingThreshold))
        {
            var ok = contractDurationMonths <= parameters.MaxHighRatingDurationMonths && customer.PaysInAdvance;
            return new ControlResultResponse(
                "C3_CLIENT_RATING", label, ok, $"rating {customer.CreditRating} > seuil {parameters.HighRatingThreshold}");
        }

        return new ControlResultResponse(
            "C3_CLIENT_RATING", label, true, $"rating {customer.CreditRating} ≤ seuil {parameters.HighRatingThreshold}");
    }

    private static ControlResultResponse EvaluateInsuranceIncluded(IReadOnlySet<PriceLine> includedLines)
    {
        var ok = includedLines.Contains(PriceLine.Insurance);
        return new ControlResultResponse("C4_ASSURANCE_INCLUSE", "Assurance incluse", ok, ok.ToString());
    }

    private static ControlResultResponse EvaluatePaymentGuarantee(CustomerCode customerCode, Customer? customer)
    {
        const string label = "Garantie de paiement (cash deposit ou paiement d'avance)";

        if (customer is null)
        {
            return new ControlResultResponse("C5_GARANTIE_PAIEMENT", label, false, $"Client {customerCode} introuvable au référentiel");
        }

        return new ControlResultResponse(
            "C5_GARANTIE_PAIEMENT", label, customer.HasPaymentGuarantee,
            $"cash_deposit={customer.CashDeposit.Amount}, paiement_avance={customer.PaysInAdvance}");
    }

    private static ControlResultResponse EvaluateNoLineBelowFloor(IReadOnlyDictionary<PriceLine, QuoteLine> lines)
    {
        var hmOk = !lines.TryGetValue(PriceLine.HeavyMaintenance, out var hm) || hm.Status != QuoteLineStatus.BelowFloor;
        var omOk = !lines.TryGetValue(PriceLine.OperatingMaintenance, out var om) || om.Status != QuoteLineStatus.BelowFloor;
        return new ControlResultResponse(
            "C6_AUCUN_PRIX_SOUS_PLANCHER_BP", "Aucun prix sous le plancher BP", hmOk && omOk, "HM/OM comparés au BP");
    }

    private static ControlResultResponse EvaluateDryLeaseCoversValueLoss(
        IReadOnlyDictionary<PriceLine, QuoteLine> lines, Money monthlyValueLoss)
    {
        const string code = "C7_DL_COUVRE_PERTE_VALEUR";
        const string label = "Le Dry lease couvre la perte de valeur mensuelle";

        if (!lines.TryGetValue(PriceLine.DryLease, out var dryLease) || dryLease.Status == QuoteLineStatus.Excluded)
        {
            return new ControlResultResponse(code, label, true, "Dry lease exclu de l'offre");
        }

        var ok = dryLease.RetainedPrice >= monthlyValueLoss;
        return new ControlResultResponse(
            code, label, ok, $"DL retenu {dryLease.RetainedPrice} vs perte de valeur mensuelle {monthlyValueLoss}");
    }

    /// <summary>Pas de <c>Locomotive</c>/flotte dans ce domaine pour
    /// l'instant (voir ProductAggregate/SeriesAggregate/ModelAggregate) :
    /// toujours hors contrôle, comme le cas Python "aucune locomotive
    /// affectée".</summary>
    private static ControlResultResponse EvaluateFleetAssignment() => new(
        "C8_LOCO_DISPONIBLE_BONNE_SERIE", "Locomotive disponible et de la bonne série", true,
        "Aucune locomotive de flotte affectée (hors contrôle)");
}
