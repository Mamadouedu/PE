using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Pricing.CampaignAggregate;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.OpportunityAggregate;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.Infrastructure.Persistence.Conversions;
using PricingHub.SharedKernel;

namespace PricingHub.Infrastructure.Persistence.Configurations.Sales;

/// <summary>
/// L'agrégat le plus profond du domaine : <c>Quote</c> → beaucoup de
/// <c>QuoteVersion</c> (<c>OwnsMany</c>) → beaucoup de <c>QuoteLine</c>
/// (<c>OwnsMany</c> imbriqué). Suit la règle établie sur Pricing : jamais
/// de <c>ComplexProperty</c>/<c>OwnsOne</c> à l'intérieur d'un
/// <c>OwnsMany</c> — tout value object à plusieurs champs (<see cref="Money"/>)
/// y est packé en colonne texte via <see cref="ValueConverters"/>, les
/// value objects à un seul champ restent de simples conversions scalaires.
/// </summary>
public sealed class QuoteConfiguration : IEntityTypeConfiguration<Quote>
{
    public void Configure(EntityTypeBuilder<Quote> builder)
    {
        builder.ToTable("quotes");

        builder.HasKey(q => q.Id);
        builder.Property(q => q.Id)
            .HasConversion(ValueConverters.ForGuid<QuoteId>(x => x.Value, QuoteId.Of))
            .HasColumnName("id")
            .ValueGeneratedNever();

        builder.Property(q => q.CustomerCode)
            .HasConversion(ValueConverters.ForString<CustomerCode>(x => x.Value, CustomerCode.Of))
            .HasColumnName("customer_code")
            .HasMaxLength(50)
            .IsRequired();

        builder.Property(q => q.ModelCode)
            .HasConversion(ValueConverters.ForString<ModelCode>(x => x.Value, ModelCode.Of))
            .HasColumnName("model_code")
            .HasMaxLength(50)
            .IsRequired();

        builder.Property(q => q.OpportunityId)
            .HasConversion(
                id => id.HasValue ? id.Value.Value : (Guid?)null,
                value => value.HasValue ? OpportunityId.Of(value.Value) : (OpportunityId?)null)
            .HasColumnName("opportunity_id");

        builder.Property(q => q.CampaignCode)
            .HasConversion(
                code => code.HasValue ? code.Value.Value : null,
                value => value == null ? (CampaignCode?)null : CampaignCode.Of(value))
            .HasColumnName("campaign_code")
            .HasMaxLength(50);

        builder.Property(q => q.AnnualMileage)
            .HasConversion(ValueConverters.ForDecimal<Mileage>(x => x.Kilometers, Mileage.FromKilometers))
            .HasColumnName("annual_mileage");

        builder.Property(q => q.ContractDuration)
            .HasConversion(ValueConverters.ForInt<Duration>(x => x.Months, Duration.FromMonths))
            .HasColumnName("contract_duration_months");

        builder.Property(q => q.Quantity).HasColumnName("quantity");
        builder.Property(q => q.StartDate).HasColumnName("start_date");

        ConfigureVersions(builder);

        builder.Ignore(q => q.DomainEvents);
    }

