namespace PricingHub.Api.Contracts;

public sealed record CreateCustomerRequest(
    string Code, string Name, int CreditRating, string Segment, decimal CashDeposit, bool PaysInAdvance);

public sealed record CustomerResponse(
    string Code, string Name, int CreditRating, string Segment, decimal CashDeposit, bool PaysInAdvance, bool HasPaymentGuarantee);
