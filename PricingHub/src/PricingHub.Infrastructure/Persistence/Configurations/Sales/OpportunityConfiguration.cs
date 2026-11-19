using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.OpportunityAggregate;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.Infrastructure.Persistence.Conversions;

namespace PricingHub.Infrastructure.Persistence.Configurations.Sales;

public sealed class OpportunityConfiguration : IEntityTypeConfiguration<Opportunity>
{
    public void Configure(EntityTypeBuilder<Opportunity> builder)
    {
        builder.ToTable("opportunities");

        builder.HasKey(o => o.Id);
        builder.Property(o => o.Id)
            .HasConversion(ValueConverters.ForGuid<OpportunityId>(x => x.Value, OpportunityId.Of))
            .HasColumnName("id")
            .ValueGeneratedNever();

        builder.Property(o => o.CustomerCode)
            .HasConversion(ValueConverters.ForString<CustomerCode>(x => x.Value, CustomerCode.Of))
            .HasColumnName("customer_code")
            .HasMaxLength(50)
            .IsRequired();

        builder.Property(o => o.Title).HasColumnName("title").HasMaxLength(500).IsRequired();
        builder.Property(o => o.Status).HasColumnName("status").HasConversion<string>().HasMaxLength(20);

        builder.Property(o => o.PipedriveDeal)
            .HasConversion(
                deal => deal.HasValue ? deal.Value.DealId : (int?)null,
                dealId => dealId.HasValue ? PipedriveDealReference.Of(dealId.Value) : (PipedriveDealReference?)null)
            .HasColumnName("pipedrive_deal_id");

        builder.Property(o => o.QuoteIds)
            .HasConversion(ValueConverters.ForQuoteIdList(), ValueConverters.QuoteIdListComparer)
            .HasColumnName("quote_ids")
            .HasColumnType("text")
            .UsePropertyAccessMode(PropertyAccessMode.Field);

        builder.Ignore(o => o.DomainEvents);
    }
}
