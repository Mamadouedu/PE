namespace PricingHub.Domain.Common;

/// <summary>Racine d'agrégat : la seule porte d'entrée pour modifier le
/// graphe d'entités qu'elle protège (ex. <c>Quote</c> protège ses
/// <c>QuoteLine</c>), et le point où s'accumulent les événements de domaine
/// avant publication (après la persistance, par l'Infrastructure).</summary>
public abstract class AggregateRoot<TId> : Entity<TId>
    where TId : notnull
{
    private readonly List<DomainEvent> _domainEvents = new();

    public IReadOnlyCollection<DomainEvent> DomainEvents => _domainEvents.AsReadOnly();

    protected AggregateRoot(TId id) : base(id)
    {
    }

    protected AggregateRoot()
    {
    }

    protected void Raise(DomainEvent domainEvent) => _domainEvents.Add(domainEvent);

    public void ClearDomainEvents() => _domainEvents.Clear();
}
