using System.Globalization;
using System.Text.Json;
using Microsoft.EntityFrameworkCore.ChangeTracking;
using Microsoft.EntityFrameworkCore.Storage.ValueConversion;
using PricingHub.Domain.Pricing;
using PricingHub.Domain.Pricing.Calculations;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.Infrastructure.Persistence.Conversions;

/// <summary>
/// Fabriques de <see cref="ValueConverter{TModel,TProvider}"/> pour les
/// value objects mono-champ du domaine (codes métier, <c>Percentage</c>,
/// <c>Duration</c>, <c>Mileage</c>, <c>Currency</c>, identifiants Guid/int).
/// Ils se mappent chacun sur une seule colonne — pas de type complexe
/// nécessaire, juste une conversion aller-retour.
/// </summary>
public static class ValueConverters
{
    public static ValueConverter<TModel, string> ForString<TModel>(Func<TModel, string> toProvider, Func<string, TModel> fromProvider) =>
        new(model => toProvider(model), provider => fromProvider(provider));

    public static ValueConverter<TModel, int> ForInt<TModel>(Func<TModel, int> toProvider, Func<int, TModel> fromProvider) =>
        new(model => toProvider(model), provider => fromProvider(provider));

    public static ValueConverter<TModel, decimal> ForDecimal<TModel>(Func<TModel, decimal> toProvider, Func<decimal, TModel> fromProvider) =>
        new(model => toProvider(model), provider => fromProvider(provider));

    public static ValueConverter<TModel, Guid> ForGuid<TModel>(Func<TModel, Guid> toProvider, Func<Guid, TModel> fromProvider) =>
        new(model => toProvider(model), provider => fromProvider(provider));

    /// <summary>
    /// <see cref="Money"/> (montant + devise) packé sur une seule colonne
    /// texte (ex. <c>"2000000.0000|EUR"</c>). Réservé aux cas où EF Core 8
    /// ne sait pas mapper <see cref="Money"/> comme un type possédé ou
    /// complexe — un <c>OwnsOne</c> ciblant un <c>readonly record struct</c>
    /// à l'intérieur d'une collection possédée échoue à la compilation en
    /// EF Core 8 (confirmé empiriquement : un seul <c>OwnsOne(x =&gt; x.Money)</c>
    /// imbriqué dans un <c>OwnsMany</c> suffit à faire perdre la résolution
    /// de type du bloc entier). Ailleurs (propriété directe d'une entité,
    /// ou imbriqué dans un autre <c>ComplexProperty</c>), préférer
    /// <c>ComplexProperty</c> — deux vraies colonnes, interrogeables en SQL.
    /// </summary>
    public static ValueConverter<Money, string> ForMoney() => new(
        money => PackMoney(money),
        packed => ParseMoney(packed));

    internal static string PackMoney(Money money) => $"{money.Amount.ToString(CultureInfo.InvariantCulture)}|{money.Currency.Code}";

    internal static Money ParseMoney(string packed)
    {
        var parts = packed.Split('|');
        var amount = decimal.Parse(parts[0], CultureInfo.InvariantCulture);
        return Money.Of(amount, Currency.FromCode(parts[1]));
    }

    /// <summary>
    /// Même contournement que <see cref="ForMoney"/>, pour la même raison :
    /// <see cref="MileageBracket"/> possédé en tant que champ d'un AUTRE
    /// type possédé (<c>BudgetPlanEntry.MileageBracket</c>) ne peut pas
    /// être lié au constructeur de son parent en EF Core 8 (« references to
    /// owned types[...] cannot be bound »). Sans objet pour
    /// <c>PriceBook.MileageBrackets</c>, qui reste mappé en <c>OwnsMany</c>
    /// classique — la contrainte ne s'applique qu'à l'imbrication
    /// possédé-dans-possédé, pas au type possédé lui-même.
    /// </summary>
    public static ValueConverter<MileageBracket, string> ForMileageBracket() => new(
        bracket => string.Join('|',
            bracket.MinKilometers.ToString(CultureInfo.InvariantCulture),
            bracket.MaxKilometers.HasValue ? bracket.MaxKilometers.Value.ToString(CultureInfo.InvariantCulture) : string.Empty,
            bracket.DryLeaseCoefficient.ToString(CultureInfo.InvariantCulture),
            bracket.HeavyMaintenanceCoefficient.ToString(CultureInfo.InvariantCulture),
            bracket.OperatingMaintenanceCoefficient.ToString(CultureInfo.InvariantCulture)),
        packed => ParseMileageBracket(packed));

