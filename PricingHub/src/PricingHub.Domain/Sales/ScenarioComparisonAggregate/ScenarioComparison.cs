using PricingHub.Domain.Common;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Sales.ScenarioComparisonAggregate;

/// <summary>
/// Le comparateur de 3 scénarios (M3-04) — regroupe jusqu'à trois offres
/// côte à côte pour un même client, chacune avec un libellé (ex.
/// "Agressif", "Standard", "Prudent"). N'existait pas comme concept côté
/// Python : le comparateur du prototype (<c>Comparateur.tsx</c>) se
/// contentait d'appeler <c>calculer_offre</c> trois fois côté frontend,
/// sans rien persister. Devient ici un agrégat propre pour que la
/// comparaison elle-même — pas seulement chaque offre — soit retrouvable
/// et partageable entre KAM.
/// </summary>
public sealed class ScenarioComparison : AggregateRoot<ScenarioComparisonId>
{
    public const int MaxScenarios = 3;

    public CustomerCode CustomerCode { get; private set; }
    public string Name { get; private set; } = string.Empty;
    public string CreatedBy { get; private set; } = string.Empty;
    public DateTimeOffset CreatedAt { get; private set; }

    private readonly List<ScenarioEntry> _scenarios = new();
    public IReadOnlyList<ScenarioEntry> Scenarios => _scenarios.AsReadOnly();

#pragma warning disable CS8618
    private ScenarioComparison()
    {
    }
#pragma warning restore CS8618

    private ScenarioComparison(ScenarioComparisonId id, CustomerCode customerCode, string name, string createdBy) : base(id)
    {
        CustomerCode = customerCode;
        Name = name;
        CreatedBy = createdBy;
        CreatedAt = DateTimeOffset.UtcNow;
    }

    public static Result<ScenarioComparison> Create(
        ScenarioComparisonId id, CustomerCode customerCode, string name, string createdBy)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            return Result.Failure<ScenarioComparison>("Le nom du comparateur ne peut pas être vide.");
        }

        if (string.IsNullOrWhiteSpace(createdBy))
        {
            return Result.Failure<ScenarioComparison>("Le créateur du comparateur est obligatoire.");
        }

        return Result.Success(new ScenarioComparison(id, customerCode, name, createdBy));
    }

    /// <summary>Ajoute une offre au comparateur. Échoue au-delà de
    /// <see cref="MaxScenarios"/> (3, M3-04) ou si le libellé est déjà
    /// utilisé dans ce comparateur.</summary>
    public Result AddScenario(string label, QuoteId quoteId, QuoteVersionNumber quoteVersion)
    {
        if (string.IsNullOrWhiteSpace(label))
        {
            return Result.Failure("Le libellé du scénario ne peut pas être vide.");
        }

        if (_scenarios.Count >= MaxScenarios)
        {
            return Result.Failure($"Un comparateur ne peut pas dépasser {MaxScenarios} scénarios.");
        }

        if (_scenarios.Any(s => s.Label.Equals(label, StringComparison.OrdinalIgnoreCase)))
        {
            return Result.Failure($"Le libellé « {label} » est déjà utilisé dans ce comparateur.");
        }

        _scenarios.Add(new ScenarioEntry(label, quoteId, quoteVersion));
        return Result.Success();
    }

    public Result RemoveScenario(string label)
    {
        var entry = _scenarios.FirstOrDefault(s => s.Label.Equals(label, StringComparison.OrdinalIgnoreCase));
        if (entry is null)
        {
            return Result.Failure($"Aucun scénario « {label} » dans ce comparateur.");
        }

        _scenarios.Remove(entry);
        return Result.Success();
    }
}
