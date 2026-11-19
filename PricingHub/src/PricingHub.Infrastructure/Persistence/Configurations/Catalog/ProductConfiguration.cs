using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using PricingHub.Domain.Catalog.ProductAggregate;
using PricingHub.Infrastructure.Persistence.Conversions;

namespace PricingHub.Infrastructure.Persistence.Configurations.Catalog;

public sealed class ProductConfiguration : IEntityTypeConfiguration<Product>
{
    public void Configure(EntityTypeBuilder<Product> builder)
    {
        builder.ToTable("products");

        builder.HasKey(p => p.Id);
        builder.Property(p => p.Id)
            .HasConversion(ValueConverters.ForString<ProductCode>(x => x.Value, ProductCode.Of))
            .HasColumnName("code")
            .HasMaxLength(50);

        builder.Property(p => p.Name).HasColumnName("name").HasMaxLength(200).IsRequired();

        builder.Ignore(p => p.DomainEvents);
    }
}