    private static MileageBracket ParseMileageBracket(string packed)
    {
        var parts = packed.Split('|');
        var minKilometers = decimal.Parse(parts[0], CultureInfo.InvariantCulture);
        decimal? maxKilometers = parts[1].Length == 0 ? null : decimal.Parse(parts[1], CultureInfo.InvariantCulture);
        var dryLeaseCoefficient = decimal.Parse(parts[2], CultureInfo.InvariantCulture);
        var heavyMaintenanceCoefficient = decimal.Parse(parts[3], CultureInfo.InvariantCulture);
        var operatingMaintenanceCoefficient = decimal.Parse(parts[4], CultureInfo.InvariantCulture);
        return MileageBracket.Create(
            minKilometers, maxKilometers, dryLeaseCoefficient, heavyMaintenanceCoefficient, operatingMaintenanceCoefficient).Value;
    }

    /// <summary>Même raison que <see cref="ForMileageBracket"/> :
    /// <c>DryLeaseGridEntry.DurationBracket</c> est un type possédé imbriqué
    /// dans un autre type possédé.</summary>
    public static ValueConverter<DurationBracket, string> ForDurationBracket() => new(
        bracket => bracket.MinMonths.ToString(CultureInfo.InvariantCulture) + "|"
            + (bracket.MaxMonths.HasValue ? bracket.MaxMonths.Value.ToString(CultureInfo.InvariantCulture) : string.Empty),
        packed => ParseDurationBracket(packed));

    private static DurationBracket ParseDurationBracket(string packed)
    {
        var parts = packed.Split('|');
        var minMonths = int.Parse(parts[0], CultureInfo.InvariantCulture);
        int? maxMonths = parts[1].Length == 0 ? null : int.Parse(parts[1], CultureInfo.InvariantCulture);
        return DurationBracket.Create(minMonths, maxMonths).Value;
    }

    /// <summary>Une <c>IReadOnlyList&lt;QuoteId&gt;</c> (sans identité
    /// propre côté stockage) packée en JSON — utilisé par
    /// <c>Opportunity.QuoteIds</c>. Le type modèle suit exactement le type
    /// de la propriété publique (<c>IReadOnlyList</c>, pas <c>List</c>) :
    /// EF écrit directement dans le champ privé (<c>PropertyAccessMode.Field</c>),
    /// mais la conversion elle-même reste indexée sur la signature publique.</summary>
    public static ValueConverter<IReadOnlyList<QuoteId>, string> ForQuoteIdList() => new(
        list => SerializeQuoteIds(list),
        json => DeserializeQuoteIds(json));

    public static ValueComparer<IReadOnlyList<QuoteId>> QuoteIdListComparer { get; } = new(
        (a, b) => QuoteIdListEquals(a, b),
        list => QuoteIdListHashCode(list),
        list => list.ToList());

    private static string SerializeQuoteIds(IReadOnlyList<QuoteId> list) =>
        JsonSerializer.Serialize(list.Select(x => x.Value).ToArray());

    private static List<QuoteId> DeserializeQuoteIds(string json) =>
        (JsonSerializer.Deserialize<Guid[]>(json) ?? Array.Empty<Guid>()).Select(QuoteId.Of).ToList();

    private static bool QuoteIdListEquals(IReadOnlyList<QuoteId>? a, IReadOnlyList<QuoteId>? b) =>
        (a ?? new List<QuoteId>()).SequenceEqual(b ?? new List<QuoteId>());

    private static int QuoteIdListHashCode(IReadOnlyList<QuoteId> list) =>
        list.Aggregate(0, (hash, item) => HashCode.Combine(hash, item.Value));

