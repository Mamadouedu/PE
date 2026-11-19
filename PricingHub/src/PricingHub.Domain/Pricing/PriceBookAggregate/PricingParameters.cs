using PricingHub.SharedKernel;

namespace PricingHub.Domain.Pricing.PriceBookAggregate;

/// <summary>
/// Paramètres globaux de tarification (section 6 du cahier des charges),
/// tous modifiables sans développement via une nouvelle version du
/// référentiel. Équivalent du modèle Python <c>Parametres</c> ;
/// <see cref="Defaults"/> reprend exactement les mêmes valeurs par défaut.
/// </summary>
public sealed record PricingParameters(
    Percentage HeavyMaintenanceMargin,
    Percentage OperatingMaintenanceMargin,
    Percentage InsuranceMargin,
    Percentage MaximumDiscount,
    Percentage AdditionalMileageSurcharge,
    Percentage KamDiscountThreshold,
    Percentage ResidualValueBonusHm8,
    Percentage ResidualValueBonusHm16,
    Percentage ResidualValueFloorRate,
    decimal ValueLossPerKilometerOutOfReference,
    Percentage AnnualIndexation,
    int OfferValidityDays,
    int MaxCampaignDurationMonths,
    int MaxLocomotivesPerContract,
    int HighRatingThreshold,
    int MaxHighRatingDurationMonths,
    Money MinimumDryLease)
{
    public static PricingParameters Defaults(Currency currency) => new(
        HeavyMaintenanceMargin: Percentage.FromRatio(0.15m),
        OperatingMaintenanceMargin: Percentage.FromRatio(0.12m),
        InsuranceMargin: Percentage.FromRatio(0.05m),
        MaximumDiscount: Percentage.FromRatio(0.10m),
        AdditionalMileageSurcharge: Percentage.FromRatio(0.25m),
        KamDiscountThreshold: Percentage.FromRatio(0.05m),
        ResidualValueBonusHm8: Percentage.FromRatio(0.04m),
        ResidualValueBonusHm16: Percentage.FromRatio(0.04m),
        ResidualValueFloorRate: Percentage.FromRatio(0.08m),
        ValueLossPerKilometerOutOfReference: 0.20m,
        AnnualIndexation: Percentage.FromRatio(0.02m),
        OfferValidityDays: 30,
        MaxCampaignDurationMonths: 3,
        MaxLocomotivesPerContract: 2,
        HighRatingThreshold: 7,
        MaxHighRatingDurationMonths: 1,
        MinimumDryLease: Money.Of(10500.0m, currency));
}
