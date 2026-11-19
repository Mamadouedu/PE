using PricingHub.Domain.Common;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Catalog.CountryAggregate;

/// <summary>
/// Un pays d'exploitation — équivalent du <c>CountryMatrix</c> du Price
/// Configurator Excel d'Akiem. N'existait pas dans le prototype Python ;
/// la désactivation plutôt que la suppression (<see cref="Deactivate"/>)
/// préserve l'historique des offres qui référencent un pays retiré du
/// catalogue actif.
/// </summary>
public sealed class Country : AggregateRoot<CountryCode>
{
    public string Name { get; private set; } = string.Empty;
    public bool IsActive { get; private set; } = true;

#pragma warning disable CS8618
    private Country()
    {
    }
#pragma warning restore CS8618

    private Country(CountryCode code, string name) : base(code)
    {
        Name = name;
    }

    public static Result<Country> Create(CountryCode code, string name)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            return Result.Failure<Country>("Le nom du pays ne peut pas être vide.");
        }

        return Result.Success(new Country(code, name));
    }

    public void Deactivate() => IsActive = false;

    public void Reactivate() => IsActive = true;
}
