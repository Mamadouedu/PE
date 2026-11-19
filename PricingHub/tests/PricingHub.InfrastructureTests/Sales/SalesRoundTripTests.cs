using Microsoft.EntityFrameworkCore;
using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Pricing;
using PricingHub.Domain.Pricing.Calculations;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.OpportunityAggregate;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.Domain.Sales.ScenarioComparisonAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.InfrastructureTests.Sales;

/// <summary>
/// Le test le plus exigeant du dépôt : vérifie que l'agrégat le plus
/// profond (Quote → QuoteVersion → QuoteLine, packé en JSON — voir
/// <c>ValueConverters.ForQuoteLines</c>) survit à un aller-retour réel,
/// y compris le versionnement automatique (une négociation après calcul
/// ouvre une seconde version, M4-04).
/// </summary>
public class SalesRoundTripTests
{
    [Fact]
    public async Task UnCustomer_SurvitAUnAllerRetourEnBase()
    {
        var code = CustomerCode.Of($"TEST_CUST_{Guid.NewGuid():N}");

        await using (var write = DatabaseFixture.CreateContext())
        {
            var customer = Customer.Create(code, "Client test", 5, "Fret", Money.Eur(50_000m), true).Value;
            write.Customers.Add(customer);
            await write.SaveChangesAsync();
        }

        await using var read = DatabaseFixture.CreateContext();
        var reloaded = await read.Customers.SingleAsync(c => c.Id == code);

        Assert.Equal("Client test", reloaded.Name);
        Assert.Equal(5, reloaded.CreditRating);
        Assert.Equal(50_000m, reloaded.CashDeposit.Amount);
        Assert.True(reloaded.PaysInAdvance);
        Assert.True(reloaded.HasPaymentGuarantee);

        read.Customers.Remove(reloaded);
        await read.SaveChangesAsync();
    }

    [Fact]
    public async Task UneOpportunite_AvecQuoteIdsEtDealPipedrive_SurvitAUnAllerRetourEnBase()
    {
        var id = OpportunityId.New();
        var customerCode = CustomerCode.Of($"TEST_CUST_{Guid.NewGuid():N}");
        var quoteIdA = QuoteId.New();
        var quoteIdB = QuoteId.New();

        await using (var write = DatabaseFixture.CreateContext())
        {
            var opportunity = Opportunity.Open(id, customerCode, "Renouvellement flotte (test)").Value;
            opportunity.LinkQuote(quoteIdA);
            opportunity.LinkQuote(quoteIdB);
            opportunity.LinkPipedriveDeal(PipedriveDealReference.Of(4242));
            write.Opportunities.Add(opportunity);
            await write.SaveChangesAsync();
        }

        await using var read = DatabaseFixture.CreateContext();
        var reloaded = await read.Opportunities.SingleAsync(o => o.Id == id);

        Assert.Equal("Renouvellement flotte (test)", reloaded.Title);
        Assert.Equal(OpportunityStatus.Open, reloaded.Status);
        Assert.Equal(4242, reloaded.PipedriveDeal!.Value.DealId);
        Assert.Equal(2, reloaded.QuoteIds.Count);
        Assert.Contains(quoteIdA, reloaded.QuoteIds);
        Assert.Contains(quoteIdB, reloaded.QuoteIds);

        read.Opportunities.Remove(reloaded);
        await read.SaveChangesAsync();
    }