    /// <summary>Un <c>IReadOnlySet&lt;PriceLine&gt;</c> packé en JSON —
    /// utilisé par <c>QuoteVersion.IncludedLines</c>. Le type modèle suit
    /// le type de la propriété publique (<c>IReadOnlySet</c>), pas le champ
    /// privé (<c>HashSet</c>) — même raison que <see cref="ForQuoteIdList"/>.</summary>
    public static ValueConverter<IReadOnlySet<PriceLine>, string> ForPriceLineSet() => new(
        set => SerializePriceLineSet(set),
        json => DeserializePriceLineSet(json));

    public static ValueComparer<IReadOnlySet<PriceLine>> PriceLineSetComparer { get; } = new(
        (a, b) => PriceLineSetEquals(a, b),
        set => PriceLineSetHashCode(set),
        set => new HashSet<PriceLine>(set));

    private static string SerializePriceLineSet(IReadOnlySet<PriceLine> set) => JsonSerializer.Serialize(set.ToArray());

    private static HashSet<PriceLine> DeserializePriceLineSet(string json) =>
        new(JsonSerializer.Deserialize<PriceLine[]>(json) ?? Array.Empty<PriceLine>());

    private static bool PriceLineSetEquals(IReadOnlySet<PriceLine>? a, IReadOnlySet<PriceLine>? b) =>
        (a ?? new HashSet<PriceLine>()).SetEquals(b ?? new HashSet<PriceLine>());

    private static int PriceLineSetHashCode(IReadOnlySet<PriceLine> set) =>
        set.Aggregate(0, (hash, item) => HashCode.Combine(hash, item));

    /// <summary>Un <c>IReadOnlyDictionary&lt;PriceLine, Money&gt;</c> packé
    /// en JSON (via un DTO intermédiaire : <see cref="Money"/> n'a pas de
    /// constructeur public, System.Text.Json ne peut pas le désérialiser
    /// directement) — utilisé par <c>QuoteVersion.NegotiatedPrices</c>. Le
    /// type modèle suit la propriété publique (<c>IReadOnlyDictionary</c>),
    /// pas le champ privé (<c>Dictionary</c>).</summary>
    public static ValueConverter<IReadOnlyDictionary<PriceLine, Money>, string> ForNegotiatedPrices() => new(
        dict => SerializeNegotiatedPrices(dict),
        json => DeserializeNegotiatedPrices(json));

    public static ValueComparer<IReadOnlyDictionary<PriceLine, Money>> NegotiatedPricesComparer { get; } = new(
        (a, b) => NegotiatedPricesEquals(a, b),
        dict => NegotiatedPricesHashCode(dict),
        dict => new Dictionary<PriceLine, Money>(dict));

    private static bool NegotiatedPricesEquals(IReadOnlyDictionary<PriceLine, Money>? a, IReadOnlyDictionary<PriceLine, Money>? b)
    {
        a ??= new Dictionary<PriceLine, Money>();
        b ??= new Dictionary<PriceLine, Money>();
        return a.Count == b.Count && a.All(kv => b.TryGetValue(kv.Key, out var value) && value.Equals(kv.Value));
    }

    private static int NegotiatedPricesHashCode(IReadOnlyDictionary<PriceLine, Money> dict) =>
        dict.Aggregate(0, (hash, kv) => HashCode.Combine(hash, kv.Key, kv.Value.Amount, kv.Value.Currency.Code));

    private sealed record NegotiatedPriceDto(PriceLine Line, decimal Amount, string CurrencyCode);

    private static string SerializeNegotiatedPrices(IReadOnlyDictionary<PriceLine, Money> dict) =>
        JsonSerializer.Serialize(dict.Select(kv => new NegotiatedPriceDto(kv.Key, kv.Value.Amount, kv.Value.Currency.Code)).ToArray());

    private static Dictionary<PriceLine, Money> DeserializeNegotiatedPrices(string json)
    {
        var dtos = JsonSerializer.Deserialize<NegotiatedPriceDto[]>(json) ?? Array.Empty<NegotiatedPriceDto>();
        return dtos.ToDictionary(d => d.Line, d => Money.Of(d.Amount, Currency.FromCode(d.CurrencyCode)));
    }

    /// <summary>Une <c>IReadOnlyList&lt;string&gt;</c> packée en JSON —
    /// utilisé par <c>QuoteVersion.ValidationLevelReasons</c>.</summary>
    public static ValueConverter<IReadOnlyList<string>, string> ForStringList() => new(
        list => SerializeStringList(list),
        json => DeserializeStringList(json));

