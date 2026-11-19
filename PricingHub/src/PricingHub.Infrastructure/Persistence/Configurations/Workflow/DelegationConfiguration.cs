using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using PricingHub.Domain.Workflow.DelegationAggregate;
using PricingHub.Infrastructure.Persistence.Conversions;

namespace PricingHub.Infrastructure.Persistence.Configurations.Workflow;

public sealed class DelegationConfiguration : IEntityTypeConfiguration<Delegation>
{
    public void Configure(EntityTypeBuilder<Delegation> builder)
    {
        builder.ToTable("delegations");

        builder.HasKey(d => d.Id);
        builder.Property(d => d.Id)
            .HasConversion(ValueConverters.ForInt<ValidationLevel>(x => x.Value, ValidationLevel.Of))
            .HasColumnName("validation_level")
            .ValueGeneratedNever();

        builder.Property(d => d.Name).HasColumnName("name").HasMaxLength(200).IsRequired();
        builder.Property(d => d.Email).HasColumnName("email").HasMaxLength(320).IsRequired();
        builder.Property(d => d.AlternateEmail).HasColumnName("alternate_email").HasMaxLength(320);

        builder.Ignore(d => d.DomainEvents);
    }
}
