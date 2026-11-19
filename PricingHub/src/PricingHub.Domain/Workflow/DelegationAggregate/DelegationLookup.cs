namespace PricingHub.Domain.Workflow.DelegationAggregate;

/// <summary>Résout le validateur délégué pour un niveau de validation
/// calculé — équivalent de <c>VersionReferentiel.validateur_pour</c> /
/// <c>engine.validateur_requis</c> (le niveau 0 n'a pas de validateur : la
/// demande elle-même est refusée avant d'en chercher un, voir
/// <c>ApprovalRequest.Request</c>).</summary>
public static class DelegationLookup
{
    public static Delegation? ValidatorFor(IEnumerable<Delegation> delegations, int validationLevel) =>
        validationLevel is >= 1 and <= 3
            ? delegations.FirstOrDefault(d => d.Id.Value == validationLevel)
            : null;
}
