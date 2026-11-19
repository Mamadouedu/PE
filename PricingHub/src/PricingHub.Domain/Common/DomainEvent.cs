namespace PricingHub.Domain.Common;

/// <summary>Un fait métier déjà survenu (ex. <c>OffreCalculee</c>,
/// <c>DerogationApprouvee</c>) — publié par un <see cref="AggregateRoot{TId}"/>
/// pour que d'autres parties du système réagissent (écriture Pipedrive,
/// notification Teams) sans que l'agrégat les connaisse.</summary>
public abstract record DomainEvent
{
    public DateTimeOffset OccurredOn { get; } = DateTimeOffset.UtcNow;
}