    public static ValueComparer<IReadOnlyList<string>> StringListComparer { get; } = new(
        (a, b) => StringListEquals(a, b),
        list => StringListHashCode(list),
        list => list.ToList());

    private static string SerializeStringList(IReadOnlyList<string> list) => JsonSerializer.Serialize(list.ToArray());

    private static List<string> DeserializeStringList(string json) =>
        JsonSerializer.Deserialize<List<string>>(json) ?? new List<string>();

    private static bool StringListEquals(IReadOnlyList<string>? a, IReadOnlyList<string>? b) =>
        (a ?? new List<string>()).SequenceEqual(b ?? new List<string>());

    private static int StringListHashCode(IReadOnlyList<string> list) =>
        list.Aggregate(0, (hash, item) => HashCode.Combine(hash, item));

    /// <summary>
    /// Les <see cref="QuoteLine"/> d'une <c>QuoteVersion</c>, packées en
    /// JSON plutôt qu'en <c>OwnsMany</c> imbriqué dans un <c>OwnsMany</c> :
    /// trois niveaux d'imbrication possédée (Quote → QuoteVersion →
    /// QuoteLine) ne sont pas résolus par EF Core 8 (confirmé
    /// empiriquement par <c>dotnet ef migrations add</c> — « Unable to
    /// determine the relationship... »), alors que deux niveaux
    /// fonctionnent (voir <c>PriceBook</c>). Reconstruit chaque
    /// <see cref="QuoteLine"/> via ses fabriques publiques
    /// (<see cref="QuoteLine.Included"/>/<see cref="QuoteLine.Excluded"/>)
    /// plutôt que de stocker le statut et le prix retenu — ils sont
    /// dérivés déterministes de (coût, catalogue, plancher, prix négocié),
    /// pas une donnée indépendante.
    /// </summary>
    public static ValueConverter<IReadOnlyList<QuoteLine>, string> ForQuoteLines() => new(
        lines => SerializeQuoteLines(lines),
        json => DeserializeQuoteLines(json));

    public static ValueComparer<IReadOnlyList<QuoteLine>> QuoteLinesComparer { get; } = new(
        (a, b) => QuoteLinesEqual(a, b),
        lines => QuoteLinesHashCode(lines),
        lines => lines.ToList());

    private sealed record QuoteLineDto(
        PriceLine Line, string Cost, string CatalogPrice, string Floor, string? NegotiatedPrice, bool IsExcluded);

    private static string SerializeQuoteLines(IReadOnlyList<QuoteLine> lines) =>
        JsonSerializer.Serialize(lines.Select(l => new QuoteLineDto(
            l.Line,
            PackMoney(l.Cost),
            PackMoney(l.CatalogPrice),
            PackMoney(l.Floor),
            l.NegotiatedPrice.HasValue ? PackMoney(l.NegotiatedPrice.Value) : null,
            l.Status == QuoteLineStatus.Excluded)).ToArray());

    private static List<QuoteLine> DeserializeQuoteLines(string json)
    {
        var dtos = JsonSerializer.Deserialize<QuoteLineDto[]>(json) ?? Array.Empty<QuoteLineDto>();
        return dtos.Select(dto =>
        {
            var pricedLine = new PricedLine(dto.Line, ParseMoney(dto.Cost), ParseMoney(dto.CatalogPrice), ParseMoney(dto.Floor));
            return dto.IsExcluded
                ? QuoteLine.Excluded(pricedLine)
                : QuoteLine.Included(pricedLine, dto.NegotiatedPrice is null ? null : ParseMoney(dto.NegotiatedPrice));
        }).ToList();
    }

    private static bool QuoteLinesEqual(IReadOnlyList<QuoteLine>? a, IReadOnlyList<QuoteLine>? b) =>
        SerializeQuoteLines(a ?? new List<QuoteLine>()) == SerializeQuoteLines(b ?? new List<QuoteLine>());

    private static int QuoteLinesHashCode(IReadOnlyList<QuoteLine> lines) => SerializeQuoteLines(lines).GetHashCode();
}
