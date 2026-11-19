using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Design;

namespace PricingHub.Infrastructure.Persistence;

/// <summary>
/// Fabrique utilisée uniquement par les outils (<c>dotnet ef</c>) pour
/// générer et appliquer les migrations en ligne de commande — le projet
/// Infrastructure n'a pas de point d'entrée ni de configuration propre,
/// c'est l'API qui configure le vrai <see cref="PricingHubDbContext"/> au
/// runtime (voir <c>PricingHub.Api/Program.cs</c>). La chaîne de connexion
/// vient de la même variable d'environnement <c>DATABASE_URL</c> que le
/// prototype Python, pour rester cohérent entre les deux stacks.
/// </summary>
public sealed class PricingHubDbContextFactory : IDesignTimeDbContextFactory<PricingHubDbContext>
{
    public PricingHubDbContext CreateDbContext(string[] args)
    {
        var connectionString = Environment.GetEnvironmentVariable("PRICINGHUB_DATABASE_URL")
            ?? "Host=localhost;Database=pricinghub_dev;Username=pricing;Password=pricing";

        var optionsBuilder = new DbContextOptionsBuilder<PricingHubDbContext>();
        optionsBuilder.UseNpgsql(connectionString);

        return new PricingHubDbContext(optionsBuilder.Options);
    }
}
