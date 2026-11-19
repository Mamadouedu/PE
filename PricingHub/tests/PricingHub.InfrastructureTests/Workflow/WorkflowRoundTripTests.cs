using Microsoft.EntityFrameworkCore;
using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.Domain.Workflow.ApprovalRequestAggregate;
using PricingHub.Domain.Workflow.DelegationAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.InfrastructureTests.Workflow;

public class WorkflowRoundTripTests
{
    [Fact]
    public async Task UneDelegation_SurvitAUnAllerRetourEnBase()
    {
        var level = ValidationLevel.Of(2);

        await using (var write = DatabaseFixture.CreateContext())
        {
            var delegation = Delegation.Create(level, "Head of Pricing", "head@akiem.com", "head.backup@akiem.com").Value;
            write.Delegations.Add(delegation);
            await write.SaveChangesAsync();
        }

        await using var read = DatabaseFixture.CreateContext();
        var reloaded = await read.Delegations.SingleAsync(d => d.Id == level);

        Assert.Equal("Head of Pricing", reloaded.Name);
        Assert.Equal("head@akiem.com", reloaded.Email);
        Assert.Equal("head.backup@akiem.com", reloaded.AlternateEmail);

        read.Delegations.Remove(reloaded);
        await read.SaveChangesAsync();
    }

    [Fact]
    public async Task UneDemandeDeDerogationApprouvee_SurvitAUnAllerRetourEnBase()
    {
        var id = ApprovalRequestId.Of(Random.Shared.Next(100_000, 999_999));
        var quoteId = QuoteId.New();
        var modelCode = ModelCode.Of($"TEST_MODEL_{Guid.NewGuid():N}");
        var customerCode = CustomerCode.Of($"TEST_CUST_{Guid.NewGuid():N}");

        await using (var write = DatabaseFixture.CreateContext())
        {
            var delegations = new[] { Delegation.Create(ValidationLevel.Of(2), "Head of Pricing", "head@akiem.com").Value };

            var request = ApprovalRequest.Request(
                id, quoteId, QuoteVersionNumber.First, PriceBookNumber.Of(1), customerCode, modelCode,
                validationLevel: 2, Money.Eur(27_901.35m), delegations, "kam@akiem.com", "remise fidélité").Value;

            Assert.True(request.Decide(ApprovalStatus.Approved, "head@akiem.com", "ok pour ce coup-ci").IsSuccess);

            write.ApprovalRequests.Add(request);
            await write.SaveChangesAsync();
        }

        await using var read = DatabaseFixture.CreateContext();
        var reloaded = await read.ApprovalRequests.SingleAsync(a => a.Id == id);

        Assert.Equal(ApprovalStatus.Approved, reloaded.Status);
        Assert.Equal(2, reloaded.ValidationLevel);
        Assert.Equal("head@akiem.com", reloaded.ValidatorEmail);
        Assert.Equal("head@akiem.com", reloaded.DecidedBy);
        Assert.Equal("ok pour ce coup-ci", reloaded.DecisionComment);
        Assert.Equal(quoteId, reloaded.QuoteId);
        Assert.Equal(1, reloaded.QuoteVersion.Value);
        Assert.Equal(27_901.35m, reloaded.MonthlyRetainedAmount.Amount);
        Assert.Equal(Currency.Eur, reloaded.MonthlyRetainedAmount.Currency);
        Assert.NotNull(reloaded.DecidedAt);

        read.ApprovalRequests.Remove(reloaded);
        await read.SaveChangesAsync();
    }
}
