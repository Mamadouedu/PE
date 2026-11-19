using Microsoft.EntityFrameworkCore;
using PricingHub.Api.Contracts;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Infrastructure.Persistence;
using PricingHub.SharedKernel;

namespace PricingHub.Api.Endpoints;

public static class CustomerEndpoints
{
    public static void MapCustomerEndpoints(this WebApplication app)
    {
        app.MapGet("/api/customers", async (PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            var customers = await db.Customers.ToListAsync(cancellationToken);
            return Results.Ok(customers.Select(ToResponse).ToList());
        })
        .WithName("ListCustomers")
        .WithOpenApi();

        app.MapGet("/api/customers/{code}", async (string code, PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            var customerCode = CustomerCode.Of(code);
            var customer = await db.Customers.SingleOrDefaultAsync(c => c.Id == customerCode, cancellationToken);
            return customer is null ? Results.NotFound() : Results.Ok(ToResponse(customer));
        })
        .WithName("GetCustomer")
        .WithOpenApi();

        app.MapPost("/api/customers", async (
            CreateCustomerRequest request, PricingHubDbContext db, CancellationToken cancellationToken) =>
        {
            var customerCode = CustomerCode.Of(request.Code);
            if (await db.Customers.AnyAsync(c => c.Id == customerCode, cancellationToken))
            {
                return Results.Conflict(new { error = $"Le client {request.Code} existe déjà." });
            }

            var result = Customer.Create(
                customerCode, request.Name, request.CreditRating, request.Segment,
                Money.Eur(request.CashDeposit), request.PaysInAdvance);
            if (result.IsFailure)
            {
                return Results.UnprocessableEntity(new { error = result.Error });
            }

            db.Customers.Add(result.Value);
            await db.SaveChangesAsync(cancellationToken);
            return Results.Created($"/api/customers/{request.Code}", ToResponse(result.Value));
        })
        .WithName("CreateCustomer")
        .WithOpenApi();
    }

    private static CustomerResponse ToResponse(Customer customer) => new(
        customer.Id.Value, customer.Name, customer.CreditRating, customer.Segment,
        customer.CashDeposit.Amount, customer.PaysInAdvance, customer.HasPaymentGuarantee);
}
