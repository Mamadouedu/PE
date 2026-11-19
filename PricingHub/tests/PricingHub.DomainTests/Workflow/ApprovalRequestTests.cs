using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.Domain.Workflow.ApprovalRequestAggregate;
using PricingHub.Domain.Workflow.DelegationAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.DomainTests.Workflow;

/// <summary>Porté depuis <c>tests/test_derogation.py</c> — section 7, M4.</summary>
public class ApprovalRequestTests
{
    private static Result<ApprovalRequest> CreateRequest(int validationLevel, string? validatorEmail, string justification = "négociation")
    {
        var delegations = validatorEmail is null
            ? Array.Empty<Delegation>()
            : new[] { Delegation.Create(ValidationLevel.Of(validationLevel), "Validateur test", validatorEmail).Value };

        return ApprovalRequest.Request(
            ApprovalRequestId.Of(1),
            QuoteId.New(),
            QuoteVersionNumber.First,
            PriceBookNumber.Of(1),
            CustomerCode.Of("CLIENTOK"),
            ModelCode.Of("VECTRON"),
            validationLevel,
            Money.Eur(5_000m),
            delegations,
            "kam@akiem.com",
            justification);
    }

    [Fact]
    public void RefuseUneDerogationPourUneOffreDansLesRegles()
    {
        var result = CreateRequest(validationLevel: 0, validatorEmail: null);

        Assert.True(result.IsFailure);
    }

    [Fact]
    public void CreeUneDemandeAvecLeNiveauEtLeValidateurCalcules()
    {
        var result = CreateRequest(validationLevel: 2, validatorEmail: "head@akiem.com", justification: "remise fidélité");

        Assert.True(result.IsSuccess);
        var request = result.Value;
        Assert.Equal(ApprovalStatus.Pending, request.Status);
        Assert.Equal(2, request.ValidationLevel);
        Assert.Equal("head@akiem.com", request.ValidatorEmail);
        Assert.Equal("kam@akiem.com", request.RequestedBy);
        Assert.Equal("remise fidélité", request.Justification);
        Assert.Null(request.DecidedAt);
    }

    [Fact]
    public void SansDelegationConfiguree_ValidatorEmailResteNull()
    {
        var result = ApprovalRequest.Request(
            ApprovalRequestId.Of(1), QuoteId.New(), QuoteVersionNumber.First, PriceBookNumber.Of(1),
            CustomerCode.Of("CLIENTOK"), ModelCode.Of("VECTRON"), validationLevel: 1, Money.Eur(5_000m),
            delegations: Array.Empty<Delegation>(), requestedBy: "kam@akiem.com", justification: "sans délégation configurée");

        Assert.True(result.IsSuccess);
        Assert.Null(result.Value.ValidatorEmail);
    }

    [Fact]
    public void ExigeUneJustification()
    {
        var result = CreateRequest(validationLevel: 1, validatorEmail: "manager@akiem.com", justification: "");

        Assert.True(result.IsFailure);
    }

    [Fact]
    public void ApprobationChangeLeStatutEtTraceLeDecideur()
    {
        var request = CreateRequest(validationLevel: 1, validatorEmail: "manager@akiem.com").Value;

        var decision = request.Decide(ApprovalStatus.Approved, "manager@akiem.com", "ok pour ce coup-ci");

        Assert.True(decision.IsSuccess);
        Assert.Equal(ApprovalStatus.Approved, request.Status);
        Assert.Equal("manager@akiem.com", request.DecidedBy);
        Assert.Equal("ok pour ce coup-ci", request.DecisionComment);
        Assert.NotNull(request.DecidedAt);
    }

    [Fact]
    public void RejetChangeLeStatut()
    {
        var request = CreateRequest(validationLevel: 1, validatorEmail: "manager@akiem.com").Value;

        var decision = request.Decide(ApprovalStatus.Rejected, "manager@akiem.com", null);

        Assert.True(decision.IsSuccess);
        Assert.Equal(ApprovalStatus.Rejected, request.Status);
    }

    [Fact]
    public void UneDerogationDejaDecideeNePeutPasEtreRedecidee()
    {
        var request = CreateRequest(validationLevel: 1, validatorEmail: "manager@akiem.com").Value;
        request.Decide(ApprovalStatus.Approved, "manager@akiem.com", null);

        var secondeDecision = request.Decide(ApprovalStatus.Rejected, "manager@akiem.com", null);

        Assert.True(secondeDecision.IsFailure);
        Assert.Equal(ApprovalStatus.Approved, request.Status);
    }

    [Fact]
    public void LeNiveauLePlusEleveDetermineLeValidateur()
    {
        // Niveau 3 : prix très négociés, sous le coût de référence.
        var result = CreateRequest(validationLevel: 3, validatorEmail: "direction@akiem.com", justification: "cas extrême");

        Assert.True(result.IsSuccess);
        Assert.Equal(3, result.Value.ValidationLevel);
        Assert.Equal("direction@akiem.com", result.Value.ValidatorEmail);
    }
}
