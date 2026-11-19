using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Catalog.SeriesAggregate;
using PricingHub.Infrastructure.Persistence.Conversions;
using PricingHub.SharedKernel;

namespace PricingHub.Infrastructure.Persistence.Configurations.Catalog;

/// <summary>
/// Le référentiel catalogue le plus important (voir <see cref="Model"/>) :
/// c'est ici que les quatre <see cref="Money"/> (VN, coûts HM 8/16 ans, OM
/// fixe) sont mappés via <c>ComplexProperty</c> — le mécanisme EF Core 8
/// pour les value objects sans identité propre, vérifié par un test
/// d'intégration contre une vraie base avant d'être généralisé au reste du
/// domaine.
/// </summary>
public sealed class ModelConfiguration : IEntityTypeConfiguration<Model>
{
    public void Configure(EntityTypeBuilder<Model> builder)
    {
        builder.ToTable("models");

        builder.HasKey(m => m.Id);
        builder.Property(m => m.Id)
            .HasConversion(ValueConverters.ForString<ModelCode>(x => x.Value, ModelCode.Of))
            .HasColumnName("code")
            .HasMaxLength(50);

        builder.Property(m => m.SeriesCode)
            .HasConversion(ValueConverters.ForString<SeriesCode>(x => x.Value, SeriesCode.Of))
            .HasColumnName("series_code")
            .HasMaxLength(50)
            .IsRequired();

        builder.Property(m => m.Name).HasColumnName("name").HasMaxLength(200).IsRequired();

        builder.ComplexProperty(m => m.NewValue, money => ConfigureMoney(money, "new_value"));
        builder.ComplexProperty(m => m.HeavyMaintenance8YearCost, money => ConfigureMoney(money, "hm_8y_cost"));
        builder.ComplexProperty(m => m.HeavyMaintenance16YearCost, money => ConfigureMoney(money, "hm_16y_cost"));
        builder.ComplexProperty(m => m.OperatingMaintenanceFixedCost, money => ConfigureMoney(money, "om_fixed_cost"));

        builder.Property(m => m.ServiceLifeYears).HasColumnName("service_life_years");

        builder.Property(m => m.EndOfLifeResidualRate)
            .HasConversion(ValueConverters.ForDecimal<Percentage>(x => x.Value, Percentage.FromRatio))
            .HasColumnName("end_of_life_residual_rate");

        builder.Property(m => m.AnnualInsuranceRate)
            .HasConversion(ValueConverters.ForDecimal<Percentage>(x => x.Value, Percentage.FromRatio))
            .HasColumnName("annual_insurance_rate");

        builder.Property(m => m.ReferenceAnnualMileage)
            .HasConversion(ValueConverters.ForDecimal<Mileage>(x => x.Kilometers, Mileage.FromKilometers))
            .HasColumnName("reference_annual_mileage");

        builder.Property(m => m.OperatingMaintenanceVariableCostPerKilometer).HasColumnName("om_variable_cost_per_km");

        builder.Ignore(m => m.HeavyMaintenanceCostPerKilometer);
        builder.Ignore(m => m.DomainEvents);
    }

    /// <summary>Un <see cref="Money"/> (montant + devise) sur deux colonnes
    /// — réutilisé par toute configuration de ce bounded context qui porte
    /// un montant non-nullable.</summary>
    internal static void ConfigureMoney(Microsoft.EntityFrameworkCore.Metadata.Builders.ComplexPropertyBuilder<Money> money, string columnPrefix)
    {
        money.Property(x => x.Amount).HasColumnName($"{columnPrefix}_amount").HasPrecision(18, 4);
        money.Property(x => x.Currency)
            .HasConversion(ValueConverters.ForString<Currency>(x => x.Code, Currency.FromCode))
            .HasColumnName($"{columnPrefix}_currency")
            .HasMaxLength(3);
    }
}
