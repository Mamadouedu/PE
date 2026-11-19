namespace PricingHub.SharedKernel;

/// <summary>
/// Code devise ISO 4217. Le cahier des charges exprime tous les prix en
/// euros HT, mais les offres PDF doivent pouvoir être émises "dans la
/// langue du client" (section 9) — garder la devise explicite plutôt que
/// de coder EUR en dur partout facilite une extension future.
/// </summary>
public readonly record struct Currency
{
    public string Code { get; }

    private Currency(string code) => Code = code;

    public static readonly Currency Eur = new("EUR");

    public static Currency FromCode(string code)
    {
        if (string.IsNullOrWhiteSpace(code) || code.Length != 3)
        {
            throw new ArgumentException("Le code devise doit comporter exactement 3 lettres (ISO 4217).", nameof(code));
        }

        return new Currency(code.ToUpperInvariant());
    }

    public override string ToString() => Code;
}
