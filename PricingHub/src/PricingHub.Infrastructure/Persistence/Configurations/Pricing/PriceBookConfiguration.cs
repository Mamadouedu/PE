using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.Infrastructure.Persistence.Conversions;
using PricingHub.SharedKernel;

namespace PricingHub.Infrastructure.Persistence.Configurations.Pricing;

/// <summary>
/// La configuration la plus dense du domaine : trois collections possédées
/// (tranches de km, grille Dry lease, Budget Plan — chacune sans identité
/// propre, donc des types possédés, pas des entités), plus
/// <see cref="PricingParameters"/> en <c>ComplexProperty</c> imbriqué.
/// Chaque collection privée (<c>_mileageBrackets</c>, etc.) n'a pas de
/// setter public ; EF doit donc lire/écrire directement le champ
/// (<c>PropertyAccessMode.Field</c>), jamais la propriété <c>IReadOnlyList</c>.
/// </summary>
public sealed class PriceBookConfiguration : IEntityTypeConfiguration<PriceBook>
{
    public void Configure(EntityTypeBuilder<PriceBook> builder)
    {
        builder.ToTable("price_books");

        builder.HasKey(p => p.Id);
        builder.Property(p => p.Id)
            .HasConversion(ValueConverters.ForInt<PriceBookNumber>(x => x.Value, PriceBookNumber.Of))
            .HasColumnName("number")
            .ValueGeneratedNever();

        builder.Property(p => p.Status).HasColumnName("status").HasConversion<string>().HasMaxLength(20);
        builder.Property(p => p.CreatedAt).HasColumnName("created_at");
        builder.Property(p => p.PublishedAt).HasColumnName("published_at");
        builder.Property(p => p.PublishedBy).HasColumnName("published_by").HasMaxLength(200);

        ConfigureParameters(builder);
        ConfigureMileageBrackets(builder);
        ConfigureDryLeaseGrid(builder);
        ConfigureBudgetPlan(builder);

        builder.Ignore(p => p.DomainEvents);
    }

    private static void ConfigureParameters(EntityTypeBuilder<PriceBook> builder)
    {
        builder.ComplexProperty(p => p.Parameters, parameters =>
        {
            ConfigurePercentage(parameters, x => x.HeavyMaintenanceMargin, "hm_margin");
            ConfigurePercentage(parameters, x => x.OperatingMaintenanceMargin, "om_margin");
            ConfigurePercentage(parameters, x => x.InsuranceMargin, "insurance_margin");
            ConfigurePercentage(parameters, x => x.MaximumDiscount, "maximum_discount");
            ConfigurePercentage(parameters, x => x.AdditionalMileageSurcharge, "additional_mileage_surcharge");
            ConfigurePercentage(parameters, x => x.KamDiscountThreshold, "kam_discount_threshold");
            ConfigurePercentage(parameters, x => x.ResidualValueBonusHm8, "residual_value_bonus_hm8");
            ConfigurePercentage(parameters, x => x.ResidualValueBonusHm16, "residual_value_bonus_hm16");
            ConfigurePercentage(parameters, x => x.ResidualValueFloorRate, "residual_value_floor_rate");
            ConfigurePercentage(parameters, x => x.AnnualIndexation, "annual_indexation");

            parameters.Property(x => x.ValueLossPerKilometerOutOfReference).HasColumnName("value_loss_per_km_out_of_reference");
            parameters.Property(x => x.OfferValidityDays).HasColumnName("offer_validity_days");
            parameters.Property(x => x.MaxCampaignDurationMonths).HasColumnName("max_campaign_duration_months");
            parameters.Property(x => x.MaxLocomotivesPerContract).HasColumnName("max_locomotives_per_contract");
            parameters.Property(x => x.HighRatingThreshold).HasColumnName("high_rating_threshold");
            parameters.Property(x => x.MaxHighRatingDurationMonths).HasColumnName("max_high_rating_duration_months");

            // Money imbriqué dans un ComplexProperty échoue aussi au binding du constructeur
            // (même limitation EF Core 8 que pour les types possédés) : colonne packée.
            parameters.Property(x => x.MinimumDryLease)
                .HasConversion(ValueConverters.ForMoney())
                .HasColumnName("minimum_dry_lease")
                .HasMaxLength(50);
        });
    }

