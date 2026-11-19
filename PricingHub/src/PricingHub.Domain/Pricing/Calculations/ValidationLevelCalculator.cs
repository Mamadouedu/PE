using PricingHub.SharedKernel;

namespace PricingHub.Domain.Pricing.Calculations;

/// <summary>
/// Niveau de validation d'une offre (0 à 3) — section 6.3 du cahier des
/// charges : jamais choisi par le KAM, toujours déduit des faits. Porté
/// terme à terme depuis la fin de <c>engine.calculer_offre</c> : chaque
/// condition ne peut qu'augmenter le niveau ("most severe wins"), jamais le
/// réduire, et chaque déclenchement laisse un motif explicable.
/// </summary>
public static class ValidationLevelCalculator
{
    public static (int Level, IReadOnlyList<string> Reasons) Calculate(
        decimal globalDiscount,
        Percentage kamDiscountThreshold,
        bool anyLineBelowFloor,
        bool anyPreSendControlFailed,
        Money totalRetainedPerUnitMonthly,
        Money monthlyReferenceCost)
    {
        var level = 0;
        var reasons = new List<string>();

        if (globalDiscount > kamDiscountThreshold.Value)
        {
            level = Math.Max(level, 1);
            reasons.Add($"Remise globale {globalDiscount:P1} > seuil KAM {kamDiscountThreshold}");
        }

        if (anyLineBelowFloor)
        {
            level = Math.Max(level, 2);
            reasons.Add("Au moins une brique sous son plancher");
        }

        if (anyPreSendControlFailed)
        {
            level = Math.Max(level, 2);
            reasons.Add("Contrôle(s) avant envoi en échec");
        }

        if (totalRetainedPerUnitMonthly < monthlyReferenceCost)
        {
            level = Math.Max(level, 3);
            reasons.Add($"Prix retenu {totalRetainedPerUnitMonthly} < coût de référence {monthlyReferenceCost}");
        }

        if (reasons.Count == 0)
        {
            reasons.Add("Dans les règles : validation KAM (niveau 0)");
        }

        return (level, reasons);
    }
}
