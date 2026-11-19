using System;
using Microsoft.EntityFrameworkCore.Migrations;
using Npgsql.EntityFrameworkCore.PostgreSQL.Metadata;

#nullable disable

namespace PricingHub.Infrastructure.Migrations
{
    /// <inheritdoc />
    public partial class Initial_Pricing : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "campaigns",
                columns: table => new
                {
                    code = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    name = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: false),
                    max_duration_months = table.Column<int>(type: "integer", nullable: true),
                    start_date = table.Column<DateOnly>(type: "date", nullable: false),
                    end_date = table.Column<DateOnly>(type: "date", nullable: true),
                    is_active = table.Column<bool>(type: "boolean", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_campaigns", x => x.code);
                });

            migrationBuilder.CreateTable(
                name: "price_books",
                columns: table => new
                {
                    number = table.Column<int>(type: "integer", nullable: false),
                    status = table.Column<string>(type: "character varying(20)", maxLength: 20, nullable: false),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    published_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true),
                    published_by = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: true),
                    additional_mileage_surcharge = table.Column<decimal>(type: "numeric", nullable: false),
                    annual_indexation = table.Column<decimal>(type: "numeric", nullable: false),
                    hm_margin = table.Column<decimal>(type: "numeric", nullable: false),
                    high_rating_threshold = table.Column<int>(type: "integer", nullable: false),
                    insurance_margin = table.Column<decimal>(type: "numeric", nullable: false),
                    kam_discount_threshold = table.Column<decimal>(type: "numeric", nullable: false),
                    max_campaign_duration_months = table.Column<int>(type: "integer", nullable: false),
                    max_high_rating_duration_months = table.Column<int>(type: "integer", nullable: false),
                    max_locomotives_per_contract = table.Column<int>(type: "integer", nullable: false),
                    maximum_discount = table.Column<decimal>(type: "numeric", nullable: false),
                    minimum_dry_lease = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    offer_validity_days = table.Column<int>(type: "integer", nullable: false),
                    om_margin = table.Column<decimal>(type: "numeric", nullable: false),
                    residual_value_bonus_hm16 = table.Column<decimal>(type: "numeric", nullable: false),
                    residual_value_bonus_hm8 = table.Column<decimal>(type: "numeric", nullable: false),
                    residual_value_floor_rate = table.Column<decimal>(type: "numeric", nullable: false),
                    value_loss_per_km_out_of_reference = table.Column<decimal>(type: "numeric", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_price_books", x => x.number);
                });

            migrationBuilder.CreateTable(
                name: "price_book_budget_plan",
                columns: table => new
                {
                    price_book_number = table.Column<int>(type: "integer", nullable: false),
                    id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    model_code = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    mileage_bracket = table.Column<string>(type: "character varying(100)", maxLength: 100, nullable: false),
                    hm_floor = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    om_floor = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    fiscal_year = table.Column<string>(type: "character varying(10)", maxLength: 10, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_price_book_budget_plan", x => new { x.price_book_number, x.id });
                    table.ForeignKey(
                        name: "FK_price_book_budget_plan_price_books_price_book_number",
                        column: x => x.price_book_number,
                        principalTable: "price_books",
                        principalColumn: "number",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "price_book_dry_lease_grid",
                columns: table => new
                {
                    price_book_number = table.Column<int>(type: "integer", nullable: false),
                    id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    model_code = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    duration_bracket = table.Column<string>(type: "character varying(30)", maxLength: 30, nullable: false),
                    monthly_rent = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_price_book_dry_lease_grid", x => new { x.price_book_number, x.id });
                    table.ForeignKey(
                        name: "FK_price_book_dry_lease_grid_price_books_price_book_number",
                        column: x => x.price_book_number,
                        principalTable: "price_books",
                        principalColumn: "number",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "price_book_mileage_brackets",
                columns: table => new
                {
                    price_book_number = table.Column<int>(type: "integer", nullable: false),
                    id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    min_kilometers = table.Column<decimal>(type: "numeric", nullable: false),
                    max_kilometers = table.Column<decimal>(type: "numeric", nullable: true),
                    dry_lease_coefficient = table.Column<decimal>(type: "numeric", nullable: false),
                    heavy_maintenance_coefficient = table.Column<decimal>(type: "numeric", nullable: false),
                    operating_maintenance_coefficient = table.Column<decimal>(type: "numeric", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_price_book_mileage_brackets", x => new { x.price_book_number, x.id });
                    table.ForeignKey(
                        name: "FK_price_book_mileage_brackets_price_books_price_book_number",
                        column: x => x.price_book_number,
                        principalTable: "price_books",
                        principalColumn: "number",
                        onDelete: ReferentialAction.Cascade);
                });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "campaigns");

            migrationBuilder.DropTable(
                name: "price_book_budget_plan");

            migrationBuilder.DropTable(
                name: "price_book_dry_lease_grid");

            migrationBuilder.DropTable(
                name: "price_book_mileage_brackets");

            migrationBuilder.DropTable(
                name: "price_books");
        }
    }
}
