using Microsoft.EntityFrameworkCore;
using PricingHub.Api.Contracts;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.Domain.Workflow.ApprovalRequestAggregate;
using PricingHub.Infrastructure.Persistence;

namespace PricingHub.Api.Endpoints;

/// <summary>
/// Le circuit de dérogation (M4, section 7) — équivalent des endpoints
/// <c>demander_derogation</c>/<c>decider_derogation</c> côté Python.
/// Toujours sur la version COURANTE de l'offre : si le KAM la modifie
/// après coup, <c>Quote.ApplyCalculation</c> ouvre une nouvelle version
/// (M4-04) et toute dérogation déjà accordée reste liée à l'ancienne.
/// </summary>
public static class ApprovalRequestEndpoints
{
    public static void MapApprovalRequestEndpoints(this WebApplication app)
    {
        app.MapPost("/api/approval-requests", async (
            RequestApprovalRequest request, PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            var quoteId = QuoteId.Of(request.QuoteId);
            var quote = await db.Quotes.Include(q => q.Versions).SingleOrDefaultAsync(q => q.Id == quoteId, cancellationToken);
            if (quote is null)
            {
                return Results.NotFound(new { error = $"Offre {request.QuoteId} introuvable." });
            }

            if (quote.PriceBookNumber is null)
            {
                return Results.UnprocessableEntity(new { error = "L'offre n'a pas encore été calculée." });
            }

            var delegations = await db.Delegations.ToListAsync(cancellationToken);

            // Numérotation séquentielle du registre (M4-05) — la table reste petite
            // (les dérogations sont rares), donc un max + 1 en mémoire est sûr ici.
            var existingRequests = await db.ApprovalRequests.ToListAsync(cancellationToken);
            var nextNumber = existingRequests.Count == 0 ? 1 : existingRequests.Max(a => a.Id.Value) + 1;

            var result = ApprovalRequest.Request(
                ApprovalRequestId.Of(nextNumber), quote.Id, quote.CurrentVersionNumber, quote.PriceBookNumber.Value,
                quote.CustomerCode, quote.ModelCode, quote.ValidationLevel, quote.TotalRetainedMonthly!.Value,
                delegations, request.RequestedBy, request.Justification);
            if (result.IsFailure)
            {
                return Results.UnprocessableEntity(new { error = result.Error });
            }

            db.ApprovalRequests.Add(result.Value);
            await db.SaveChangesAsync(cancellationToken);
            return Results.Created($"/api/approval-requests/{nextNumber}", ToResponse(result.Value));
        })
        .WithName("RequestApproval")
        .WithOpenApi();

        app.MapGet("/api/approval-requests/{number:int}", async (
            int number, PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            var id = ApprovalRequestId.Of(number);
            var request = await db.ApprovalRequests.SingleOrDefaultAsync(a => a.Id == id, cancellationToken);
            return request is null ? Results.NotFound() : Results.Ok(ToResponse(request));
        })
        .WithName("GetApprovalRequest")
        .WithOpenApi();

        app.MapGet("/api/approval-requests", async (PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            var requests = await db.ApprovalRequests.ToListAsync(cancellationToken);
            return Results.Ok(requests.OrderByDescending(a => a.Id.Value).Select(ToResponse).ToList());
        })
        .WithName("ListApprovalRequests")
        .WithOpenApi();

        app.MapPost("/api/approval-requests/{number:int}/decide", async (
            int number, DecideApprovalRequest request, PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            var id = ApprovalRequestId.Of(number);
            var approvalRequest = await db.ApprovalRequests.SingleOrDefaultAsync(a => a.Id == id, cancellationToken);
            if (approvalRequest is null)
            {
                return Results.NotFound();
            }

            var result = approvalRequest.Decide(request.Decision, request.DecidedBy, request.Comment);
            if (result.IsFailure)
            {
                return Results.UnprocessableEntity(new { error = result.Error });
            }

            await db.SaveChangesAsync(cancellationToken);
            return Results.Ok(ToResponse(approvalRequest));
        })
        .WithName("DecideApprovalRequest")
        .WithOpenApi();
    }

    private static ApprovalRequestResponse ToResponse(ApprovalRequest request) => new(
        request.Id.Value, request.Status, request.ValidationLevel, request.RequestedBy, request.Justification,
        request.QuoteId.Value, request.QuoteVersion.Value, request.PriceBookNumber.Value, request.CustomerCode.Value,
        request.ModelCode.Value, request.MonthlyRetainedAmount.Amount, request.ValidatorEmail, request.RequestedAt,
        request.DecidedAt, request.DecidedBy, request.DecisionComment);
}
