using PricingHub.Domain.Catalog.SeriesAggregate;
using PricingHub.Domain.Common;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Catalog.ModelAggregate;

/// <summary>
/// Un modèle — la variante technique précise d'une série (ex. série Vectron
/// → modèles Vectron AC, Vectron DC, Vectron MS), chacune avec ses propres
/// coûts. C'est le référentiel catalogue le plus important : il remplace
/// directement l'onglet « Models » du Price Configurator Excel d'Akiem, et
/// c'est lui — pas <see cref="Series"/> — qui porte les données qui
/// alimentent le prix : valeur à neuf, durée de vie, coûts de maintenance,
/// taux d'assurance.
///
/// Porte des <i>données</i>, pas des <i>formules</i> : le calcul du prix
/// (VR(a, k), coût HM/km appliqué à une configuration donnée, etc.) vit
/// dans <c>Pricing.Calculations</c>, qui lit un <see cref="Model"/> en
/// entrée. Équivalent du modèle Python <c>Serie</c> (<c>referentiel.py</c>)
/// — porté champ à champ, à ce niveau plus fin du catalogue réel.
/// </summary>
public sealed class Model : AggregateRoot<ModelCode>
{
    public SeriesCode SeriesCode { get; private set; }
    public string Name { get; private set; } = string.Empty;

    /// <summary>Valeur à neuf (VN).</summary>
    public Money NewValue { get; private set; }

    /// <summary>Durée de vie économique, en années (L — 30 ans chez Akiem).</summary>
    public int ServiceLifeYears { get; private set; }

    /// <summary>Taux de valeur résiduelle en fin de vie (v — 10 % de VN à l'âge L).</summary>
    public Percentage EndOfLifeResidualRate { get; private set; }

    /// <summary>Kilométrage annuel de référence (K_ref) utilisé pour calculer
    /// les km cumulés théoriques à un âge donné, et le kilométrage
    /// supplémentaire facturable au-delà.</summary>
    public Mileage ReferenceAnnualMileage { get; private set; }

    /// <summary>Coût de la visite HM à 8 ans.</summary>
    public Money HeavyMaintenance8YearCost { get; private set; }

    /// <summary>Coût de la visite HM à 16 ans.</summary>
    public Money HeavyMaintenance16YearCost { get; private set; }

    /// <summary>Part fixe de l'Operation Maintenance (€/an).</summary>
    public Money OperatingMaintenanceFixedCost { get; private set; }

    /// <summary>Part variable de l'Operation Maintenance (€/km).</summary>
    public decimal OperatingMaintenanceVariableCostPerKilometer { get; private set; }

    /// <summary>Taux d'assurance annuel, appliqué à la valeur assurée du matériel.</summary>
    public Percentage AnnualInsuranceRate { get; private set; }

#pragma warning disable CS8618
    private Model()
    {
    }
#pragma warning restore CS8618

    private Model(
        ModelCode code,
        SeriesCode seriesCode,
        string name,
        Money newValue,
        int serviceLifeYears,
        Percentage endOfLifeResidualRate,
        Mileage referenceAnnualMileage,
        Money heavyMaintenance8YearCost,
        Money heavyMaintenance16YearCost,
        Money operatingMaintenanceFixedCost,
        decimal operatingMaintenanceVariableCostPerKilometer,
        Percentage annualInsuranceRate)
        : base(code)
    {
        SeriesCode = seriesCode;
        Name = name;
        NewValue = newValue;
        ServiceLifeYears = serviceLifeYears;
        EndOfLifeResidualRate = endOfLifeResidualRate;
        ReferenceAnnualMileage = referenceAnnualMileage;
        HeavyMaintenance8YearCost = heavyMaintenance8YearCost;
        HeavyMaintenance16YearCost = heavyMaintenance16YearCost;
        OperatingMaintenanceFixedCost = operatingMaintenanceFixedCost;
        OperatingMaintenanceVariableCostPerKilometer = operatingMaintenanceVariableCostPerKilometer;
        AnnualInsuranceRate = annualInsuranceRate;
    }

    public static Result<Model> Create(
        ModelCode code,
        SeriesCode seriesCode,
        string name,
        Money newValue,
        int serviceLifeYears,
        Percentage endOfLifeResidualRate,
        Mileage referenceAnnualMileage,
        Money heavyMaintenance8YearCost,
        Money heavyMaintenance16YearCost,
        Money operatingMaintenanceFixedCost,
        decimal operatingMaintenanceVariableCostPerKilometer,
        Percentage annualInsuranceRate)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            return Result.Failure<Model>("Le nom du modèle ne peut pas être vide.");
        }

        if (newValue.Amount <= 0m)
        {
            return Result.Failure<Model>("La valeur à neuf doit être strictement positive.");
        }

        if (serviceLifeYears <= 0)
        {
            return Result.Failure<Model>("La durée de vie doit être strictement positive.");
        }

        if (operatingMaintenanceVariableCostPerKilometer < 0m)
        {
            return Result.Failure<Model>("Le coût OM variable au km ne peut pas être négatif.");
        }

        return Result.Success(new Model(
            code,
            seriesCode,
            name,
            newValue,
            serviceLifeYears,
            endOfLifeResidualRate,
            referenceAnnualMileage,
            heavyMaintenance8YearCost,
            heavyMaintenance16YearCost,
            operatingMaintenanceFixedCost,
            operatingMaintenanceVariableCostPerKilometer,
            annualInsuranceRate));
    }

    /// <summary>Coût HM ramené au km — (coût 8 ans + coût 16 ans) ÷ (16 ×
    /// km de référence annuel). Sert de base à la provision HM d'une offre
    /// Heavy Maintenance (section 6.1 du cahier des charges).</summary>
    public decimal HeavyMaintenanceCostPerKilometer =>
        (HeavyMaintenance8YearCost.Amount + HeavyMaintenance16YearCost.Amount)
        / (16m * ReferenceAnnualMileage.Kilometers);
}
