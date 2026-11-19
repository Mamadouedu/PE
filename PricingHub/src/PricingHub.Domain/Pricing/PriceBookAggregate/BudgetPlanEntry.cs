using PricingHub.Domain.Catalog.SeriesAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Pricing.PriceBookAggregate;

/// <summary>Plancher BP (Budget Plan) HM / OM pour une série × tranche de
/// km — le prix retenu ne peut jamais descendre en dessous, quelle que soit
/// la remise négociée (section 12.3). Équivalent du modèle Python
/// <c>BudgetPlanEntry</c>.</summary>
public sealed class BudgetPlanEntry
{
    public SeriesCode SeriesCode { get; }
    public MileageBracket MileageBracket { get; }
    public Money HeavyMaintenanceFloor { get; }
    public Money OperatingMaintenanceFloor { get; }
    public string FiscalYear { get; }

    private BudgetPlanEntry(
        SeriesCode seriesCode,
        MileageBracket mileageBracket,
        Money heavyMaintenanceFloor,
        Money operatingMaintenanceFloor,
        string fiscalYear)
    {
        SeriesCode = seriesCode;
        MileageBracket = mileageBracket;
        HeavyMaintenanceFloor = heavyMaintenanceFloor;
        OperatingMaintenanceFloor = operatingMaintenanceFloor;
        FiscalYear = fiscalYear;
    }

    public static Result<BudgetPlanEntry> Create(
        SeriesCode seriesCode,
        MileageBracket mileageBracket,
        Money heavyMaintenanceFloor,
        Money operatingMaintenanceFloor,
        string fiscalYear)
    {
        if (string.IsNullOrWhiteSpace(fiscalYear))
        {
            return Result.Failure<BudgetPlanEntry>("L'exercice du BP ne peut pas être vide.");
        }

        if (heavyMaintenanceFloor.Amount < 0m || operatingMaintenanceFloor.Amount < 0m)
        {
            return Result.Failure<BudgetPlanEntry>("Un plancher BP ne peut pas être négatif.");
        }

        return Result.Success(new BudgetPlanEntry(
            seriesCode, mileageBracket, heavyMaintenanceFloor, operatingMaintenanceFloor, fiscalYear));
    }
}
