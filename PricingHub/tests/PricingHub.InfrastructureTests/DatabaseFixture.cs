using Microsoft.EntityFrameworkCore;
using PricingHub.Infrastructure.Persistence;

namespace PricingHub.InfrastructureTests;

/// <summary>
/// Contre une vraie instance PostgreSQL locale (base <c>pricinghub_dev</c>,
/// démarrée pour le développement), jamais une base en mémoire : le but de
/// ces tests est justement de vérifier que le mapping EF Core — les
/// <c>ComplexProperty</c> pour les value objects, les types possédés pour
/// les collections, les convertisseurs JSON pour les dictionnaires —
/// fonctionne réellement contre Npgsql, pas seulement qu'il compile.
/// </summary>
public static class DatabaseFixture
{
    public static PricingHubDbContext CreateContext()
    {
        var connectionString = Environment.GetEnvironmentVariable("PRICINGHUB_DATABASE_URL")
            ?? "Host=localhost;Database=pricinghub_dev;Username=pricing;Password=pricing";

        var optionsBuilder = new DbContextOptionsBuilder<PricingHubDbContext>();
        optionsBuilder.UseNpgsql(connectionString);

        return new PricingHubDbContext(optionsBuilder.Options);
    }
}
