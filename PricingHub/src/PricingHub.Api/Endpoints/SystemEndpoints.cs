using Microsoft.EntityFrameworkCore;
using PricingHub.Infrastructure.Persistence;

namespace PricingHub.Api.Endpoints;

public static class SystemEndpoints
{
    public static void MapSystemEndpoints(this WebApplication app)
    {
        app.MapGet("/health", async (PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            var canConnect = await db.Database.CanConnectAsync(cancellationToken);
            return canConnect
                ? Results.Ok(new { status = "ok", database = "reachable" })
                : Results.Json(new { status = "degraded", database = "unreachable" }, statusCode: StatusCodes.Status503ServiceUnavailable);
        })
        .WithName("GetHealth")
        .WithOpenApi();
    }
}