    private static void ConfigureVersions(EntityTypeBuilder<Quote> builder)
    {
        builder.OwnsMany(q => q.Versions, version =>
        {
            version.ToTable("quote_versions");
            version.WithOwner().HasForeignKey("quote_id");

            version.Property(v => v.Id)
                .HasConversion(ValueConverters.ForInt<QuoteVersionNumber>(x => x.Value, QuoteVersionNumber.Of))
                .HasColumnName("version_number");
            version.HasKey("quote_id", "Id");

            version.Property(v => v.Status).HasColumnName("status").HasConversion<string>().HasMaxLength(20);

            version.Property(v => v.IncludedLines)
                .HasConversion(ValueConverters.ForPriceLineSet(), ValueConverters.PriceLineSetComparer)
                .HasColumnName("included_lines")
                .UsePropertyAccessMode(PropertyAccessMode.Field);

            version.Property(v => v.NegotiatedPrices)
                .HasConversion(ValueConverters.ForNegotiatedPrices(), ValueConverters.NegotiatedPricesComparer)
                .HasColumnName("negotiated_prices")
                .UsePropertyAccessMode(PropertyAccessMode.Field);

            version.Property(v => v.LocomotiveNumber).HasColumnName("locomotive_number").HasMaxLength(100);
            version.Property(v => v.AgeAtStartYears).HasColumnName("age_at_start_years");

            version.Property(v => v.CumulativeMileageAtStart)
                .HasConversion(ValueConverters.ForDecimal<Mileage>(x => x.Kilometers, Mileage.FromKilometers))
                .HasColumnName("cumulative_mileage_at_start");

            version.Property(v => v.HeavyMaintenance8Done).HasColumnName("heavy_maintenance_8_done");
            version.Property(v => v.HeavyMaintenance16Done).HasColumnName("heavy_maintenance_16_done");
            version.Property(v => v.HasFleetAssignment).HasColumnName("has_fleet_assignment");

            version.Property(v => v.PriceBookNumber)
                .HasConversion(
                    number => number.HasValue ? number.Value.Value : (int?)null,
                    value => value.HasValue ? PriceBookNumber.Of(value.Value) : (PriceBookNumber?)null)
                .HasColumnName("price_book_number");

            ConfigureNullableMoney(version, v => v.ResidualValueAtStart, "residual_value_at_start");
            ConfigureNullableMoney(version, v => v.ResidualValueAtEnd, "residual_value_at_end");
            ConfigureNullableMoney(version, v => v.TotalValueLoss, "total_value_loss");
            ConfigureNullableMoney(version, v => v.MonthlyValueLoss, "monthly_value_loss");
            ConfigureNullableMoney(version, v => v.TotalCatalogPerUnitMonthly, "total_catalog_per_unit_monthly");
            ConfigureNullableMoney(version, v => v.TotalRetainedPerUnitMonthly, "total_retained_per_unit_monthly");
            ConfigureNullableMoney(version, v => v.TotalFloorPerUnitMonthly, "total_floor_per_unit_monthly");
            ConfigureNullableMoney(version, v => v.TotalRetainedMonthly, "total_retained_monthly");
            ConfigureNullableMoney(version, v => v.TotalRetainedContract, "total_retained_contract");
            ConfigureNullableMoney(version, v => v.MonthlyReferenceCost, "monthly_reference_cost");

            version.Property(v => v.AdditionalMileagePrice).HasColumnName("additional_mileage_price");
            version.Property(v => v.GlobalDiscount).HasColumnName("global_discount");
            version.Property(v => v.ValidationLevel).HasColumnName("validation_level");

            version.Property(v => v.ValidationLevelReasons)
                .HasConversion(ValueConverters.ForStringList(), ValueConverters.StringListComparer)
                .HasColumnName("validation_level_reasons")
                .UsePropertyAccessMode(PropertyAccessMode.Field);

            version.Property(v => v.CreatedAt).HasColumnName("created_at");
            version.Property(v => v.DecidedAt).HasColumnName("decided_at");
            version.Property(v => v.DecidedBy).HasColumnName("decided_by").HasMaxLength(200);
            version.Property(v => v.DecisionComment).HasColumnName("decision_comment").HasMaxLength(2000);

            // Pas un troisième niveau d'OwnsMany imbriqué (Quote → QuoteVersion → QuoteLine) :
            // EF Core 8 ne résout pas cette profondeur (voir ValueConverters.ForQuoteLines).
            version.Property(v => v.Lines)
                .HasConversion(ValueConverters.ForQuoteLines(), ValueConverters.QuoteLinesComparer)
                .HasColumnName("lines")
                .UsePropertyAccessMode(PropertyAccessMode.Field);
        });

        builder.Navigation(q => q.Versions).UsePropertyAccessMode(PropertyAccessMode.Field);
    }

    private static void ConfigureNullableMoney(
        OwnedNavigationBuilder<Quote, QuoteVersion> version,
        System.Linq.Expressions.Expression<Func<QuoteVersion, Money?>> selector,
        string columnName) =>
        version.Property(selector).HasConversion(ValueConverters.ForMoney()).HasColumnName(columnName).HasMaxLength(50);

}
