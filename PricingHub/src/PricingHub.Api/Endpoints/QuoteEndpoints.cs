using PricingHub.Api.Contracts;
using PricingHub.Api.Services;

namespace PricingHub.Api.Endpoints;

public static class QuoteEndpoints
{
    public static void MapQuoteEndpoints(this WebApplication app)
    {
        app.MapPost("/api/quotes/calculate", async (
            CalculateQuoteRequest request, QuoteCalculationService service, CancellationToken cancellationToken) =>
        {
            var result = await service.CalculateAsync(request, cancellationToken);
            return result.IsSuccess
                ? Results.Ok(result.Value)
                : Results.UnprocessableEntity(new { error = result.Error });
        })
        .WithName("CalculateQuote")
        .WithOpenApi();
    }
}
