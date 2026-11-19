using PricingHub.SharedKernel;

namespace PricingHub.Domain.Pricing.PriceBookAggregate;

/// <summary>
/// Tranche de kilométrage annuel (ex. 80 000 à 200 000 km) et ses trois
/// coefficients multiplicateurs — Dry lease, Heavy maintenance, Operation
/// maintenance. Les coefficients sont de simples multiplicateurs (pas des
/// <see cref="Percentage"/> : ils peuvent dépasser 1), fidèles au modèle
/// Python <c>TrancheKm</c>.
/// </summary>
public sealed class MileageBracket
{
    public decimal MinKilometers { get; }
    public decimal? MaxKilometers { get; }
    public decimal DryLeaseCoefficient { get; }
    public decimal HeavyMaintenanceCoefficient { get; }
    public decimal OperatingMaintenanceCoefficient { get; }

    private MileageBracket(
        decimal minKilometers,
        decimal? maxKilometers,
        decimal dryLeaseCoefficient,
        decimal heavyMaintenanceCoefficient,
        decimal operatingMaintenanceCoefficient)
    {
        MinKilometers = minKilometers;
        MaxKilometers = maxKilometers;
        DryLeaseCoefficient = dryLeaseCoefficient;
        HeavyMaintenanceCoefficient = heavyMaintenanceCoefficient;
        OperatingMaintenanceCoefficient = operatingMaintenanceCoefficient;
    }

    public static Result<MileageBracket> Create(
        decimal minKilometers,
        decimal? maxKilometers,
        decimal dryLeaseCoefficient,
        decimal heavyMaintenanceCoefficient,
        decimal operatingMaintenanceCoefficient)
    {
        if (minKilometers < 0m)
        {
            return Result.Failure<MileageBracket>("Le km minimum ne peut pas être négatif.");
        }

        if (maxKilometers is { } max && max < minKilometers)
        {
            return Result.Failure<MileageBracket>("Le km maximum ne peut pas être inférieur au km minimum.");
        }

        if (dryLeaseCoefficient <= 0m || heavyMaintenanceCoefficient <= 0m || operatingMaintenanceCoefficient <= 0m)
        {
            return Result.Failure<MileageBracket>("Les coefficients de tranche doivent être strictement positifs.");
        }

        return Result.Success(new MileageBracket(
            minKilometers, maxKilometers, dryLeaseCoefficient, heavyMaintenanceCoefficient, operatingMaintenanceCoefficient));
    }

    public bool Contains(decimal annualMileage) =>
        annualMileage >= MinKilometers && (MaxKilometers is null || annualMileage <= MaxKilometers);
}
