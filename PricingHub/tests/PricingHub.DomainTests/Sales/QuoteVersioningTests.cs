using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Pricing;
using PricingHub.Domain.Pricing.Calculations;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.DomainTests.Fixtures;
using PricingHub.SharedKernel;

namespace PricingHub.DomainTests.Sales;

/// <summary>
/// Vérifie le mécanisme de versionnement lui-même (M4-04) : aucun
/// équivalent direct côté Python, qui ne conservait pas d'état entre deux
/// appels à <c>calculer_offre</c>. Ce filet de sécurité est donc écrit
/// directement contre le comportement attendu de <see cref="Quote"/>, pas
/// porté depuis une valeur de référence externe.
/// </summary>
public class QuoteVersioningTests
{
    private static Quote CreateCalculatedQuote()
    {
        var quote = Quote.CreateDraft(
            QuoteId.New(), CustomerCode.Of("CLIENTOK"), ModelCode.Of("VECTRON"),
            Mileage.FromKilometers(120_000m), Duration.FromMonths(24), 1, new DateOnly(2026, 1, 1)).Value;

        quote.AssignManualFleetData(5m, Mileage.FromKilometers(600_000m), false, false);
        Calculate(quote);
        return quote;
    }

    private static void Calculate(Quote quote)
    {
        var vrStart = ResidualValueCalculator.Calculate(VectronFixture.Model, VectronFixture.Parameters, quote.AgeAtStartYears, quote.CumulativeMileageAtStart, false, false);
        var ageEnd = quote.AgeAtStartYears + quote.ContractDuration.Years;
        var mileageEnd = Mileage.FromKilometers(quote.CumulativeMileageAtStart.Kilometers + quote.AnnualMileage.Kilometers * quote.ContractDuration.Years);
        var vrEnd = ResidualValueCalculator.Calculate(VectronFixture.Model, VectronFixture.Parameters, ageEnd, mileageEnd, false, false);
        var vrAverage = Money.Eur((vrStart.Amount + vrEnd.Amount) / 2m);
        var additionalMileagePrice = AdditionalMileageCalculator.CalculatePerKilometerPrice(VectronFixture.Model, VectronFixture.BracketA, VectronFixture.Parameters.AdditionalMileageSurcharge);

        var pricedLines = new Dictionary<PriceLine, PricedLine>
        {
            [PriceLine.DryLease] = DryLeaseCalculator.Calculate(VectronFixture.DryLeaseGrid, VectronFixture.BracketA, VectronFixture.Parameters.MaximumDiscount),
            [PriceLine.HeavyMaintenance] = HeavyMaintenanceCalculator.Calculate(VectronFixture.Model, quote.AnnualMileage, VectronFixture.BracketA, VectronFixture.BudgetPlanA, VectronFixture.Parameters.HeavyMaintenanceMargin),
            [PriceLine.OperatingMaintenance] = OperatingMaintenanceCalculator.Calculate(VectronFixture.Model, quote.AnnualMileage, VectronFixture.BracketA, VectronFixture.BudgetPlanA, VectronFixture.Parameters.OperatingMaintenanceMargin),
            [PriceLine.Insurance] = InsuranceCalculator.Calculate(VectronFixture.Model, vrAverage, VectronFixture.Parameters.InsuranceMargin),
        };

        var result = quote.ApplyCalculation(PriceBookNumber.Of(1), VectronFixture.Parameters, vrStart, vrEnd, additionalMileagePrice, pricedLines, preSendControlsFailed: false);
        Assert.True(result.IsSuccess);
    }

    [Fact]
    public void UneNouvelleOffre_DemarreEnVersion1Brouillon()
    {
        var quote = Quote.CreateDraft(
            QuoteId.New(), CustomerCode.Of("CLIENTOK"), ModelCode.Of("VECTRON"),
            Mileage.FromKilometers(120_000m), Duration.FromMonths(24), 1, new DateOnly(2026, 1, 1)).Value;

        Assert.Equal(1, quote.CurrentVersionNumber.Value);
        Assert.Single(quote.Versions);
        Assert.Equal(QuoteStatus.Draft, quote.Status);
    }

