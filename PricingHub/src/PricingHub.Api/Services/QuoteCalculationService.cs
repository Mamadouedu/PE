using Microsoft.EntityFrameworkCore;
using PricingHub.Api.Contracts;
using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Pricing;
using PricingHub.Domain.Pricing.CampaignAggregate;
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
/// renvoyer un objet jetable. Les 8 contrôles avant envoi (section 6.4)
/// sont évalués ici via <see cref="PreSendControlsEvaluator"/> — hormis
/// C8 (flotte), qui reste toujours "hors contrôle" tant qu'il n'y a pas
/// de <c>Locomotive</c> dans ce domaine.
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

        // Le client n'est pas requis pour calculer un prix (les contrôles C3/C5
        // tolèrent son absence en échouant explicitement, comme côté Python),
        // mais on le cherche pour que ces deux contrôles aient un sens.
        var customer = await _db.Customers.SingleOrDefaultAsync(c => c.Id == customerCode, cancellationToken);

        CampaignCode? campaignCode = null;
        if (!string.IsNullOrWhiteSpace(request.CampaignCode))
        {
            campaignCode = CampaignCode.Of(request.CampaignCode);
            var campaignExists = await _db.Campaigns.AnyAsync(c => c.Id == campaignCode, cancellationToken);
            if (!campaignExists)
            {
                return Result.Failure<QuoteResponse>($"Campagne {request.CampaignCode} introuvable.");
            }
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
            request.Quantity, request.StartDate, campaignCode, request.IncludedLines);
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
        var monthlyValueLoss = (vrStart - vrEnd) * (1m / request.DurationMonths);

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

        // Les mêmes QuoteLine que ApplyCalculation construira en interne, mais
        // construites ici en amont : C6/C7 ont besoin de leur statut (BelowFloor,
        // Excluded) et du prix retenu, qui n'existent qu'une fois la décision
        // commerciale (brique incluse, prix négocié) combinée au calcul.
        var includedLines = request.IncludedLines is null
            ? new HashSet<PriceLine> { PriceLine.DryLease, PriceLine.HeavyMaintenance, PriceLine.OperatingMaintenance, PriceLine.Insurance }
            : new HashSet<PriceLine>(request.IncludedLines);

        var lines = pricedLines.ToDictionary(
            kv => kv.Key,
            kv => includedLines.Contains(kv.Key)
                ? QuoteLine.Included(kv.Value, request.NegotiatedPrices?.TryGetValue(kv.Key, out var amount) == true ? Money.Eur(amount) : null)
                : QuoteLine.Excluded(kv.Value));

        var controls = PreSendControlsEvaluator.Evaluate(
            quote.IsCampaign, request.DurationMonths, request.Quantity, customerCode, customer,
            includedLines, lines, monthlyValueLoss, priceBook.Parameters);
        var preSendControlsFailed = controls.Any(c => !c.Ok);

        var calculationResult = quote.ApplyCalculation(
            priceBook.Id, priceBook.Parameters, vrStart, vrEnd, additionalMileagePrice, pricedLines, preSendControlsFailed);
        if (calculationResult.IsFailure)
        {
            return Result.Failure<QuoteResponse>(calculationResult.Error);
        }

        _db.Quotes.Add(quote);
        await _db.SaveChangesAsync(cancellationToken);

        return Result.Success(MapToResponse(quote, controls));
    }

    private static QuoteResponse MapToResponse(Quote quote, IReadOnlyList<ControlResultResponse> controls) => new(
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
        quote.ValidationLevelReasons.ToList(),
        controls,
        controls.All(c => c.Ok));
}
