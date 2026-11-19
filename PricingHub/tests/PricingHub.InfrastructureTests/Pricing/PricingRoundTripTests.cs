using Microsoft.EntityFrameworkCore;
using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Pricing.CampaignAggregate;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.InfrastructureTests.Pricing;

/// <summary>
/// Vérifie le contournement retenu pour les value objects imbriqués dans
/// d'autres value objects (Money dans DryLeaseGridEntry/BudgetPlanEntry/
/// PricingParameters, MileageBracket dans BudgetPlanEntry, DurationBracket
/// dans DryLeaseGridEntry) : EF Core 8 ne sait pas lier ces imbrications au
/// constructeur (confirmé par <c>dotnet ef migrations add</c>, pas
/// seulement par la compilation), donc elles sont mappées en colonne
/// texte packée plutôt qu'en <c>ComplexProperty</c>/<c>OwnsOne</c> imbriqué.
/// Ce test prouve que l'aller-retour reconstruit des valeurs identiques.
/// </summary>
public class PricingRoundTripTests
{
    [Fact]
    public async Task UnPriceBookComplet_SurvitAUnAllerRetourEnBase()
    {
        var modelCode = ModelCode.Of($"TEST_MODEL_{Guid.NewGuid():N}");
        var number = PriceBookNumber.Of(Random.Shared.Next(100_000, 999_999));

        await using (var write = DatabaseFixture.CreateContext())
        {
            var priceBook = PriceBook.CreateDraft(number, PricingParameters.Defaults(Currency.Eur));

            var bracketA = MileageBracket.Create(80_000m, 149_999m, 1.0m, 1.0m, 1.0m).Value;
            priceBook.AddMileageBracket(bracketA);

            var durationBracket = DurationBracket.Create(0, null).Value;
            priceBook.AddDryLeaseGridEntry(
                DryLeaseGridEntry.Create(modelCode, durationBracket, Money.Eur(20_000m)).Value);

            priceBook.AddBudgetPlanEntry(
                BudgetPlanEntry.Create(modelCode, bracketA, Money.Eur(2_000m), Money.Eur(1_500m), "2026").Value);

            write.PriceBooks.Add(priceBook);
            await write.SaveChangesAsync();
        }

        await using var read = DatabaseFixture.CreateContext();
        var reloaded = await read.PriceBooks
            .Include(p => p.MileageBrackets)
            .Include(p => p.DryLeaseGrid)
            .Include(p => p.BudgetPlan)
            .SingleAsync(p => p.Id == number);

        Assert.Equal(PriceBookStatus.Draft, reloaded.Status);

        // PricingParameters (ComplexProperty direct) — valeurs par défaut du cahier des charges.
        Assert.Equal(0.15m, reloaded.Parameters.HeavyMaintenanceMargin.Value);
        Assert.Equal(10_500.0m, reloaded.Parameters.MinimumDryLease.Amount);
        Assert.Equal(Currency.Eur, reloaded.Parameters.MinimumDryLease.Currency);

        // Tranche de km — OwnsMany direct, scalaire.
        var bracket = Assert.Single(reloaded.MileageBrackets);
        Assert.Equal(80_000m, bracket.MinKilometers);
        Assert.Equal(149_999m, bracket.MaxKilometers);

        // Grille Dry lease — ModelCode scalaire, DurationBracket et Money en colonne packée.
        var grid = Assert.Single(reloaded.DryLeaseGrid);
        Assert.Equal(modelCode, grid.ModelCode);
        Assert.Equal(0, grid.DurationBracket.MinMonths);
        Assert.Null(grid.DurationBracket.MaxMonths);
        Assert.Equal(20_000m, grid.MonthlyRent.Amount);
        Assert.Equal(Currency.Eur, grid.MonthlyRent.Currency);

        // Budget Plan — MileageBracket et deux Money en colonne packée.
        var bp = Assert.Single(reloaded.BudgetPlan);
        Assert.Equal(modelCode, bp.ModelCode);
        Assert.Equal("2026", bp.FiscalYear);
        Assert.Equal(80_000m, bp.MileageBracket.MinKilometers);
        Assert.Equal(149_999m, bp.MileageBracket.MaxKilometers);
        Assert.Equal(2_000m, bp.HeavyMaintenanceFloor.Amount);
        Assert.Equal(1_500m, bp.OperatingMaintenanceFloor.Amount);

        // Suppression dans le même contexte que la lecture : les propriétés fantômes
        // (id des collections possédées) ne survivent pas à un ré-attachement
        // (`Remove`) sur un contexte différent de celui qui a chargé l'entité.
        read.PriceBooks.Remove(reloaded);
        await read.SaveChangesAsync();
    }

    [Fact]
    public async Task UneCampagne_SurvitAUnAllerRetourEnBase()
    {
        var code = CampaignCode.Of($"TEST_CAMPAIGN_{Guid.NewGuid():N}");

        await using (var write = DatabaseFixture.CreateContext())
        {
            var campaign = Campaign.Create(
                code, "AMS (test)", new DateOnly(2026, 1, 1), new DateOnly(2026, 3, 31), maxDurationMonths: 3).Value;
            write.Campaigns.Add(campaign);
            await write.SaveChangesAsync();
        }

        await using var read = DatabaseFixture.CreateContext();
        var reloaded = await read.Campaigns.SingleAsync(c => c.Id == code);

        Assert.Equal("AMS (test)", reloaded.Name);
        Assert.Equal(3, reloaded.MaxDurationMonths);
        Assert.True(reloaded.Covers(new DateOnly(2026, 2, 1)));
        Assert.False(reloaded.Covers(new DateOnly(2026, 4, 1)));

        await using var cleanup = DatabaseFixture.CreateContext();
        cleanup.Campaigns.Remove(reloaded);
        await cleanup.SaveChangesAsync();
    }
}
