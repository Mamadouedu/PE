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
/// Offre complète (config_base, <c>tests/conftest.py</c>) chiffrée de bout
/// en bout — équivalent de <c>engine.calculer_offre</c> appelé depuis
/// <c>tests/test_engine_*.py</c>, mais orchestré ici manuellement : les
/// calculateurs (Pricing) restent des services sans état, c'est
/// <see cref="Quote.ApplyCalculation"/> qui les combine. Sert de filet de
/// sécurité sur les totaux et le niveau de validation, pas seulement sur
/// chaque brique isolément.
/// </summary>
public class QuoteCalculationTests
{
    [Fact]
    public void OffreDeBaseEstDansLesRegles_NiveauValidationZero()
    {
        var quote = Quote.CreateDraft(
            QuoteId.New(),
            CustomerCode.Of("CLIENTOK"),
            ModelCode.Of("VECTRON"),
            Mileage.FromKilometers(120_000m),
            Duration.FromMonths(24),
            quantity: 1,
            startDate: new DateOnly(2026, 1, 1),
            isCampaign: false).Value;

        quote.AssignManualFleetData(
            ageAtStartYears: 5m,
            cumulativeMileageAtStart: Mileage.FromKilometers(600_000m),
            heavyMaintenance8Done: false,
            heavyMaintenance16Done: false);

        var durationYears = quote.ContractDuration.Years;
        var ageEnd = quote.AgeAtStartYears + durationYears;
        var mileageEnd = Mileage.FromKilometers(quote.CumulativeMileageAtStart.Kilometers + quote.AnnualMileage.Kilometers * durationYears);

        var vrStart = ResidualValueCalculator.Calculate(
            VectronFixture.Model, VectronFixture.Parameters, quote.AgeAtStartYears, quote.CumulativeMileageAtStart, false, false);
        var vrEnd = ResidualValueCalculator.Calculate(
            VectronFixture.Model, VectronFixture.Parameters, ageEnd, mileageEnd, false, false);
        var vrAverage = Money.Eur((vrStart.Amount + vrEnd.Amount) / 2m);

        Assert.Equal(1_700_000.0m, vrStart.Amount, 2);
        Assert.Equal(1_580_000.0m, vrEnd.Amount, 2);

        var additionalMileagePrice = AdditionalMileageCalculator.CalculatePerKilometerPrice(
            VectronFixture.Model, VectronFixture.BracketA, VectronFixture.Parameters.AdditionalMileageSurcharge);

        var pricedLines = new Dictionary<PriceLine, PricedLine>
        {
            [PriceLine.DryLease] = DryLeaseCalculator.Calculate(
                VectronFixture.DryLeaseGrid, VectronFixture.BracketA, VectronFixture.Parameters.MaximumDiscount),
            [PriceLine.HeavyMaintenance] = HeavyMaintenanceCalculator.Calculate(
                VectronFixture.Model, quote.AnnualMileage, VectronFixture.BracketA, VectronFixture.BudgetPlanA,
                VectronFixture.Parameters.HeavyMaintenanceMargin),
            [PriceLine.OperatingMaintenance] = OperatingMaintenanceCalculator.Calculate(
                VectronFixture.Model, quote.AnnualMileage, VectronFixture.BracketA, VectronFixture.BudgetPlanA,
                VectronFixture.Parameters.OperatingMaintenanceMargin),
            [PriceLine.Insurance] = InsuranceCalculator.Calculate(
                VectronFixture.Model, vrAverage, VectronFixture.Parameters.InsuranceMargin),
        };

        var result = quote.ApplyCalculation(
            PriceBookNumber.Of(1), VectronFixture.Parameters, vrStart, vrEnd, additionalMileagePrice, pricedLines,
            preSendControlsFailed: false);

        Assert.True(result.IsSuccess);
        Assert.Equal(QuoteStatus.Calculated, quote.Status);

        var costHm = pricedLines[PriceLine.HeavyMaintenance].Cost.Amount;
        var costOm = pricedLines[PriceLine.OperatingMaintenance].Cost.Amount;
        var costAssurance = pricedLines[PriceLine.Insurance].Cost.Amount;
        var catalogDl = pricedLines[PriceLine.DryLease].CatalogPrice.Amount;
        var catalogHm = pricedLines[PriceLine.HeavyMaintenance].CatalogPrice.Amount;
        var catalogOm = pricedLines[PriceLine.OperatingMaintenance].CatalogPrice.Amount;
        var catalogAssurance = pricedLines[PriceLine.Insurance].CatalogPrice.Amount;

        var expectedMonthlyValueLoss = (vrStart.Amount - vrEnd.Amount) / 24m;
        var expectedMonthlyReferenceCost = expectedMonthlyValueLoss + costHm + costOm + costAssurance;
        var expectedTotalCatalog = catalogDl + catalogHm + catalogOm + catalogAssurance;

        Assert.Equal(5_000.0m, expectedMonthlyValueLoss, 6);
        Assert.Equal(expectedMonthlyValueLoss, quote.MonthlyValueLoss!.Value.Amount, 6);
        Assert.Equal(expectedMonthlyReferenceCost, quote.MonthlyReferenceCost!.Value.Amount, 6);

        // Sans négociation : prix retenu == prix catalogue sur toutes les briques.
        Assert.Equal(expectedTotalCatalog, quote.TotalRetainedPerUnitMonthly!.Value.Amount, 6);
        Assert.Equal(expectedTotalCatalog, quote.TotalCatalogPerUnitMonthly!.Value.Amount, 6);
        Assert.Equal(0.0m, quote.GlobalDiscount!.Value, 6);
        Assert.Equal(expectedTotalCatalog * 24m, quote.TotalRetainedContract!.Value.Amount, 4);

        Assert.Equal(0, quote.ValidationLevel);
        Assert.Contains("Dans les règles", quote.ValidationLevelReasons[0]);
    }

