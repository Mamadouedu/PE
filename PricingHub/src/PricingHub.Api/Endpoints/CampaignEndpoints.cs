using Microsoft.EntityFrameworkCore;
using PricingHub.Api.Contracts;
using PricingHub.Infrastructure.Persistence;

namespace PricingHub.Api.Endpoints;

/// <summary>
/// Liste des campagnes commerciales ouvertes — le frontend KAM s'en sert
/// pour remplacer l'ancien booléen <c>ConfigurationOffre.campagne</c> par
/// un vrai choix de campagne (<see cref="PricingHub.Api.Contracts.CalculateQuoteRequest.CampaignCode"/>).
/// </summary>
public static class CampaignEndpoints
{
    public static void MapCampaignEndpoints(this WebApplication app)
    {
        app.MapGet("/api/campaigns", async (PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            var campaigns = await db.Campaigns.Where(c => c.IsActive).ToListAsync(cancellationToken);
            var response = campaigns
                .Select(c => new CampaignResponse(c.Id.Value, c.Name, c.MaxDurationMonths, c.StartDate, c.EndDate))
                .OrderBy(c => c.Code)
                .ToList();
            return Results.Ok(response);
        })
        .WithName("ListCampaigns")
        .WithOpenApi();
    }
}
