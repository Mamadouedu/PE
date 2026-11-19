using PricingHub.Domain.Workflow.DelegationAggregate;

namespace PricingHub.DomainTests.Workflow;

public class DelegationTests
{
    [Fact]
    public void ExigeUnEmailValide()
    {
        var result = Delegation.Create(ValidationLevel.Of(1), "Manager", "pas-un-email");

        Assert.True(result.IsFailure);
    }

    [Fact]
    public void ValidatorFor_ResoutLeValidateurDuNiveauDemande()
    {
        var delegations = new[]
        {
            Delegation.Create(ValidationLevel.Of(1), "Manager", "manager@akiem.com").Value,
            Delegation.Create(ValidationLevel.Of(2), "Head of Pricing", "head@akiem.com").Value,
            Delegation.Create(ValidationLevel.Of(3), "Direction", "direction@akiem.com").Value,
        };

        Assert.Equal("head@akiem.com", DelegationLookup.ValidatorFor(delegations, 2)!.Email);
    }

    [Fact]
    public void ValidatorFor_RenvoieNullSiAucuneDelegationPourCeNiveau()
    {
        var delegations = new[] { Delegation.Create(ValidationLevel.Of(1), "Manager", "manager@akiem.com").Value };

        Assert.Null(DelegationLookup.ValidatorFor(delegations, 2));
    }

    [Fact]
    public void ValidatorFor_RenvoieNullPourLeNiveau0()
    {
        var delegations = new[] { Delegation.Create(ValidationLevel.Of(1), "Manager", "manager@akiem.com").Value };

        Assert.Null(DelegationLookup.ValidatorFor(delegations, 0));
    }
}
