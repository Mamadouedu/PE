using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Infrastructure.Persistence.Configurations.Catalog;
using PricingHub.Infrastructure.Persistence.Conversions;

namespace PricingHub.Infrastructure.Persistence.Configurations.Sales;

public sealed class CustomerConfiguration : IEntityTypeConfiguration<Customer>
{
    public void Configure(EntityTypeBuilder<Customer> builder)
    {
        builder.ToTable("customers");

        builder.HasKey(c => c.Id);
        builder.Property(c => c.Id)
            .HasConversion(ValueConverters.ForString<CustomerCode>(x => x.Value, CustomerCode.Of))
            .HasColumnName("code")
            .HasMaxLength(50);

        builder.Property(c => c.Name).HasColumnName("name").HasMaxLength(200).IsRequired();
        builder.Property(c => c.CreditRating).HasColumnName("credit_rating");
        builder.Property(c => c.Segment).HasColumnName("segment").HasMaxLength(100);
        builder.Property(c => c.PaysInAdvance).HasColumnName("pays_in_advance");

        // Propriété directe d'une entité top-level (pas imbriqué dans un type possédé) : ComplexProperty, éprouvé.
        builder.ComplexProperty(c => c.CashDeposit, money => ModelConfiguration.ConfigureMoney(money, "cash_deposit"));

        builder.Ignore(c => c.DomainEvents);
    }
}
