using Microsoft.EntityFrameworkCore;
using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Catalog.ProductAggregate;
using PricingHub.Domain.Catalog.SeriesAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.InfrastructureTests.Catalog;

/// <summary>
/// Premier test contre une vraie base : vérifie que <c>ComplexProperty</c>
/// (EF Core 8) mappe correctement <see cref="Money"/> (montant + devise,
/// deux colonnes) sur un <see cref="Model"/> complet — la pièce la plus à
/// risque de la configuration Catalog, puisque c'est un mécanisme EF Core
/// relativement récent.
/// </summary>
public class CatalogRoundTripTests
{
    [Fact]
    public async Task UnModelComplet_SurvitAUnAllerRetourEnBase()
    {
        var productCode = ProductCode.Of($"TEST_PRODUCT_{Guid.NewGuid():N}");
        var seriesCode = SeriesCode.Of($"TEST_SERIES_{Guid.NewGuid():N}");
        var modelCode = ModelCode.Of($"TEST_MODEL_{Guid.NewGuid():N}");

        await using (var write = DatabaseFixture.CreateContext())
        {
            var product = Product.Create(productCode, "Locomotive (test)").Value;
            var series = Series.Create(seriesCode, productCode, "Vectron (test)").Value;
            var model = Model.Create(
                modelCode, seriesCode, "Vectron MS (test)",
                newValue: Money.Eur(2_000_000m),
                serviceLifeYears: 30,
                endOfLifeResidualRate: Percentage.FromRatio(0.10m),
                referenceAnnualMileage: Mileage.FromKilometers(120_000m),
                heavyMaintenance8YearCost: Money.Eur(150_000m),
                heavyMaintenance16YearCost: Money.Eur(200_000m),
                operatingMaintenanceFixedCost: Money.Eur(6_000m),
                operatingMaintenanceVariableCostPerKilometer: 0.05m,
                annualInsuranceRate: Percentage.FromRatio(0.03m)).Value;

            write.Products.Add(product);
            write.Series.Add(series);
            write.Models.Add(model);
            await write.SaveChangesAsync();
        }

        await using var read = DatabaseFixture.CreateContext();
        var reloaded = await read.Models.SingleAsync(m => m.Id == modelCode);

        Assert.Equal("Vectron MS (test)", reloaded.Name);
        Assert.Equal(seriesCode, reloaded.SeriesCode);
        Assert.Equal(2_000_000m, reloaded.NewValue.Amount);
        Assert.Equal(Currency.Eur, reloaded.NewValue.Currency);
        Assert.Equal(30, reloaded.ServiceLifeYears);
        Assert.Equal(0.10m, reloaded.EndOfLifeResidualRate.Value);
        Assert.Equal(120_000m, reloaded.ReferenceAnnualMileage.Kilometers);
        Assert.Equal(150_000m, reloaded.HeavyMaintenance8YearCost.Amount);
        Assert.Equal(200_000m, reloaded.HeavyMaintenance16YearCost.Amount);
        Assert.Equal(6_000m, reloaded.OperatingMaintenanceFixedCost.Amount);
        Assert.Equal(0.05m, reloaded.OperatingMaintenanceVariableCostPerKilometer);
        Assert.Equal(0.03m, reloaded.AnnualInsuranceRate.Value);

        // Nettoyage : ce test écrit dans la vraie base de dev, pas une base jetable.
        await using var cleanup = DatabaseFixture.CreateContext();
        cleanup.Models.Remove(reloaded);
        cleanup.Series.Remove(await cleanup.Series.SingleAsync(s => s.Id == seriesCode));
        cleanup.Products.Remove(await cleanup.Products.SingleAsync(p => p.Id == productCode));
        await cleanup.SaveChangesAsync();
    }
}
