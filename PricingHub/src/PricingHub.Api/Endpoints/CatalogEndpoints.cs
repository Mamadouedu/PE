using Microsoft.EntityFrameworkCore;
using PricingHub.Api.Contracts;
using PricingHub.Infrastructure.Persistence;

namespace PricingHub.Api.Endpoints;

public static class CatalogEndpoints
{
    public static void MapCatalogEndpoints(this WebApplication app)
    {
        app.MapGet("/api/models", async (PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            // Matérialise d'abord (ToListAsync), puis projette en mémoire : accéder à
            // .Id.Value / .SeriesCode.Value sur des propriétés converties (HasConversion)
            // à l'intérieur d'un Select traduit en SQL n'est pas garanti côté EF Core.
            var models = await db.Models.ToListAsync(cancellationToken);
            var response = models
                .Select(m => new ModelSummaryResponse(m.Id.Value, m.SeriesCode.Value, m.Name, m.NewValue.Amount))
                .ToList();
            return Results.Ok(response);
        })
        .WithName("ListModels")
        .WithOpenApi();
    }
}
