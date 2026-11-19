using Microsoft.EntityFrameworkCore;
using PricingHub.Api.Contracts;
using PricingHub.Domain.Workflow.DelegationAggregate;
using PricingHub.Infrastructure.Persistence;

namespace PricingHub.Api.Endpoints;

/// <summary>La table Délégation (section 8.3) : un validateur par niveau
/// de validation (1 à 3).</summary>
public static class DelegationEndpoints
{
    public static void MapDelegationEndpoints(this WebApplication app)
    {
        app.MapGet("/api/delegations", async (PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            var delegations = await db.Delegations.ToListAsync(cancellationToken);
            return Results.Ok(delegations.OrderBy(d => d.Id.Value).Select(ToResponse).ToList());
        })
        .WithName("ListDelegations")
        .WithOpenApi();

        app.MapPost("/api/delegations", async (
            CreateDelegationRequest request, PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            var level = ValidationLevel.Of(request.Level);
            var existing = await db.Delegations.SingleOrDefaultAsync(d => d.Id == level, cancellationToken);
            if (existing is not null)
            {
                existing.Reassign(request.Name, request.Email, request.AlternateEmail);
                await db.SaveChangesAsync(cancellationToken);
                return Results.Ok(ToResponse(existing));
            }

            var result = Delegation.Create(level, request.Name, request.Email, request.AlternateEmail);
            if (result.IsFailure)
            {
                return Results.UnprocessableEntity(new { error = result.Error });
            }

            db.Delegations.Add(result.Value);
            await db.SaveChangesAsync(cancellationToken);
            return Results.Created($"/api/delegations/{request.Level}", ToResponse(result.Value));
        })
        .WithName("UpsertDelegation")
        .WithOpenApi();
    }

    private static DelegationResponse ToResponse(Delegation delegation) =>
        new(delegation.Id.Value, delegation.Name, delegation.Email, delegation.AlternateEmail);
}
