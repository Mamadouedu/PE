using PricingHub.Domain.Common;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Sales.CustomerAggregate;

/// <summary>
/// Un client Akiem — rating crédit, dépôt de garantie, mode de paiement.
/// Équivalent du modèle Python <c>Client</c>, consulté par les contrôles
/// avant envoi C3 et C5 (section 6.4), portés sur le client plutôt que sur
/// le moteur de prix (ils en sont indépendants).
/// </summary>
public sealed class Customer : AggregateRoot<CustomerCode>
{
    public string Name { get; private set; } = string.Empty;

    /// <summary>Rating crédit, de 0 (le plus risqué) à 10.</summary>
    public int CreditRating { get; private set; }

    public string Segment { get; private set; } = string.Empty;
    public Money CashDeposit { get; private set; }
    public bool PaysInAdvance { get; private set; }

#pragma warning disable CS8618
    private Customer()
    {
    }
#pragma warning restore CS8618

    private Customer(CustomerCode code, string name, int creditRating, string segment, Money cashDeposit, bool paysInAdvance)
        : base(code)
    {
        Name = name;
        CreditRating = creditRating;
        Segment = segment;
        CashDeposit = cashDeposit;
        PaysInAdvance = paysInAdvance;
    }

    public static Result<Customer> Create(
        CustomerCode code, string name, int creditRating, string segment, Money cashDeposit, bool paysInAdvance)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            return Result.Failure<Customer>("Le nom du client ne peut pas être vide.");
        }

        if (creditRating is < 0 or > 10)
        {
            return Result.Failure<Customer>("Le rating doit être compris entre 0 et 10.");
        }

        if (cashDeposit.Amount < 0m)
        {
            return Result.Failure<Customer>("Le cash deposit ne peut pas être négatif.");
        }

        return Result.Success(new Customer(code, name, creditRating, segment, cashDeposit, paysInAdvance));
    }

    /// <summary>Contrôle C5 (section 6.4) : garantie de paiement — cash
    /// deposit ou paiement d'avance.</summary>
    public bool HasPaymentGuarantee => CashDeposit.Amount > 0m || PaysInAdvance;

    /// <summary>Contrôle C3 (section 6.4) : au-delà de ce seuil de rating,
    /// durée courte et paiement d'avance sont exigés.</summary>
    public bool HasHighCreditRisk(int highRatingThreshold) => CreditRating > highRatingThreshold;
}
