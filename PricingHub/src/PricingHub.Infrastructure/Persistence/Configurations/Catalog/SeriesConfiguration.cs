using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using PricingHub.Domain.Catalog.ProductAggregate;
using PricingHub.Domain.Catalog.SeriesAggregate;
using PricingHub.Infrastructure.Persistence.Conversions;

namespace PricingHub.Infrastructure.Persistence.Configurations.Catalog;

public sealed class SeriesConfiguration : IEntityTypeConfiguration<Series>
{
    public void Configure(EntityTypeBuilder<Series> builder)
    {
        builder.ToTable("series");

        builder.HasKey(s => s.Id);
        builder.Property(s => s.Id)
            .HasConversion(ValueConverters.ForString<SeriesCode>(x => x.Value, SeriesCode.Of))
            .HasColumnName("code")
            .HasMaxLength(50);

        builder.Property(s => s.ProductCode)
            .HasConversion(ValueConverters.ForString<ProductCode>(x => x.Value, ProductCode.Of))
            .HasColumnName("product_code")
            .HasMaxLength(50)
            .IsRequired();

        builder.Property(s => s.Name).HasColumnName("name").HasMaxLength(200).IsRequired();

        builder.HasIndex(s => s.ProductCode);

        builder.Ignore(s => s.DomainEvents);
    }
}
