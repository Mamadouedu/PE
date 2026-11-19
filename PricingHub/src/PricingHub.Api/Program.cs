using System.Text.Json.Serialization;
using Microsoft.EntityFrameworkCore;
using PricingHub.Api.Contracts;
using PricingHub.Api.Services;
using PricingHub.Infrastructure.Persistence;

var builder = WebApplication.CreateBuilder(args);

// Même variable d'environnement que le prototype Python (DATABASE_URL),
// mais au format Npgsql plutôt que SQLAlchemy — voir PricingHubDbContextFactory
// pour la même convention côté outils (dotnet ef).
var connectionString = Environment.GetEnvironmentVariable("PRICINGHUB_DATABASE_URL")
    ?? builder.Configuration.GetConnectionString("PricingHub")
    ?? "Host=localhost;Database=pricinghub_dev;Username=pricing;Password=pricing";

builder.Services.AddDbContext<PricingHubDbContext>(options => options.UseNpgsql(connectionString));
builder.Services.AddScoped<QuoteCalculationService>();

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

builder.Services.ConfigureHttpJsonOptions(options =>
{
    options.SerializerOptions.Converters.Add(new JsonStringEnumConverter());
});

// Origines du frontend KAM autorisées — même convention que l'API Python
// (CORS_ORIGINS, séparées par des virgules ; Vite par défaut en dev).
var corsOrigins = (Environment.GetEnvironmentVariable("CORS_ORIGINS") ?? "http://localhost:5173,http://127.0.0.1:5173")
    .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy => policy
        .WithOrigins(corsOrigins)
        .AllowAnyMethod()
        .AllowAnyHeader()
        .AllowCredentials());
});

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseCors();

app.MapGet("/health", async (PricingHubDbContext db, CancellationToken cancellationToken) =>
{
    var canConnect = await db.Database.CanConnectAsync(cancellationToken);
    return canConnect
        ? Results.Ok(new { status = "ok", database = "reachable" })
        : Results.Json(new { status = "degraded", database = "unreachable" }, statusCode: StatusCodes.Status503ServiceUnavailable);
})
.WithName("GetHealth")
.WithOpenApi();

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

app.Run();

public partial class Program;
