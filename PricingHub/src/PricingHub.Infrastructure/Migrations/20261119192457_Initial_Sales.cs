using System;
using Microsoft.EntityFrameworkCore.Migrations;
using Npgsql.EntityFrameworkCore.PostgreSQL.Metadata;

#nullable disable

namespace PricingHub.Infrastructure.Migrations
{
    /// <inheritdoc />
    public partial class Initial_Sales : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "customers",
                columns: table => new
                {
                    code = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    name = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: false),
                    credit_rating = table.Column<int>(type: "integer", nullable: false),
                    segment = table.Column<string>(type: "character varying(100)", maxLength: 100, nullable: false),
                    pays_in_advance = table.Column<bool>(type: "boolean", nullable: false),
                    cash_deposit_amount = table.Column<decimal>(type: "numeric(18,4)", precision: 18, scale: 4, nullable: false),
                    cash_deposit_currency = table.Column<string>(type: "character varying(3)", maxLength: 3, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_customers", x => x.code);
                });

            migrationBuilder.CreateTable(
                name: "opportunities",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false),
                    customer_code = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    title = table.Column<string>(type: "character varying(500)", maxLength: 500, nullable: false),
                    status = table.Column<string>(type: "character varying(20)", maxLength: 20, nullable: false),
                    pipedrive_deal_id = table.Column<int>(type: "integer", nullable: true),
                    quote_ids = table.Column<string>(type: "text", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_opportunities", x => x.id);
                });

            migrationBuilder.CreateTable(
                name: "quotes",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false),
                    customer_code = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    model_code = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    opportunity_id = table.Column<Guid>(type: "uuid", nullable: true),
                    campaign_code = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: true),
                    annual_mileage = table.Column<decimal>(type: "numeric", nullable: false),
                    contract_duration_months = table.Column<int>(type: "integer", nullable: false),
                    quantity = table.Column<int>(type: "integer", nullable: false),
                    start_date = table.Column<DateOnly>(type: "date", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_quotes", x => x.id);
                });

            migrationBuilder.CreateTable(
                name: "scenario_comparisons",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false),
                    customer_code = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    name = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: false),
                    created_by = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: false),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_scenario_comparisons", x => x.id);
                });

            migrationBuilder.CreateTable(
                name: "quote_versions",
                columns: table => new
                {
                    version_number = table.Column<int>(type: "integer", nullable: false),
                    quote_id = table.Column<Guid>(type: "uuid", nullable: false),
                    status = table.Column<string>(type: "character varying(20)", maxLength: 20, nullable: false),
                    included_lines = table.Column<string>(type: "text", nullable: false),
                    negotiated_prices = table.Column<string>(type: "text", nullable: false),
                    locomotive_number = table.Column<string>(type: "character varying(100)", maxLength: 100, nullable: true),
                    age_at_start_years = table.Column<decimal>(type: "numeric", nullable: false),
                    cumulative_mileage_at_start = table.Column<decimal>(type: "numeric", nullable: false),
                    heavy_maintenance_8_done = table.Column<bool>(type: "boolean", nullable: false),
                    heavy_maintenance_16_done = table.Column<bool>(type: "boolean", nullable: false),
                    has_fleet_assignment = table.Column<bool>(type: "boolean", nullable: false),
                    lines = table.Column<string>(type: "text", nullable: false),
                    price_book_number = table.Column<int>(type: "integer", nullable: true),
                    residual_value_at_start = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: true),
                    residual_value_at_end = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: true),
                    total_value_loss = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: true),
                    monthly_value_loss = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: true),
                    additional_mileage_price = table.Column<decimal>(type: "numeric", nullable: true),
                    total_catalog_per_unit_monthly = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: true),
                    total_retained_per_unit_monthly = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: true),
                    total_floor_per_unit_monthly = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: true),
                    total_retained_monthly = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: true),
                    total_retained_contract = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: true),
                    global_discount = table.Column<decimal>(type: "numeric", nullable: true),
                    monthly_reference_cost = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: true),
                    validation_level = table.Column<int>(type: "integer", nullable: false),
                    validation_level_reasons = table.Column<string>(type: "text", nullable: false),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    decided_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true),
                    decided_by = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: true),
                    decision_comment = table.Column<string>(type: "character varying(2000)", maxLength: 2000, nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_quote_versions", x => new { x.quote_id, x.version_number });
                    table.ForeignKey(
                        name: "FK_quote_versions_quotes_quote_id",
                        column: x => x.quote_id,
                        principalTable: "quotes",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "scenario_comparison_entries",
                columns: table => new
                {
                    scenario_comparison_id = table.Column<Guid>(type: "uuid", nullable: false),
                    id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    label = table.Column<string>(type: "character varying(100)", maxLength: 100, nullable: false),
                    quote_id = table.Column<Guid>(type: "uuid", nullable: false),
                    quote_version_number = table.Column<int>(type: "integer", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_scenario_comparison_entries", x => new { x.scenario_comparison_id, x.id });
                    table.ForeignKey(
                        name: "FK_scenario_comparison_entries_scenario_comparisons_scenario_c~",
                        column: x => x.scenario_comparison_id,
                        principalTable: "scenario_comparisons",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Cascade);
                });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "customers");

            migrationBuilder.DropTable(
                name: "opportunities");

            migrationBuilder.DropTable(
                name: "quote_versions");

            migrationBuilder.DropTable(
                name: "scenario_comparison_entries");

            migrationBuilder.DropTable(
                name: "quotes");

            migrationBuilder.DropTable(
                name: "scenario_comparisons");
        }
    }
}