    [Fact]
    public void NegocierUnPrixApresCalcul_OuvreUneNouvelleVersion()
    {
        var quote = CreateCalculatedQuote();
        Assert.Equal(1, quote.CurrentVersionNumber.Value);
        Assert.Equal(QuoteStatus.Calculated, quote.Status);
        var ancienMontantRetenu = quote.TotalRetainedPerUnitMonthly!.Value;

        quote.NegotiatePrice(PriceLine.DryLease, Money.Eur(18_500m));

        Assert.Equal(2, quote.CurrentVersionNumber.Value);
        Assert.Equal(2, quote.Versions.Count);
        Assert.Equal(QuoteStatus.Draft, quote.Status);

        // La version 1 reste intacte : elle garde son résultat calculé.
        var versionUn = quote.Versions[0];
        Assert.Equal(QuoteStatus.Calculated, versionUn.Status);
        Assert.Equal(ancienMontantRetenu.Amount, versionUn.TotalRetainedPerUnitMonthly!.Value.Amount, 6);
        Assert.Empty(versionUn.NegotiatedPrices);

        // La version 2 reprend l'affectation de flotte de la version 1 (copie-avant).
        Assert.True(quote.HasFleetAssignment);
        Assert.Equal(5m, quote.AgeAtStartYears);
    }

    [Fact]
    public void RecalculerUneVersionSoumise_EstRefuse()
    {
        var quote = CreateCalculatedQuote();
        Assert.True(quote.SubmitForApproval().IsSuccess);

        var vrStart = ResidualValueCalculator.Calculate(VectronFixture.Model, VectronFixture.Parameters, 5m, Mileage.FromKilometers(600_000m), false, false);
        var result = quote.ApplyCalculation(
            PriceBookNumber.Of(1), VectronFixture.Parameters, vrStart, vrStart,
            0m, new Dictionary<PriceLine, PricedLine>
            {
                [PriceLine.DryLease] = DryLeaseCalculator.Calculate(VectronFixture.DryLeaseGrid, VectronFixture.BracketA, VectronFixture.Parameters.MaximumDiscount),
                [PriceLine.HeavyMaintenance] = HeavyMaintenanceCalculator.Calculate(VectronFixture.Model, quote.AnnualMileage, VectronFixture.BracketA, VectronFixture.BudgetPlanA, VectronFixture.Parameters.HeavyMaintenanceMargin),
                [PriceLine.OperatingMaintenance] = OperatingMaintenanceCalculator.Calculate(VectronFixture.Model, quote.AnnualMileage, VectronFixture.BracketA, VectronFixture.BudgetPlanA, VectronFixture.Parameters.OperatingMaintenanceMargin),
                [PriceLine.Insurance] = InsuranceCalculator.Calculate(VectronFixture.Model, vrStart, VectronFixture.Parameters.InsuranceMargin),
            }, preSendControlsFailed: false);

        Assert.True(result.IsFailure);
        Assert.Equal(1, quote.CurrentVersionNumber.Value);
        Assert.Equal(QuoteStatus.Submitted, quote.Status);
    }

    [Fact]
    public void ApprouverPuisEditer_OuvreUneNouvelleVersionEtLAncienneApprobationResteLiéeALAncienneVersion()
    {
        var quote = CreateCalculatedQuote();
        Assert.True(quote.SubmitForApproval().IsSuccess);
        Assert.True(quote.Approve("manager@akiem.com").IsSuccess);
        var versionApprouvee = quote.CurrentVersionNumber;

        quote.AssignManualFleetData(6m, Mileage.FromKilometers(650_000m), false, false);

        Assert.NotEqual(versionApprouvee, quote.CurrentVersionNumber);
        Assert.Equal(QuoteStatus.Draft, quote.Status);
        Assert.Equal(QuoteStatus.Approved, quote.Versions.First(v => v.Id == versionApprouvee).Status);
    }
}
