using PricingHub.Domain.Common;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Sales.OpportunityAggregate;

/// <summary>
/// Une opportunité commerciale — le pendant interne d'un deal Pipedrive.
/// N'existe pas dans le prototype Python (qui ne modélisait qu'une offre
/// isolée) : introduite ici parce qu'un KAM négocie souvent plusieurs
/// offres (plusieurs séries, plusieurs scénarios) pour une même
/// opportunité commerciale avant qu'une ne soit retenue, et parce que
/// l'écriture retour Pipedrive (M3-06) a besoin d'un point d'ancrage
/// stable — le deal — indépendant de chaque <see cref="Quote"/>.
/// </summary>
public sealed class Opportunity : AggregateRoot<OpportunityId>
{
    public CustomerCode CustomerCode { get; private set; }
    public string Title { get; private set; } = string.Empty;
    public OpportunityStatus Status { get; private set; } = OpportunityStatus.Open;
    public PipedriveDealReference? PipedriveDeal { get; private set; }

    private readonly List<QuoteId> _quoteIds = new();
    public IReadOnlyList<QuoteId> QuoteIds => _quoteIds.AsReadOnly();

#pragma warning disable CS8618
    private Opportunity()
    {
    }
#pragma warning restore CS8618

    private Opportunity(OpportunityId id, CustomerCode customerCode, string title) : base(id)
    {
        CustomerCode = customerCode;
        Title = title;
    }

    public static Result<Opportunity> Open(OpportunityId id, CustomerCode customerCode, string title)
    {
        if (string.IsNullOrWhiteSpace(title))
        {
            return Result.Failure<Opportunity>("Le titre de l'opportunité ne peut pas être vide.");
        }

        return Result.Success(new Opportunity(id, customerCode, title));
    }

    public void LinkQuote(QuoteId quoteId)
    {
        if (!_quoteIds.Contains(quoteId))
        {
            _quoteIds.Add(quoteId);
        }
    }

    public void LinkPipedriveDeal(PipedriveDealReference pipedriveDeal) => PipedriveDeal = pipedriveDeal;

    public Result MarkWon()
    {
        if (Status != OpportunityStatus.Open)
        {
            return Result.Failure("Seule une opportunité ouverte peut être gagnée.");
        }

        Status = OpportunityStatus.Won;
        return Result.Success();
    }

    public Result MarkLost()
    {
        if (Status != OpportunityStatus.Open)
        {
            return Result.Failure("Seule une opportunité ouverte peut être perdue.");
        }

        Status = OpportunityStatus.Lost;
        return Result.Success();
    }
}
