namespace PricingHub.SharedKernel;

/// <summary>
/// Succès ou échec explicite, sans exception : une configuration sans
/// tranche de km correspondante, ou une série inconnue, sont des résultats
/// attendus du calcul de prix (la configuration vient du KAM), pas des bugs
/// — <see cref="Result{TValue}"/> les fait apparaître dans la signature de
/// la méthode plutôt que de forcer l'appelant à savoir quelles exceptions
/// attraper.
/// </summary>
public class Result
{
    public bool IsSuccess { get; }
    public bool IsFailure => !IsSuccess;
    public string Error { get; }

    protected Result(bool isSuccess, string error)
    {
        if (isSuccess && error != string.Empty)
        {
            throw new InvalidOperationException("Un résultat réussi ne porte pas de message d'erreur.");
        }

        if (!isSuccess && error == string.Empty)
        {
            throw new InvalidOperationException("Un résultat en échec doit porter un message d'erreur.");
        }

        IsSuccess = isSuccess;
        Error = error;
    }

    public static Result Success() => new(true, string.Empty);
    public static Result Failure(string error) => new(false, error);

    public static Result<TValue> Success<TValue>(TValue value) => new(value, true, string.Empty);
    public static Result<TValue> Failure<TValue>(string error) => new(default!, false, error);
}

public class Result<TValue> : Result
{
    private readonly TValue _value;

    protected internal Result(TValue value, bool isSuccess, string error) : base(isSuccess, error)
    {
        _value = value;
    }

    public TValue Value => IsSuccess
        ? _value
        : throw new InvalidOperationException(
            "La valeur d'un résultat en échec ne peut pas être lue — vérifiez IsSuccess avant.");

    public static implicit operator Result<TValue>(TValue value) => Success(value);
}
