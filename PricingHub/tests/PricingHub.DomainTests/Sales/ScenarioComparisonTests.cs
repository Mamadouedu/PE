using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.Domain.Sales.ScenarioComparisonAggregate;

namespace PricingHub.DomainTests.Sales;

/// <summary>Porté conceptuellement depuis le comparateur frontend du
/// prototype Python (M3-04) — trois scénarios maximum.</summary>
public class ScenarioComparisonTests
{
    private static ScenarioComparison CreateComparison() =>
        ScenarioComparison.Create(
            ScenarioComparisonId.New(), CustomerCode.Of("CLIENTOK"), "Négociation Vectron", "kam@akiem.com").Value;

    [Fact]
    public void AccepteJusquaTroisScenarios()
    {
        var comparison = CreateComparison();

        Assert.True(comparison.AddScenario("Agressif", QuoteId.New(), QuoteVersionNumber.First).IsSuccess);
        Assert.True(comparison.AddScenario("Standard", QuoteId.New(), QuoteVersionNumber.First).IsSuccess);
        Assert.True(comparison.AddScenario("Prudent", QuoteId.New(), QuoteVersionNumber.First).IsSuccess);
        Assert.Equal(3, comparison.Scenarios.Count);
    }

    [Fact]
    public void RefuseUnQuatriemeScenario()
    {
        var comparison = CreateComparison();
        comparison.AddScenario("Agressif", QuoteId.New(), QuoteVersionNumber.First);
        comparison.AddScenario("Standard", QuoteId.New(), QuoteVersionNumber.First);
        comparison.AddScenario("Prudent", QuoteId.New(), QuoteVersionNumber.First);

        var result = comparison.AddScenario("Bonus", QuoteId.New(), QuoteVersionNumber.First);

        Assert.True(result.IsFailure);
        Assert.Equal(3, comparison.Scenarios.Count);
    }

    [Fact]
    public void RefuseUnLibelleDejaUtilise()
    {
        var comparison = CreateComparison();
        comparison.AddScenario("Standard", QuoteId.New(), QuoteVersionNumber.First);

        var result = comparison.AddScenario("standard", QuoteId.New(), QuoteVersionNumber.First);

        Assert.True(result.IsFailure);
    }

    [Fact]
    public void SupprimeUnScenarioParLibelle()
    {
        var comparison = CreateComparison();
        comparison.AddScenario("Standard", QuoteId.New(), QuoteVersionNumber.First);

        var result = comparison.RemoveScenario("Standard");

        Assert.True(result.IsSuccess);
        Assert.Empty(comparison.Scenarios);
    }
}
