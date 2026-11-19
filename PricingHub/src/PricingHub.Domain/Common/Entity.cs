namespace PricingHub.Domain.Common;

/// <summary>Base pour toute entité avec identité propre : deux entités sont
/// égales si elles ont le même <typeparamref name="TId"/>, jamais par la
/// valeur de leurs autres champs.</summary>
public abstract class Entity<TId> : IEquatable<Entity<TId>>
    where TId : notnull
{
    public TId Id { get; protected set; }

    protected Entity(TId id) => Id = id;

#pragma warning disable CS8618 // requis par EF Core (matérialisation sans passer par le constructeur public)
    protected Entity()
    {
    }
#pragma warning restore CS8618

    public bool Equals(Entity<TId>? other)
    {
        if (other is null) return false;
        if (ReferenceEquals(this, other)) return true;
        if (GetType() != other.GetType()) return false;
        return Id.Equals(other.Id);
    }

    public override bool Equals(object? obj) => Equals(obj as Entity<TId>);

    public override int GetHashCode() => HashCode.Combine(GetType(), Id);

    public static bool operator ==(Entity<TId>? left, Entity<TId>? right) =>
        left is null ? right is null : left.Equals(right);

    public static bool operator !=(Entity<TId>? left, Entity<TId>? right) => !(left == right);
}
