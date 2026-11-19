// Peuple la base de dev (pricinghub_dev) avec un jeu de données minimal mais
// cohérent — équivalent .NET de scripts/seed_dev.py côté Python : la série
// VECTRON du cahier des charges, un référentiel pricing publié, un client.
// Idempotent : ne recrée rien si VECTRON existe déjà.

using Microsoft.EntityFrameworkCore;
using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Catalog.ProductAggregate;
using PricingHub.Domain.Catalog.SeriesAggregate;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Infrastructure.Persistence;
using PricingHub.SharedKernel;

var connectionString = Environment.GetEnvironmentVariable("PRICINGHUB_DATABASE_URL")
    ?? "Host=localhost;Database=pricinghub_dev;Username=pricing;Password=pricing";

var optionsBuilder = new DbContextOptionsBuilder<PricingHubDbContext>();
optionsBuilder.UseNpgsql(connectionString);

await using var db = new PricingHubDbContext(optionsBuilder.Options);

var productCode = ProductCode.Of("LOCOMOTIVE");
var seriesCode = SeriesCode.Of("VECTRON");
var modelCode = ModelCode.Of("VECTRON");

if (await db.Models.AnyAsync(m => m.Id == modelCode))
{
    Console.WriteLine("VECTRON existe déjà — rien à faire.");
    return;
}

var product = Product.Create(productCode, "Locomotive").Value;
var series = Series.Create(seriesCode, productCode, "Vectron").Value;
var model = Model.Create(
    modelCode, seriesCode, "Vectron",
    newValue: Money.Eur(2_000_000m),
    serviceLifeYears: 30,
    endOfLifeResidualRate: Percentage.FromRatio(0.10m),
    referenceAnnualMileage: Mileage.FromKilometers(120_000m),
    heavyMaintenance8YearCost: Money.Eur(150_000m),
    heavyMaintenance16YearCost: Money.Eur(200_000m),
    operatingMaintenanceFixedCost: Money.Eur(6_000m),
    operatingMaintenanceVariableCostPerKilometer: 0.05m,
    annualInsuranceRate: Percentage.FromRatio(0.03m)).Value;

db.Products.Add(product);
db.Series.Add(series);
db.Models.Add(model);

var bracketA = MileageBracket.Create(80_000m, 149_999m, 1.0m, 1.0m, 1.0m).Value;
var bracketB = MileageBracket.Create(150_000m, 200_000m, 1.05m, 1.1m, 1.05m).Value;

var priceBook = PriceBook.CreateDraft(PriceBookNumber.Of(1), PricingParameters.Defaults(Currency.Eur));
priceBook.AddMileageBracket(bracketA);
priceBook.AddMileageBracket(bracketB);
priceBook.AddDryLeaseGridEntry(
    DryLeaseGridEntry.Create(modelCode, DurationBracket.Create(0, null).Value, Money.Eur(20_000m)).Value);
priceBook.AddBudgetPlanEntry(
    BudgetPlanEntry.Create(modelCode, bracketA, Money.Eur(2_000m), Money.Eur(1_500m), "2026").Value);
priceBook.AddBudgetPlanEntry(
    BudgetPlanEntry.Create(modelCode, bracketB, Money.Eur(2_400m), Money.Eur(1_800m), "2026").Value);
priceBook.Publish("seed-dev");

db.PriceBooks.Add(priceBook);

var customer = Customer.Create(
    CustomerCode.Of("CLIENTOK"), "Client standard", creditRating: 5, segment: "Fret",
    cashDeposit: Money.Eur(0m), paysInAdvance: true).Value;
db.Customers.Add(customer);

await db.SaveChangesAsync();

Console.WriteLine("Référentiel de dev créé : produit LOCOMOTIVE, série VECTRON, modèle VECTRON,");
Console.WriteLine("référentiel pricing n°1 publié, client CLIENTOK.");
