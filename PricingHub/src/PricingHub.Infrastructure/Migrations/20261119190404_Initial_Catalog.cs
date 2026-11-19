using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace PricingHub.Infrastructure.Migrations
{
    /// <inheritdoc />
    public partial class Initial_Catalog : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "countries",
                columns: table => new
                {
                    code = table.Column<string>(type: "character varying(2)", maxLength: 2, nullable: false),
                    name = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: false),
                    is_active = table.Column<bool>(type: "boolean", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_countries", x => x.code);
                });

            migrationBuilder.CreateTable(
                name: "models",
                columns: table => new
                {
                    code = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    series_code = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    name = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: false),
                    service_life_years = table.Column<int>(type: "integer", nullable: false),
                    end_of_life_residual_rate = table.Column<decimal>(type: "numeric", nullable: false),
                    reference_annual_mileage = table.Column<decimal>(type: "numeric", nullable: false),
                    om_variable_cost_per_km = table.Column<decimal>(type: "numeric", nullable: false),
                    annual_insurance_rate = table.Column<decimal>(type: "numeric", nullable: false),
                    hm_16y_cost_amount = table.Column<decimal>(type: "numeric(18,4)", precision: 18, scale: 4, nullable: false),
                    hm_16y_cost_currency = table.Column<string>(type: "character varying(3)", maxLength: 3, nullable: false),
                    hm_8y_cost_amount = table.Column<decimal>(type: "numeric(18,4)", precision: 18, scale: 4, nullable: false),
                    hm_8y_cost_currency = table.Column<string>(type: "character varying(3)", maxLength: 3, nullable: false),
                    new_value_amount = table.Column<decimal>(type: "numeric(18,4)", precision: 18, scale: 4, nullable: false),
                    new_value_currency = table.Column<string>(type: "character varying(3)", maxLength: 3, nullable: false),
                    om_fixed_cost_amount = table.Column<decimal>(type: "numeric(18,4)", precision: 18, scale: 4, nullable: false),
                    om_fixed_cost_currency = table.Column<string>(type: "character varying(3)", maxLength: 3, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_models", x => x.code);
                });

            migrationBuilder.CreateTable(
                name: "products",
                columns: table => new
                {
                    code = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    name = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_products", x => x.code);
                });

            migrationBuilder.CreateTable(
                name: "series",
                columns: table => new
                {
                    code = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    product_code = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    name = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_series", x => x.code);
                });

            migrationBuilder.CreateIndex(
                name: "IX_series_product_code",
                table: "series",
                column: "product_code");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "countries");

            migrationBuilder.DropTable(
                name: "models");

            migrationBuilder.DropTable(
                name: "products");

            migrationBuilder.DropTable(
                name: "series");
        }
    }
}
