using Microsoft.EntityFrameworkCore;
using PricingHub.Api.Contracts;
using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Pricing;
using PricingHub.Domain.Pricing.Calculations;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.Infrastructure.Persistence;
using PricingHub.SharedKernel;

namespace PricingHub.Api.Services;

/// <summary>
/// Orchestration du calcul d'offre — équivalent de
/// <c>engine.calculer_offre</c> côté Python, mais qui lit son <see cref="Model"/>
/// et son <see cref="PriceBook"/> depuis PostgreSQL plutôt que de les
/// recevoir en mémoire, et persiste l'offre calculée plutôt que de
/// renvoyer un objet jetable. Les contrôles avant envoi (C1 à C8, section
/// 6.4) ne sont pas encore branchés : <c>preSendControlsFailed</c> est
/// toujours <c>false</c> pour cette première tranche — à compléter une
/// fois Customer et la flotte exposés par l'API.
/// </summary>
public sealed class QuoteCalculationService
{
    private readonly PricingHubDbContext _db;

    public QuoteCalculationService(PricingHubDbContext db) => _db = db;

    public async Task<Result<QuoteResponse>> CalculateAsync(CalculateQuoteRequest request, CancellationToken cancellationToken)
    {
        var modelCode = ModelCode.Of(request.ModelCode);
        var customerCode = CustomerCode.Of(request.CustomerCode);

        var model = await _db.Models.SingleOrDefaultAsync(m => m.Id == modelCode, cancellationToken);
        if (model is null)
        {
            return Result.Failure<QuoteResponse>($"Modèle {request.ModelCode} introuvable au catalogue.");
        }

        var priceBook = await _db.PriceBooks
            .Include(p => p.MileageBrackets)
            .Include(p => p.DryLeaseGrid)
            .Include(p => p.BudgetPlan)
            .Where(p => p.Status == PriceBookStatus.Published)
            .OrderByDescending(p => p.Id)
            .FirstOrDefaultAsync(cancellationToken);
        if (priceBook is null)
        {
            return Result.Failure<QuoteResponse>("Aucune version du référentiel pricing n'est publiée.");
        }

        var annualMileage = Mileage.FromKilometers(request.AnnualMileageKm);
        var duration = Duration.FromMonths(request.DurationMonths);

        var bracketResult = priceBook.MileageBracketFor(request.AnnualMileageKm);
        if (bracketResult.IsFailure)
        {
            return Result.Failure<QuoteResponse>(bracketResult.Error);
        }

        var gridResult = priceBook.DryLeaseGridEntryFor(modelCode, request.DurationMonths);
        if (gridResult.IsFailure)
        {
            return Result.Failure<QuoteResponse>(gridResult.Error);
        }

        var budgetPlanResult = priceBook.BudgetPlanEntryFor(modelCode, request.AnnualMileageKm);
        if (budgetPlanResult.IsFailure)
        {
            return Result.Failure<QuoteResponse>(budgetPlanResult.Error);
        }

        var quoteResult = Quote.CreateDraft(
            QuoteId.New(), customerCode, modelCode, annualMileage, duration,
            request.Quantity, request.StartDate, campaignCode: null, request.IncludedLines);
        if (quoteResult.IsFailure)
        {
            return Result.Failure<QuoteResponse>(quoteResult.Error);
        }

        var quote = quoteResult.Value;
        quote.AssignManualFleetData(
            request.AgeAtStartYears, Mileage.FromKilometers(request.CumulativeMileageAtStartKm),
            request.HeavyMaintenance8Done, request.HeavyMaintenance16Done);

        if (request.NegotiatedPrices is not null)
        {
            foreach (var (line, amount) in request.NegotiatedPrices)
            {
                quote.NegotiatePrice(line, Money.Eur(amount));
            }
        }

        var ageEnd = request.AgeAtStartYears + duration.Years;
        var mileageEnd = Mileage.FromKilometers(request.CumulativeMileageAtStartKm + request.AnnualMileageKm * duration.Years);

        var vrStart = ResidualValueCalculator.Calculate(
            model, priceBook.Parameters, request.AgeAtStartYears, Mileage.FromKilometers(request.CumulativeMileageAtStartKm),
            request.HeavyMaintenance8Done, request.HeavyMaintenance16Done);
        var vrEnd = ResidualValueCalculator.Calculate(
            model, priceBook.Parameters, ageEnd, mileageEnd, request.HeavyMaintenance8Done, request.HeavyMaintenance16Done);
        var vrAverage = Money.Eur((vrStart.Amount + vrEnd.Amount) / 2m);

        var additionalMileagePrice = AdditionalMileageCalculator.CalculatePerKilometerPrice(
            model, bracketResult.Value, priceBook.Parameters.AdditionalMileageSurcharge);

        var pricedLines = new Dictionary<PriceLine, PricedLine>
        {
            [PriceLine.DryLease] = DryLeaseCalculator.Calculate(
                gridResult.Value, bracketResult.Value, priceBook.Parameters.MaximumDiscount),
            [PriceLine.HeavyMaintenance] = HeavyMaintenanceCalculator.Calculate(
                model, annualMileage, bracketResult.Value, budgetPlanResult.Value, priceBook.Parameters.HeavyMaintenanceMargin),
            [PriceLine.OperatingMaintenance] = OperatingMaintenanceCalculator.Calculate(
                model, annualMileage, bracketResult.Value, budgetPlanResult.Value, priceBook.Parameters.OperatingMaintenanceMargin),
            [PriceLine.Insurance] = InsuranceCalculator.Calculate(model, vrAverage, priceBook.Parameters.InsuranceMargin),
        };

        var calculationResult = quote.ApplyCalculation(
            priceBook.Id, priceBook.Parameters, vrStart, vrEnd, additionalMileagePrice, pricedLines, preSendControlsFailed: false);
        if (calculationResult.IsFailure)
        {
            return Result.Failure<QuoteResponse>(calculationResult.Error);
        }

        _db.Quotes.Add(quote);
        await _db.SaveChangesAsync(cancellationToken);

        return Result.Success(MapToResponse(quote));
    }

    private static QuoteResponse MapToResponse(Quote quote) => new(
        quote.Id.Value,
        quote.CurrentVersionNumber.Value,
        quote.Status,
        quote.PriceBookNumber!.Value.Value,
        quote.Lines.Select(l => new QuoteLineResponse(
            l.Line, l.Cost.Amount, l.CatalogPrice.Amount, l.Floor.Amount, l.NegotiatedPrice?.Amount, l.RetainedPrice.Amount, l.Status)).ToList(),
        quote.ResidualValueAtStart!.Value.Amount,
        quote.ResidualValueAtEnd!.Value.Amount,
        quote.MonthlyValueLoss!.Value.Amount,
        quote.AdditionalMileagePrice!.Value,
        quote.TotalCatalogPerUnitMonthly!.Value.Amount,
        quote.TotalRetainedPerUnitMonthly!.Value.Amount,
        quote.TotalRetainedMonthly!.Value.Amount,
        quote.TotalRetainedContract!.Value.Amount,
        quote.GlobalDiscount!.Value,
        quote.MonthlyReferenceCost!.Value.Amount,
        quote.ValidationLevel,
        quote.ValidationLevelReasons.ToList());
}
