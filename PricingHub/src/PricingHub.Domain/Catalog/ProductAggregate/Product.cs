using PricingHub.Domain.Common;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Catalog.ProductAggregate;

/// <summary>
/// Une famille de produit — le niveau le plus large du catalogue (ex.
/// Locomotive, Passenger Train, Freight Wagon, Maintenance Package).
/// N'existait pas dans le prototype Python, qui ne couvrait que la
/// location de locomotives ; introduit pour refléter le catalogue réel
/// d'Akiem (audit du Price Configurator Excel), où une <c>Series</c>
/// (Vectron, Traxx, Prima, EuroDual...) appartient toujours à un Product.
/// Ne porte aucune donnée de prix : celles-ci vivent sur
/// <c>Catalog.ModelAggregate.Model</c>, au niveau le plus fin.
/// </summary>
public sealed class Product : AggregateRoot<ProductCode>
{
    public string Name { get; private set; } = string.Empty;

#pragma warning disable CS8618
    private Product()
    {
    }
#pragma warning restore CS8618

    private Product(ProductCode code, string name) : base(code)
    {
        Name = name;
    }

    public static Result<Product> Create(ProductCode code, string name)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            return Result.Failure<Product>("Le nom du produit ne peut pas être vide.");
        }

        return Result.Success(new Product(code, name));
    }
}