    private static void ConfigurePercentage(
        ComplexPropertyBuilder<PricingParameters> parameters,
        System.Linq.Expressions.Expression<Func<PricingParameters, Percentage>> selector,
        string columnName) =>
        parameters.Property(selector)
            .HasConversion(ValueConverters.ForDecimal<Percentage>(x => x.Value, Percentage.FromRatio))
            .HasColumnName(columnName);

    private static void ConfigureMileageBrackets(EntityTypeBuilder<PriceBook> builder)
    {
        builder.OwnsMany(p => p.MileageBrackets, bracket =>
        {
            bracket.ToTable("price_book_mileage_brackets");
            bracket.WithOwner().HasForeignKey("price_book_number");
            bracket.Property<int>("id");
            bracket.HasKey("price_book_number", "id");

            bracket.Property(x => x.MinKilometers).HasColumnName("min_kilometers");
            bracket.Property(x => x.MaxKilometers).HasColumnName("max_kilometers");
            bracket.Property(x => x.DryLeaseCoefficient).HasColumnName("dry_lease_coefficient");
            bracket.Property(x => x.HeavyMaintenanceCoefficient).HasColumnName("heavy_maintenance_coefficient");
            bracket.Property(x => x.OperatingMaintenanceCoefficient).HasColumnName("operating_maintenance_coefficient");
        });

        builder.Navigation(p => p.MileageBrackets).UsePropertyAccessMode(PropertyAccessMode.Field);
    }

    private static void ConfigureDryLeaseGrid(EntityTypeBuilder<PriceBook> builder)
    {
        builder.OwnsMany(p => p.DryLeaseGrid, grid =>
        {
            grid.ToTable("price_book_dry_lease_grid");
            grid.WithOwner().HasForeignKey("price_book_number");
            grid.Property<int>("id");
            grid.HasKey("price_book_number", "id");

            grid.Property(x => x.ModelCode)
                .HasConversion(ValueConverters.ForString<ModelCode>(x => x.Value, ModelCode.Of))
                .HasColumnName("model_code")
                .HasMaxLength(50);

            // DurationBracket en colonne packée, pas OwnsOne : voir ValueConverters.ForDurationBracket.
            grid.Property(x => x.DurationBracket).HasConversion(ValueConverters.ForDurationBracket()).HasColumnName("duration_bracket").HasMaxLength(30);

            // Money en colonne packée, pas ComplexProperty/OwnsOne : voir ValueConverters.ForMoney.
            grid.Property(x => x.MonthlyRent).HasConversion(ValueConverters.ForMoney()).HasColumnName("monthly_rent").HasMaxLength(50);
        });

        builder.Navigation(p => p.DryLeaseGrid).UsePropertyAccessMode(PropertyAccessMode.Field);
    }

    private static void ConfigureBudgetPlan(EntityTypeBuilder<PriceBook> builder)
    {
        builder.OwnsMany(p => p.BudgetPlan, bp =>
        {
            bp.ToTable("price_book_budget_plan");
            bp.WithOwner().HasForeignKey("price_book_number");
            bp.Property<int>("id");
            bp.HasKey("price_book_number", "id");

            bp.Property(x => x.ModelCode)
                .HasConversion(ValueConverters.ForString<ModelCode>(x => x.Value, ModelCode.Of))
                .HasColumnName("model_code")
                .HasMaxLength(50);

            bp.Property(x => x.FiscalYear).HasColumnName("fiscal_year").HasMaxLength(10);

            // MileageBracket en colonne packée, pas OwnsOne : voir ValueConverters.ForMileageBracket.
            bp.Property(x => x.MileageBracket).HasConversion(ValueConverters.ForMileageBracket()).HasColumnName("mileage_bracket").HasMaxLength(100);

            // Money en colonne packée, pas ComplexProperty/OwnsOne : voir ValueConverters.ForMoney.
            bp.Property(x => x.HeavyMaintenanceFloor).HasConversion(ValueConverters.ForMoney()).HasColumnName("hm_floor").HasMaxLength(50);
            bp.Property(x => x.OperatingMaintenanceFloor).HasConversion(ValueConverters.ForMoney()).HasColumnName("om_floor").HasMaxLength(50);
        });

        builder.Navigation(p => p.BudgetPlan).UsePropertyAccessMode(PropertyAccessMode.Field);
    }
}
