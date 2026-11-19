using PricingHub.Domain.Catalog.ProductAggregate;
using PricingHub.Domain.Common;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Catalog.SeriesAggregate;

/// <summary>
/// Une série de locomotives (ex. Vectron, Traxx, Prima, EuroDual) —
/// appartient à un <see cref="Product"/> et regroupe les
/// <c>Catalog.ModelAggregate.Model</c> qui en sont les variantes
/// techniques (ex. série Traxx → modèles Traxx AC3, Traxx DC3, Traxx MS3).
///
/// Ne porte aucune donnée de prix : simple groupement commercial/technique.
/// Les données qui alimentent le prix (valeur à neuf, coûts de
/// maintenance, taux d'assurance) vivent sur <c>Model</c>, pas ici — c'est
/// <c>Model</c> qui remplace directement l'onglet « Models » du Price
/// Configurator Excel d'Akiem, à la granularité où les coûts varient
/// réellement d'une variante technique à l'autre.
/// </summary>
public sealed class Series : AggregateRoot<SeriesCode>
{
    public ProductCode ProductCode { get; private set; }
    public string Name { get; private set; } = string.Empty;

#pragma warning disable CS8618
    private Series()
    {
    }
#pragma warning restore CS8618

    private Series(SeriesCode code, ProductCode productCode, string name) : base(code)
    {
        ProductCode = productCode;
        Name = name;
    }

    public static Result<Series> Create(SeriesCode code, ProductCode productCode, string name)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            return Result.Failure<Series>("Le nom de la série ne peut pas être vide.");
        }

        return Result.Success(new Series(code, productCode, name));
    }
}