    [Fact]
    public void RemiseAuDelaDuSeuilKam_DeclencheLeNiveau1()
    {
        var quote = Quote.CreateDraft(
            QuoteId.New(), CustomerCode.Of("CLIENTOK"), ModelCode.Of("VECTRON"),
            Mileage.FromKilometers(120_000m), Duration.FromMonths(24), 1, new DateOnly(2026, 1, 1), false).Value;

        quote.AssignManualFleetData(5m, Mileage.FromKilometers(600_000m), false, false);

        // Une petite remise sur le Dry lease suffit à dépasser le seuil KAM (5 %)
        // sans passer sous aucun plancher ni sous le coût de référence.
        quote.NegotiatePrice(PriceLine.DryLease, Money.Eur(18_500m));

        var vrStart = ResidualValueCalculator.Calculate(VectronFixture.Model, VectronFixture.Parameters, 5m, Mileage.FromKilometers(600_000m), false, false);
        var vrEnd = ResidualValueCalculator.Calculate(VectronFixture.Model, VectronFixture.Parameters, 7m, Mileage.FromKilometers(840_000m), false, false);
        var vrAverage = Money.Eur((vrStart.Amount + vrEnd.Amount) / 2m);
        var additionalMileagePrice = AdditionalMileageCalculator.CalculatePerKilometerPrice(
            VectronFixture.Model, VectronFixture.BracketA, VectronFixture.Parameters.AdditionalMileageSurcharge);

        var pricedLines = new Dictionary<PriceLine, PricedLine>
        {
            [PriceLine.DryLease] = DryLeaseCalculator.Calculate(VectronFixture.DryLeaseGrid, VectronFixture.BracketA, VectronFixture.Parameters.MaximumDiscount),
            [PriceLine.HeavyMaintenance] = HeavyMaintenanceCalculator.Calculate(VectronFixture.Model, quote.AnnualMileage, VectronFixture.BracketA, VectronFixture.BudgetPlanA, VectronFixture.Parameters.HeavyMaintenanceMargin),
            [PriceLine.OperatingMaintenance] = OperatingMaintenanceCalculator.Calculate(VectronFixture.Model, quote.AnnualMileage, VectronFixture.BracketA, VectronFixture.BudgetPlanA, VectronFixture.Parameters.OperatingMaintenanceMargin),
            [PriceLine.Insurance] = InsuranceCalculator.Calculate(VectronFixture.Model, vrAverage, VectronFixture.Parameters.InsuranceMargin),
        };

        quote.ApplyCalculation(PriceBookNumber.Of(1), VectronFixture.Parameters, vrStart, vrEnd, additionalMileagePrice, pricedLines, preSendControlsFailed: false);

        Assert.True(quote.ValidationLevel >= 1);
    }
}
