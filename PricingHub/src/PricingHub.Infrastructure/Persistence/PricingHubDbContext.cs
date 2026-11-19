using Microsoft.EntityFrameworkCore;
using PricingHub.Domain.Catalog.CountryAggregate;
using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Catalog.ProductAggregate;
using PricingHub.Domain.Catalog.SeriesAggregate;
using PricingHub.Domain.Pricing.CampaignAggregate;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.OpportunityAggregate;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.Domain.Sales.ScenarioComparisonAggregate;
using PricingHub.Domain.Workflow.ApprovalRequestAggregate;
using PricingHub.Domain.Workflow.DelegationAggregate;

namespace PricingHub.Infrastructure.Persistence;

/// <summary>
/// Le point d'entrée EF Core vers PostgreSQL. Les agrégats sont ajoutés au
/// fur et à mesure que leur <c>IEntityTypeConfiguration</c> est écrite et
/// vérifiée contre une vraie base (voir les tests d'intégration) — pas
/// d'un coup, pour garder chaque étape vérifiable isolément.
/// </summary>
public sealed class PricingHubDbContext : DbContext
{
    public PricingHubDbContext(DbContextOptions<PricingHubDbContext> options) : base(options)
    {
    }

    public DbSet<Product> Products => Set<Product>();
    public DbSet<Series> Series => Set<Series>();
    public DbSet<Model> Models => Set<Model>();
    public DbSet<Country> Countries => Set<Country>();
    public DbSet<PriceBook> PriceBooks => Set<PriceBook>();
    public DbSet<Campaign> Campaigns => Set<Campaign>();
    public DbSet<Customer> Customers => Set<Customer>();
    public DbSet<Opportunity> Opportunities => Set<Opportunity>();
    public DbSet<Quote> Quotes => Set<Quote>();
    public DbSet<ScenarioComparison> ScenarioComparisons => Set<ScenarioComparison>();
    public DbSet<ApprovalRequest> ApprovalRequests => Set<ApprovalRequest>();
    public DbSet<Delegation> Delegations => Set<Delegation>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        // QuoteVersion.Lines est packé en JSON (voir ValueConverters.ForQuoteLines), pas
        // mappé comme type possédé : sans cet Ignore explicite, les conventions EF Core
        // découvrent quand même QuoteLine comme type d'entité via la propriété collection,
        // avant même que la configuration Fluent de QuoteVersion ne s'applique, et la
        // construction du modèle échoue (confirmé par dotnet ef migrations add).
        modelBuilder.Ignore<QuoteLine>();

        modelBuilder.ApplyConfigurationsFromAssembly(typeof(PricingHubDbContext).Assembly);
    }
}
