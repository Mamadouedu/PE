using PricingHub.Domain.Common;

namespace PricingHub.Domain.Sales.QuoteAggregate;

public sealed record QuoteCalculated(QuoteId QuoteId, QuoteVersionNumber Version, int ValidationLevel) : DomainEvent;

public sealed record QuoteSubmittedForApproval(QuoteId QuoteId, QuoteVersionNumber Version, int ValidationLevel) : DomainEvent;

/// <summary>Déclenche l'écriture retour Pipedrive (M3-06) : les KAM ne
/// remettent pas systématiquement à jour le deal une fois le prix validé.</summary>
public sealed record QuoteApproved(QuoteId QuoteId, QuoteVersionNumber Version, string ApprovedBy) : DomainEvent;

public sealed record QuoteRejected(QuoteId QuoteId, QuoteVersionNumber Version, string Reason) : DomainEvent;
