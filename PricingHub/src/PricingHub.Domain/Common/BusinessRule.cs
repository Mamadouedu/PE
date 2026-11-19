namespace PricingHub.Domain.Common;

/// <summary>Une règle métier nommée et testable isolément (ex.
/// <c>KilometrageSuppRequiertUneTranche</c>), plutôt qu'une condition noyée
/// dans une méthode — le message d'erreur et la condition de violation
/// vivent au même endroit.</summary>
public interface IBusinessRule
{
    bool IsBroken();
    string Message { get; }
}

public sealed class BusinessRuleValidationException : Exception
{
    public IBusinessRule BrokenRule { get; }

    public BusinessRuleValidationException(IBusinessRule brokenRule)
        : base(brokenRule.Message)
    {
        BrokenRule = brokenRule;
    }
}

public static class BusinessRuleChecker
{
    /// <summary>À utiliser dans les invariants internes d'un agrégat (ne
    /// devraient jamais se produire si le code appelant est correct). Pour
    /// une erreur de saisie attendue côté KAM, préférer <c>Result.Failure</c>
    /// — voir <see cref="PricingHub.SharedKernel.Result"/>.</summary>
    public static void CheckRule(IBusinessRule rule)
    {
        if (rule.IsBroken())
        {
            throw new BusinessRuleValidationException(rule);
        }
    }
}
