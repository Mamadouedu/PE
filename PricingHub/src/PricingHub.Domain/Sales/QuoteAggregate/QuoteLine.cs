using PricingHub.Domain.Pricing;
using PricingHub.Domain.Pricing.Calculations;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Sales.QuoteAggregate;

/// <summary>
/// Une brique chiffrée pour une offre donnée — la combinaison d'un
/// <see cref="PricedLine"/> (calculé, sans connaître la décision
/// commerciale) avec le choix du KAM : brique incluse ou non, prix négocié
/// ou non. Équivalent du modèle Python <c>DetailBrique</c> et de la
/// fonction <c>engine._prix_retenu</c>.
/// </summary>
public sealed class QuoteLine
{
    public PriceLine Line { get; }
    public Money Cost { get; }
    public Money CatalogPrice { get; }
    public Money Floor { get; }
    public Money? NegotiatedPrice { get; }
    public Money RetainedPrice { get; }
    public QuoteLineStatus Status { get; }

    private QuoteLine(
        PriceLine line, Money cost, Money catalogPrice, Money floor, Money? negotiatedPrice, Money retainedPrice, QuoteLineStatus status)
    {
        Line = line;
        Cost = cost;
        CatalogPrice = catalogPrice;
        Floor = floor;
        NegotiatedPrice = negotiatedPrice;
        RetainedPrice = retainedPrice;
        Status = status;
    }

    public static QuoteLine Excluded(PricedLine pricedLine) =>
        new(pricedLine.Line, pricedLine.Cost, pricedLine.CatalogPrice, pricedLine.Floor,
            negotiatedPrice: null, retainedPrice: Money.Zero(pricedLine.CatalogPrice.Currency), QuoteLineStatus.Excluded);

    public static QuoteLine Included(PricedLine pricedLine, Money? negotiatedPrice)
    {
        var retained = negotiatedPrice ?? pricedLine.CatalogPrice;

        QuoteLineStatus status;
        if (retained < pricedLine.Floor)
        {
            status = QuoteLineStatus.BelowFloor;
        }
        else if (negotiatedPrice is { } price && price < pricedLine.CatalogPrice)
        {
            status = QuoteLineStatus.Alert;
        }
        else
        {
            status = QuoteLineStatus.Ok;
        }

        return new QuoteLine(pricedLine.Line, pricedLine.Cost, pricedLine.CatalogPrice, pricedLine.Floor, negotiatedPrice, retained, status);
    }
}
