using PricingHub.Domain.Common;

namespace PricingHub.Domain.Workflow.ApprovalRequestAggregate;

/// <summary>Déclenche l'envoi au bon validateur (M4-03) — Power Automate et
/// Teams restent responsables du rappel et de l'escalade après délai, hors
/// périmètre du domaine.</summary>
public sealed record ApprovalRequested(ApprovalRequestId ApprovalRequestId, int ValidationLevel, string? ValidatorEmail) : DomainEvent;

public sealed record ApprovalDecided(ApprovalRequestId ApprovalRequestId, ApprovalStatus Decision, string DecidedBy) : DomainEvent;
