using PricingHub.Domain.Common;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Pricing.CampaignAggregate;

/// <summary>
/// Une campagne commerciale (ex. AMS, Renewal Q1) — n'existait dans le
/// prototype Python que comme un booléen (<c>ConfigurationOffre.campagne</c>)
/// déclenchant le contrôle C1 (durée ≤ durée maximale de campagne,
/// section 6.4). Devient ici un agrégat à part entière : plusieurs
/// campagnes actives en parallèle peuvent avoir des durées maximales et
/// des périodes différentes, et une <c>Quote</c> doit pouvoir dire
/// *laquelle* elle sert, pas seulement qu'elle sert "une campagne".
///
/// <see cref="MaxDurationMonths"/> est propre à la campagne : si absent,
/// le contrôle C1 retombe sur <c>PricingParameters.MaxCampaignDurationMonths</c>
/// (le plafond global).
/// </summary>
public sealed class Campaign : AggregateRoot<CampaignCode>
{
    public string Name { get; private set; } = string.Empty;
    public int? MaxDurationMonths { get; private set; }
    public DateOnly StartDate { get; private set; }
    public DateOnly? EndDate { get; private set; }
    public bool IsActive { get; private set; } = true;

#pragma warning disable CS8618
    private Campaign()
    {
    }
#pragma warning restore CS8618

    private Campaign(CampaignCode code, string name, int? maxDurationMonths, DateOnly startDate, DateOnly? endDate)
        : base(code)
    {
        Name = name;
        MaxDurationMonths = maxDurationMonths;
        StartDate = startDate;
        EndDate = endDate;
    }

    public static Result<Campaign> Create(
        CampaignCode code, string name, DateOnly startDate, DateOnly? endDate = null, int? maxDurationMonths = null)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            return Result.Failure<Campaign>("Le nom de la campagne ne peut pas être vide.");
        }

        if (endDate is { } end && end < startDate)
        {
            return Result.Failure<Campaign>("La date de fin ne peut pas précéder la date de début.");
        }

        if (maxDurationMonths is <= 0)
        {
            return Result.Failure<Campaign>("La durée maximale de campagne doit être strictement positive.");
        }

        return Result.Success(new Campaign(code, name, maxDurationMonths, startDate, endDate));
    }

    /// <summary>La campagne est-elle ouverte à cette date ? Une campagne
    /// désactivée (<see cref="IsActive"/> = false) ne couvre plus rien,
    /// même dans sa période.</summary>
    public bool Covers(DateOnly date) =>
        IsActive && date >= StartDate && (EndDate is null || date <= EndDate);

    public void Close() => IsActive = false;
}