    [Fact]
    public async Task UneOffreCalculeePuisRenegociee_SurvitAUnAllerRetourEnBase_AvecDeuxVersions()
    {
        var quoteId = QuoteId.New();
        var modelCode = ModelCode.Of($"TEST_MODEL_{Guid.NewGuid():N}");
        var customerCode = CustomerCode.Of($"TEST_CUST_{Guid.NewGuid():N}");
        var parameters = PricingParameters.Defaults(Currency.Eur);

        await using (var write = DatabaseFixture.CreateContext())
        {
            var quote = Quote.CreateDraft(
                quoteId, customerCode, modelCode, Mileage.FromKilometers(120_000m), Duration.FromMonths(24),
                quantity: 1, startDate: new DateOnly(2026, 1, 1)).Value;

            quote.AssignManualFleetData(5m, Mileage.FromKilometers(600_000m), heavyMaintenance8Done: true, heavyMaintenance16Done: false);

            var vrStart = Money.Eur(1_700_000m);
            var vrEnd = Money.Eur(1_580_000m);
            var pricedLines = new Dictionary<PriceLine, PricedLine>
            {
                [PriceLine.DryLease] = new PricedLine(PriceLine.DryLease, Money.Eur(20_000m), Money.Eur(20_000m), Money.Eur(18_000m)),
                [PriceLine.HeavyMaintenance] = new PricedLine(PriceLine.HeavyMaintenance, Money.Eur(1_822.92m), Money.Eur(2_096.35m), Money.Eur(2_000m)),
                [PriceLine.OperatingMaintenance] = new PricedLine(PriceLine.OperatingMaintenance, Money.Eur(1_000m), Money.Eur(1_500m), Money.Eur(1_500m)),
                [PriceLine.Insurance] = new PricedLine(PriceLine.Insurance, Money.Eur(4_100m), Money.Eur(4_305m), Money.Eur(4_100m)),
            };

            Assert.True(quote.ApplyCalculation(
                PriceBookNumber.Of(1), parameters, vrStart, vrEnd, 0.5m, pricedLines, preSendControlsFailed: false).IsSuccess);
            Assert.True(quote.SubmitForApproval().IsSuccess);
            Assert.True(quote.Approve("manager@akiem.com").IsSuccess);

            // Négocier après approbation ouvre automatiquement une version 2 (M4-04).
            quote.NegotiatePrice(PriceLine.DryLease, Money.Eur(17_000m));

            write.Quotes.Add(quote);
            await write.SaveChangesAsync();
        }

        await using var read = DatabaseFixture.CreateContext();
        var reloaded = await read.Quotes.Include(q => q.Versions).SingleAsync(q => q.Id == quoteId);

        Assert.Equal(customerCode, reloaded.CustomerCode);
        Assert.Equal(modelCode, reloaded.ModelCode);
        Assert.Equal(2, reloaded.Versions.Count);

        var versionOne = reloaded.Versions.Single(v => v.Id.Value == 1);
        Assert.Equal(QuoteStatus.Approved, versionOne.Status);
        Assert.Equal("manager@akiem.com", versionOne.DecidedBy);
        Assert.Equal(4, versionOne.Lines.Count);

        var dryLease = versionOne.Lines.Single(l => l.Line == PriceLine.DryLease);
        Assert.Equal(20_000m, dryLease.CatalogPrice.Amount);
        Assert.Equal(Currency.Eur, dryLease.CatalogPrice.Currency);
        Assert.Equal(18_000m, dryLease.Floor.Amount);
        Assert.Equal(QuoteLineStatus.Ok, dryLease.Status);
        Assert.Null(dryLease.NegotiatedPrice);

        Assert.Equal(1_700_000m, versionOne.ResidualValueAtStart!.Value.Amount);
        Assert.Equal(1_580_000m, versionOne.ResidualValueAtEnd!.Value.Amount);
        Assert.True(versionOne.HeavyMaintenance8Done);
        Assert.False(versionOne.HeavyMaintenance16Done);

        var versionTwo = reloaded.Versions.Single(v => v.Id.Value == 2);
        Assert.Equal(QuoteStatus.Draft, versionTwo.Status);
        Assert.Equal(17_000m, versionTwo.NegotiatedPrices[PriceLine.DryLease].Amount);
        // Version 2 copie l'affectation de flotte de la version 1 (copie-avant).
        Assert.True(versionTwo.HasFleetAssignment);
        Assert.Equal(5m, versionTwo.AgeAtStartYears);
        // Version 2 n'a pas encore été recalculée : pas de lignes.
        Assert.Empty(versionTwo.Lines);

        Assert.Equal(reloaded.CurrentVersionNumber, versionTwo.Id);

        read.Quotes.Remove(reloaded);
        await read.SaveChangesAsync();
    }

    [Fact]
    public async Task UnComparateurDeScenarios_SurvitAUnAllerRetourEnBase()
    {
        var id = ScenarioComparisonId.New();
        var customerCode = CustomerCode.Of($"TEST_CUST_{Guid.NewGuid():N}");
        var quoteId = QuoteId.New();

        await using (var write = DatabaseFixture.CreateContext())
        {
            var comparison = ScenarioComparison.Create(id, customerCode, "Négociation Vectron (test)", "kam@akiem.com").Value;
            Assert.True(comparison.AddScenario("Standard", quoteId, QuoteVersionNumber.First).IsSuccess);
            write.ScenarioComparisons.Add(comparison);
            await write.SaveChangesAsync();
        }

        await using var read = DatabaseFixture.CreateContext();
        var reloaded = await read.ScenarioComparisons.Include(c => c.Scenarios).SingleAsync(c => c.Id == id);

        var scenario = Assert.Single(reloaded.Scenarios);
        Assert.Equal("Standard", scenario.Label);
        Assert.Equal(quoteId, scenario.QuoteId);
        Assert.Equal(1, scenario.QuoteVersion.Value);

        read.ScenarioComparisons.Remove(reloaded);
        await read.SaveChangesAsync();
    }
}
