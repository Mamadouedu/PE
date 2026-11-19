using PricingHub.Domain.Workflow.ApprovalRequestAggregate;

namespace PricingHub.Api.Contracts;

/// <summary>Demande une dérogation pour la version COURANTE de l'offre
/// (équivalent de <c>demander_derogation</c> côté Python, section 7, M4-02).</summary>
public sealed record RequestApprovalRequest(Guid QuoteId, string RequestedBy, string Justification);

public sealed record DecideApprovalRequest(ApprovalStatus Decision, string DecidedBy, string? Comment);

public sealed record ApprovalRequestResponse(
    int Number,
    ApprovalStatus Status,
    int ValidationLevel,
    string RequestedBy,
    string Justification,
    Guid QuoteId,
    int QuoteVersion,
    int PriceBookNumber,
    string CustomerCode,
    string ModelCode,
    decimal MonthlyRetainedAmount,
    string? ValidatorEmail,
    DateTimeOffset RequestedAt,
    DateTimeOffset? DecidedAt,
    string? DecidedBy,
    string? DecisionComment);
