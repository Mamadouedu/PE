namespace PricingHub.Domain.Pricing;

/// <summary>Une des quatre briques du prix full service — section 6 du
/// cahier des charges. Équivalent de l'énumération Python <c>Brique</c>.</summary>
public enum PriceLine
{
    DryLease,
    HeavyMaintenance,
    OperatingMaintenance,
    Insurance,
}
