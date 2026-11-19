namespace PricingHub.SharedKernel;

/// <summary>
/// Un montant dans une devise donnée. Toutes les briques du prix (Dry
/// lease, HM, OM, assurance) sont des <see cref="Money"/>, jamais des
/// <c>decimal</c> nus — impossible d'additionner par erreur un prix et un
/// pourcentage, ou deux montants de devises différentes.
/// </summary>
public readonly record struct Money
{
    public decimal Amount { get; }
    public Currency Currency { get; }

    private Money(decimal amount, Currency currency)
    {
        Amount = amount;
        Currency = currency;
    }

    public static Money Of(decimal amount, Currency currency) => new(amount, currency);

    public static Money Eur(decimal amount) => new(amount, Currency.Eur);

    public static Money Zero(Currency currency) => new(0m, currency);

    public Money Add(Money other)
    {
        EnsureSameCurrency(other);
        return new Money(Amount + other.Amount, Currency);
    }

    public Money Subtract(Money other)
    {
        EnsureSameCurrency(other);
        return new Money(Amount - other.Amount, Currency);
    }

    public Money Multiply(decimal factor) => new(Amount * factor, Currency);

    public Money Multiply(Percentage percentage) => new(Amount * percentage.Value, Currency);

    public Money Max(Money other)
    {
        EnsureSameCurrency(other);
        return Amount >= other.Amount ? this : other;
    }

    public Money Min(Money other)
    {
        EnsureSameCurrency(other);
        return Amount <= other.Amount ? this : other;
    }

    public static Money operator +(Money left, Money right) => left.Add(right);
    public static Money operator -(Money left, Money right) => left.Subtract(right);
    public static Money operator *(Money money, decimal factor) => money.Multiply(factor);
    public static Money operator *(Money money, Percentage percentage) => money.Multiply(percentage);

    public static bool operator <(Money left, Money right)
    {
        left.EnsureSameCurrency(right);
        return left.Amount < right.Amount;
    }

    public static bool operator >(Money left, Money right)
    {
        left.EnsureSameCurrency(right);
        return left.Amount > right.Amount;
    }

    public static bool operator <=(Money left, Money right)
    {
        left.EnsureSameCurrency(right);
        return left.Amount <= right.Amount;
    }

    public static bool operator >=(Money left, Money right)
    {
        left.EnsureSameCurrency(right);
        return left.Amount >= right.Amount;
    }

    private void EnsureSameCurrency(Money other)
    {
        if (Currency != other.Currency)
        {
            throw new InvalidOperationException(
                $"Impossible de combiner des montants en {Currency.Code} et en {other.Currency.Code}.");
        }
    }

    public override string ToString() => $"{Amount:N2} {Currency.Code}";
}
