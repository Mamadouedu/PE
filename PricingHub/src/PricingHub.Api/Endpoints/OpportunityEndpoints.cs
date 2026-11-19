using Microsoft.EntityFrameworkCore;
using PricingHub.Api.Contracts;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.OpportunityAggregate;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.Infrastructure.Persistence;
using PricingHub.SharedKernel;

namespace PricingHub.Api.Endpoints;

public static class OpportunityEndpoints
{
    public static void MapOpportunityEndpoints(this WebApplication app)
    {
        app.MapPost("/api/opportunities", async (
            OpenOpportunityRequest request, PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            var result = Opportunity.Open(OpportunityId.New(), CustomerCode.Of(request.CustomerCode), request.Title);
            if (result.IsFailure)
            {
                return Results.UnprocessableEntity(new { error = result.Error });
            }

            db.Opportunities.Add(result.Value);
            await db.SaveChangesAsync(cancellationToken);
            return Results.Created($"/api/opportunities/{result.Value.Id.Value}", ToResponse(result.Value));
        })
        .WithName("OpenOpportunity")
        .WithOpenApi();

        app.MapGet("/api/opportunities/{id:guid}", async (Guid id, PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            var opportunityId = OpportunityId.Of(id);
            var opportunity = await db.Opportunities.SingleOrDefaultAsync(o => o.Id == opportunityId, cancellationToken);
            return opportunity is null ? Results.NotFound() : Results.Ok(ToResponse(opportunity));
        })
        .WithName("GetOpportunity")
        .WithOpenApi();

        app.MapPost("/api/opportunities/{id:guid}/link-quote", async (
            Guid id, LinkQuoteRequest request, PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            var opportunityId = OpportunityId.Of(id);
            var opportunity = await db.Opportunities.SingleOrDefaultAsync(o => o.Id == opportunityId, cancellationToken);
            if (opportunity is null)
            {
                return Results.NotFound();
            }

            opportunity.LinkQuote(QuoteId.Of(request.QuoteId));
            await db.SaveChangesAsync(cancellationToken);
            return Results.Ok(ToResponse(opportunity));
        })
        .WithName("LinkQuoteToOpportunity")
        .WithOpenApi();

        app.MapPost("/api/opportunities/{id:guid}/mark-won", async (
            Guid id, PricingHubDbContext db, CancellationToken cancellationToken) => await Decide(id, db, cancellationToken, o => o.MarkWon()))
        .WithName("MarkOpportunityWon")
        .WithOpenApi();

        app.MapPost("/api/opportunities/{id:guid}/mark-lost", async (
            Guid id, PricingHubDbContext db, CancellationToken cancellationToken) => await Decide(id, db, cancellationToken, o => o.MarkLost()))
        .WithName("MarkOpportunityLost")
        .WithOpenApi();
    }

    private static async Task<IResult> Decide(
        Guid id, PricingHubDbContext db, CancellationToken cancellationToken, Func<Opportunity, Result> decide)
    {
        var opportunityId = OpportunityId.Of(id);
        var opportunity = await db.Opportunities.SingleOrDefaultAsync(o => o.Id == opportunityId, cancellationToken);
        if (opportunity is null)
        {
            return Results.NotFound();
        }

        var result = decide(opportunity);
        if (result.IsFailure)
        {
            return Results.UnprocessableEntity(new { error = result.Error });
        }

        await db.SaveChangesAsync(cancellationToken);
        return Results.Ok(ToResponse(opportunity));
    }

    private static OpportunityResponse ToResponse(Opportunity opportunity) => new(
        opportunity.Id.Value, opportunity.CustomerCode.Value, opportunity.Title, opportunity.Status,
        opportunity.PipedriveDeal?.DealId, opportunity.QuoteIds.Select(q => q.Value).ToList());
}
