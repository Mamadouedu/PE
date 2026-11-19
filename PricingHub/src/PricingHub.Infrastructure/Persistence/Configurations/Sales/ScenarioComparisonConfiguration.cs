using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.Domain.Sales.ScenarioComparisonAggregate;
using PricingHub.Infrastructure.Persistence.Conversions;

namespace PricingHub.Infrastructure.Persistence.Configurations.Sales;

public sealed class ScenarioComparisonConfiguration : IEntityTypeConfiguration<ScenarioComparison>
{
    public void Configure(EntityTypeBuilder<ScenarioComparison> builder)
    {
        builder.ToTable("scenario_comparisons");

        builder.HasKey(s => s.Id);
        builder.Property(s => s.Id)
            .HasConversion(ValueConverters.ForGuid<ScenarioComparisonId>(x => x.Value, ScenarioComparisonId.Of))
            .HasColumnName("id")
            .ValueGeneratedNever();

        builder.Property(s => s.CustomerCode)
            .HasConversion(ValueConverters.ForString<CustomerCode>(x => x.Value, CustomerCode.Of))
            .HasColumnName("customer_code")
            .HasMaxLength(50)
            .IsRequired();

        builder.Property(s => s.Name).HasColumnName("name").HasMaxLength(200).IsRequired();
        builder.Property(s => s.CreatedBy).HasColumnName("created_by").HasMaxLength(200).IsRequired();
        builder.Property(s => s.CreatedAt).HasColumnName("created_at");

        builder.OwnsMany(s => s.Scenarios, entry =>
        {
            entry.ToTable("scenario_comparison_entries");
            entry.WithOwner().HasForeignKey("scenario_comparison_id");
            entry.Property<int>("id");
            entry.HasKey("scenario_comparison_id", "id");

            entry.Property(x => x.Label).HasColumnName("label").HasMaxLength(100);
            entry.Property(x => x.QuoteId)
                .HasConversion(ValueConverters.ForGuid<QuoteId>(x => x.Value, QuoteId.Of))
                .HasColumnName("quote_id");
            entry.Property(x => x.QuoteVersion)
                .HasConversion(ValueConverters.ForInt<QuoteVersionNumber>(x => x.Value, QuoteVersionNumber.Of))
                .HasColumnName("quote_version_number");
        });

        builder.Navigation(s => s.Scenarios).UsePropertyAccessMode(PropertyAccessMode.Field);

        builder.Ignore(s => s.DomainEvents);
    }
}
