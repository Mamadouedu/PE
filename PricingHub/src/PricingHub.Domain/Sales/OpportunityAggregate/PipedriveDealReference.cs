namespace PricingHub.Domain.Sales.OpportunityAggregate;

/// <summary>Référence vers le deal Pipedrive lié — l'écriture retour que
/// les KAM n'effectuent pas toujours manuellement une fois le prix validé
/// (M3-06) ; c'est l'identifiant que l'intégration Pipedrive doit mettre à
/// jour.</summary>
public readonly record struct PipedriveDealReference
{
    public int DealId { get; }

    private PipedriveDealReference(int dealId) => DealId = dealId;

    public static PipedriveDealReference Of(int dealId)
    {
        if (dealId <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(dealId), dealId, "L'identifiant du deal Pipedrive doit être strictement positif.");
        }

        return new PipedriveDealReference(dealId);
    }

    public override string ToString() => DealId.ToString();
}
