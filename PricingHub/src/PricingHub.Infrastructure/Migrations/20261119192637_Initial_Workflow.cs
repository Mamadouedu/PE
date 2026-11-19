using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace PricingHub.Infrastructure.Migrations
{
    /// <inheritdoc />
    public partial class Initial_Workflow : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "approval_requests",
                columns: table => new
                {
                    number = table.Column<int>(type: "integer", nullable: false),
                    status = table.Column<string>(type: "character varying(20)", maxLength: 20, nullable: false),
                    validation_level = table.Column<int>(type: "integer", nullable: false),
                    requested_by = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: false),
                    justification = table.Column<string>(type: "character varying(4000)", maxLength: 4000, nullable: false),
                    quote_id = table.Column<Guid>(type: "uuid", nullable: false),
                    quote_version_number = table.Column<int>(type: "integer", nullable: false),
                    price_book_number = table.Column<int>(type: "integer", nullable: false),
                    customer_code = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    model_code = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    validator_email = table.Column<string>(type: "character varying(320)", maxLength: 320, nullable: true),
                    requested_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    decided_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true),
                    decided_by = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: true),
                    decision_comment = table.Column<string>(type: "character varying(2000)", maxLength: 2000, nullable: true),
                    monthly_retained_amount_amount = table.Column<decimal>(type: "numeric(18,4)", precision: 18, scale: 4, nullable: false),
                    monthly_retained_amount_currency = table.Column<string>(type: "character varying(3)", maxLength: 3, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_approval_requests", x => x.number);
                });

            migrationBuilder.CreateTable(
                name: "delegations",
                columns: table => new
                {
                    validation_level = table.Column<int>(type: "integer", nullable: false),
                    name = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: false),
                    email = table.Column<string>(type: "character varying(320)", maxLength: 320, nullable: false),
                    alternate_email = table.Column<string>(type: "character varying(320)", maxLength: 320, nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_delegations", x => x.validation_level);
                });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "approval_requests");

            migrationBuilder.DropTable(
                name: "delegations");
        }
    }
}
