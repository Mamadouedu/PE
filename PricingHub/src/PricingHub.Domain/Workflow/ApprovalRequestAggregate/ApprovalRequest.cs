using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Common;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.Domain.Workflow.DelegationAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Workflow.ApprovalRequestAggregate;

/// <summary>
/// Le circuit de dérogation (M4, section 7 du cahier des charges) : le
/// niveau de validation est calculé par le moteur de prix, jamais choisi
/// par le KAM (M4-01) ; cet agrégat encapsule ce qui l'entoure — la
/// demande, avec justification obligatoire (M4-02), la décision, et le
/// registre central (M4-05). Équivalent du modèle Python <c>Derogation</c>.
///
/// Gèle la configuration exacte qui l'a déclenchée au moment de la
/// demande — y compris <see cref="QuoteVersion"/>, le numéro de version
/// précis de l'offre (pas seulement son identité) : une approbation reste
/// liée à cette version-là, jamais à « la dernière version » de l'offre.
/// Puisqu'éditer une <c>Quote</c> après calcul ouvre toujours une nouvelle
/// version (voir <c>Quote.EnsureEditableVersion</c>), toute modification
/// du KAM rend mécaniquement caduque l'approbation de l'ancienne version
/// (M4-04) sans qu'il soit besoin de comparer des champs un à un.
/// </summary>
public sealed class ApprovalRequest : AggregateRoot<ApprovalRequestId>
{
    public ApprovalStatus Status { get; private set; }
    public int ValidationLevel { get; private set; }
    public string RequestedBy { get; private set; } = string.Empty;
    public string Justification { get; private set; } = string.Empty;

    public QuoteId QuoteId { get; private set; }
    public QuoteVersionNumber QuoteVersion { get; private set; }
    public PriceBookNumber PriceBookNumber { get; private set; }
    public CustomerCode CustomerCode { get; private set; }
    public ModelCode ModelCode { get; private set; }
    public Money MonthlyRetainedAmount { get; private set; }
    public string? ValidatorEmail { get; private set; }

    public DateTimeOffset RequestedAt { get; private set; }
    public DateTimeOffset? DecidedAt { get; private set; }
    public string? DecidedBy { get; private set; }
    public string? DecisionComment { get; private set; }

#pragma warning disable CS8618
    private ApprovalRequest()
    {
    }
#pragma warning restore CS8618

    private ApprovalRequest(
        ApprovalRequestId id,
        QuoteId quoteId,
        QuoteVersionNumber quoteVersion,
        PriceBookNumber priceBookNumber,
        CustomerCode customerCode,
        ModelCode modelCode,
        int validationLevel,
        Money monthlyRetainedAmount,
        string? validatorEmail,
        string requestedBy,
        string justification)
        : base(id)
    {
        QuoteId = quoteId;
        QuoteVersion = quoteVersion;
        PriceBookNumber = priceBookNumber;
        CustomerCode = customerCode;
        ModelCode = modelCode;
        ValidationLevel = validationLevel;
        MonthlyRetainedAmount = monthlyRetainedAmount;
        ValidatorEmail = validatorEmail;
        RequestedBy = requestedBy;
        Justification = justification;
        Status = ApprovalStatus.Pending;
        RequestedAt = DateTimeOffset.UtcNow;
    }

    /// <summary>Crée la demande et résout le validateur délégué pour le
    /// niveau calculé (<paramref name="delegations"/> — la table
    /// Délégation, section 8.3). Échoue si l'offre est déjà dans les
    /// règles (niveau 0 — équivalent de <c>DerogationNonNecessaire</c>) ou
    /// si la justification est absente (M4-02). L'absence de délégation
    /// configurée pour le niveau requis n'empêche pas la demande (anomalie
    /// de référentiel à corriger côté administration, pas une raison de
    /// bloquer le KAM) : <see cref="ValidatorEmail"/> reste alors
    /// <c>null</c>.</summary>
    public static Result<ApprovalRequest> Request(
        ApprovalRequestId id,
        QuoteId quoteId,
        QuoteVersionNumber quoteVersion,
        PriceBookNumber priceBookNumber,
        CustomerCode customerCode,
        ModelCode modelCode,
        int validationLevel,
        Money monthlyRetainedAmount,
        IReadOnlyCollection<Delegation> delegations,
        string requestedBy,
        string justification)
    {
        if (validationLevel <= 0)
        {
            return Result.Failure<ApprovalRequest>(
                "L'offre est dans les règles (niveau 0) : aucune dérogation n'est nécessaire.");
        }

        if (string.IsNullOrWhiteSpace(justification))
        {
            return Result.Failure<ApprovalRequest>("La justification est obligatoire pour demander une dérogation.");
        }

        if (string.IsNullOrWhiteSpace(requestedBy))
        {
            return Result.Failure<ApprovalRequest>("Le demandeur est obligatoire.");
        }

        var validator = DelegationLookup.ValidatorFor(delegations, validationLevel);

        var request = new ApprovalRequest(
            id, quoteId, quoteVersion, priceBookNumber, customerCode, modelCode, validationLevel, monthlyRetainedAmount,
            validator?.Email, requestedBy, justification);

        request.Raise(new ApprovalRequested(id, validationLevel, validator?.Email));
        return Result.Success(request);
    }

    /// <summary>Enregistre la décision du validateur. Échoue si la
    /// dérogation a déjà été décidée, ou si <paramref name="decision"/>
    /// n'est pas une décision valide (seules <c>Approved</c> et
    /// <c>Rejected</c> le sont — équivalent de <c>DecisionInvalide</c>).</summary>
    public Result Decide(ApprovalStatus decision, string decidedBy, string? comment)
    {
        if (Status != ApprovalStatus.Pending)
        {
            return Result.Failure("Cette dérogation a déjà été décidée.");
        }

        if (decision is not (ApprovalStatus.Approved or ApprovalStatus.Rejected))
        {
            return Result.Failure("Décision invalide : seules Approved et Rejected sont des décisions valides.");
        }

        Status = decision;
        DecidedBy = decidedBy;
        DecisionComment = comment;
        DecidedAt = DateTimeOffset.UtcNow;
        Raise(new ApprovalDecided(Id, decision, decidedBy));
        return Result.Success();
    }
}
