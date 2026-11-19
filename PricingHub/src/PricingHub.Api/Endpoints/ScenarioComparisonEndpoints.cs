using Microsoft.EntityFrameworkCore;
using PricingHub.Api.Contracts;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.Domain.Sales.ScenarioComparisonAggregate;
using PricingHub.Infrastructure.Persistence;

namespace PricingHub.Api.Endpoints;

/// <summary>Le comparateur de 3 scénarios (M3-04).</summary>
public static class ScenarioComparisonEndpoints
{
    public static void MapScenarioComparisonEndpoints(this WebApplication app)
    {
        app.MapPost("/api/scenario-comparisons", async (
            CreateScenarioComparisonRequest request, PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            var result = ScenarioComparison.Create(
                ScenarioComparisonId.New(), CustomerCode.Of(request.CustomerCode), request.Name, request.CreatedBy);
            if (result.IsFailure)
            {
                return Results.UnprocessableEntity(new { error = result.Error });
            }

            db.ScenarioComparisons.Add(result.Value);
            await db.SaveChangesAsync(cancellationToken);
            return Results.Created($"/api/scenario-comparisons/{result.Value.Id.Value}", ToResponse(result.Value));
        })
        .WithName("CreateScenarioComparison")
        .WithOpenApi();

        app.MapGet("/api/scenario-comparisons/{id:guid}", async (
            Guid id, PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            var comparisonId = ScenarioComparisonId.Of(id);
            var comparison = await db.ScenarioComparisons
                .Include(c => c.Scenarios)
                .SingleOrDefaultAsync(c => c.Id == comparisonId, cancellationToken);
            return comparison is null ? Results.NotFound() : Results.Ok(ToResponse(comparison));
        })
        .WithName("GetScenarioComparison")
        .WithOpenApi();

        app.MapPost("/api/scenario-comparisons/{id:guid}/scenarios", async (
            Guid id, AddScenarioRequest request, PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            var comparisonId = ScenarioComparisonId.Of(id);
            var comparison = await db.ScenarioComparisons
                .Include(c => c.Scenarios)
                .SingleOrDefaultAsync(c => c.Id == comparisonId, cancellationToken);
            if (comparison is null)
            {
                return Results.NotFound();
            }

            var result = comparison.AddScenario(
                request.Label, QuoteId.Of(request.QuoteId), QuoteVersionNumber.Of(request.QuoteVersion));
            if (result.IsFailure)
            {
                return Results.UnprocessableEntity(new { error = result.Error });
            }

            await db.SaveChangesAsync(cancellationToken);
            return Results.Ok(ToResponse(comparison));
        })
        .WithName("AddScenario")
        .WithOpenApi();

        app.MapDelete("/api/scenario-comparisons/{id:guid}/scenarios/{label}", async (
            Guid id, string label, PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            var comparisonId = ScenarioComparisonId.Of(id);
            var comparison = await db.ScenarioComparisons
                .Include(c => c.Scenarios)
                .SingleOrDefaultAsync(c => c.Id == comparisonId, cancellationToken);
            if (comparison is null)
            {
                return Results.NotFound();
            }

            var result = comparison.RemoveScenario(label);
            if (result.IsFailure)
            {
                return Results.UnprocessableEntity(new { error = result.Error });
            }

            await db.SaveChangesAsync(cancellationToken);
            return Results.Ok(ToResponse(comparison));
        })
        .WithName("RemoveScenario")
        .WithOpenApi();
    }

    private static ScenarioComparisonResponse ToResponse(ScenarioComparison comparison) => new(
        comparison.Id.Value, comparison.CustomerCode.Value, comparison.Name, comparison.CreatedBy, comparison.CreatedAt,
        comparison.Scenarios.Select(s => new ScenarioEntryResponse(s.Label, s.QuoteId.Value, s.QuoteVersion.Value)).ToList());
}
