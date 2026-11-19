using System.Text.Json.Serialization;
using Microsoft.EntityFrameworkCore;
using PricingHub.Api.Endpoints;
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

app.MapSystemEndpoints();
app.MapCatalogEndpoints();
app.MapQuoteEndpoints();
app.MapCustomerEndpoints();
app.MapOpportunityEndpoints();
app.MapDelegationEndpoints();
app.MapApprovalRequestEndpoints();
app.MapScenarioComparisonEndpoints();

app.Run();

public partial class Program;
