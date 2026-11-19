using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.Domain.Workflow.ApprovalRequestAggregate;
using PricingHub.Infrastructure.Persistence.Configurations.Catalog;
using PricingHub.Infrastructure.Persistence.Conversions;

namespace PricingHub.Infrastructure.Persistence.Configurations.Workflow;

public sealed class ApprovalRequestConfiguration : IEntityTypeConfiguration<ApprovalRequest>
{
    public void Configure(EntityTypeBuilder<ApprovalRequest> builder)
    {
        builder.ToTable("approval_requests");

        builder.HasKey(a => a.Id);
        builder.Property(a => a.Id)
            .HasConversion(ValueConverters.ForInt<ApprovalRequestId>(x => x.Value, ApprovalRequestId.Of))
            .HasColumnName("number")
            .ValueGeneratedNever();

        builder.Property(a => a.Status).HasColumnName("status").HasConversion<string>().HasMaxLength(20);
        builder.Property(a => a.ValidationLevel).HasColumnName("validation_level");
        builder.Property(a => a.RequestedBy).HasColumnName("requested_by").HasMaxLength(200).IsRequired();
        builder.Property(a => a.Justification).HasColumnName("justification").HasMaxLength(4000).IsRequired();

        builder.Property(a => a.QuoteId)
            .HasConversion(ValueConverters.ForGuid<QuoteId>(x => x.Value, QuoteId.Of))
            .HasColumnName("quote_id");

        builder.Property(a => a.QuoteVersion)
            .HasConversion(ValueConverters.ForInt<QuoteVersionNumber>(x => x.Value, QuoteVersionNumber.Of))
            .HasColumnName("quote_version_number");

        builder.Property(a => a.PriceBookNumber)
            .HasConversion(ValueConverters.ForInt<PriceBookNumber>(x => x.Value, PriceBookNumber.Of))
            .HasColumnName("price_book_number");

        builder.Property(a => a.CustomerCode)
            .HasConversion(ValueConverters.ForString<CustomerCode>(x => x.Value, CustomerCode.Of))
            .HasColumnName("customer_code")
            .HasMaxLength(50)
            .IsRequired();

        builder.Property(a => a.ModelCode)
            .HasConversion(ValueConverters.ForString<ModelCode>(x => x.Value, ModelCode.Of))
            .HasColumnName("model_code")
            .HasMaxLength(50)
            .IsRequired();

        // Propriété directe d'une entité top-level : ComplexProperty, éprouvé (pas d'imbrication possédée ici).
        builder.ComplexProperty(a => a.MonthlyRetainedAmount, money => ModelConfiguration.ConfigureMoney(money, "monthly_retained_amount"));

        builder.Property(a => a.ValidatorEmail).HasColumnName("validator_email").HasMaxLength(320);
        builder.Property(a => a.RequestedAt).HasColumnName("requested_at");
        builder.Property(a => a.DecidedAt).HasColumnName("decided_at");
        builder.Property(a => a.DecidedBy).HasColumnName("decided_by").HasMaxLength(200);
        builder.Property(a => a.DecisionComment).HasColumnName("decision_comment").HasMaxLength(2000);

        builder.Ignore(a => a.DomainEvents);
    }
}
