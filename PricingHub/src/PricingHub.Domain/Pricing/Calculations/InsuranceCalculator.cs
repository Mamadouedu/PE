using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Pricing.Calculations;

/// <summary>
/// Prime d'assurance = valeur résiduelle moyenne du contrat × taux annuel
/// ÷ 12 ; catalogue = prime × (1 + marge assurance), plancher = la prime
/// elle-même (jamais vendue à perte) — section 6.1. Porté depuis le bloc
/// Assurance de <c>engine.calculer_offre</c>.
/// </summary>
public static class InsuranceCalculator
{
    public static PricedLine Calculate(Model model, Money contractAverageResidualValue, Percentage margin)
    {
        var premium = contractAverageResidualValue.Multiply(model.AnnualInsuranceRate).Multiply(1m / 12m);
        var catalogPrice = premium + premium * margin;
        return new PricedLine(PriceLine.Insurance, premium, catalogPrice, premium);
    }
}
