using PricingHub.Domain.Common;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Workflow.DelegationAggregate;

/// <summary>
/// Un validateur délégué pour un niveau de validation donné — la table
/// Délégation (section 8.3 du cahier des charges), un validateur par
/// niveau (1 à 3). Équivalent du modèle Python <c>Validateur</c>.
///
/// Le niveau est calculé par le moteur de prix et n'est jamais choisi par
/// le KAM (M4-01) ; cet agrégat répond simplement à « qui, pour ce
/// niveau ? ». Le rappel et l'escalade après délai vers le suppléant
/// restent la responsabilité du flow Power Automate/Teams déclenché par
/// <c>Workflow.ApprovalRequestAggregate</c>, pas de cet agrégat.
/// </summary>
public sealed class Delegation : AggregateRoot<ValidationLevel>
{
    public string Name { get; private set; } = string.Empty;
    public string Email { get; private set; } = string.Empty;
    public string? AlternateEmail { get; private set; }

#pragma warning disable CS8618
    private Delegation()
    {
    }
#pragma warning restore CS8618

    private Delegation(ValidationLevel level, string name, string email, string? alternateEmail) : base(level)
    {
        Name = name;
        Email = email;
        AlternateEmail = alternateEmail;
    }

    public static Result<Delegation> Create(ValidationLevel level, string name, string email, string? alternateEmail = null)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            return Result.Failure<Delegation>("Le nom du validateur ne peut pas être vide.");
        }

        if (string.IsNullOrWhiteSpace(email) || !email.Contains('@'))
        {
            return Result.Failure<Delegation>("Le validateur doit avoir un e-mail valide.");
        }

        return Result.Success(new Delegation(level, name, email, alternateEmail));
    }

    public void Reassign(string name, string email, string? alternateEmail)
    {
        Name = name;
        Email = email;
        AlternateEmail = alternateEmail;
    }
}
