// Types côté KAM pour l'API .NET (PricingHub). Contrats en camelCase côté
// JSON (convention par défaut d'ASP.NET Core Minimal API), énumérations
// sérialisées comme chaînes PascalCase (JsonStringEnumConverter côté API).
//
// `QuoteResponse` (back-end) porte aussi `lines[].cost` (coût de revient) —
// jamais importé au-delà de `offre.ts` : les coûts et marges ne sont pas
// visibles des KAM (M3-07). Voir `offre.ts` pour l'adaptation qui le filtre.

export type PriceLine = "DryLease" | "HeavyMaintenance" | "OperatingMaintenance" | "Insurance";

export const LIBELLE_PRICE_LINE: Record<PriceLine, string> = {
  DryLease: "Dry lease",
  HeavyMaintenance: "Heavy maintenance",
  OperatingMaintenance: "Operation maintenance",
  Insurance: "Assurance",
};

export type QuoteLineStatus = "Ok" | "Alert" | "BelowFloor" | "Excluded";

export type QuoteStatus = "Draft" | "Calculated" | "Submitted" | "Approved" | "Rejected";

export type ApprovalStatus = "Pending" | "Approved" | "Rejected";

// Entrée du calcul d'offre — équivalent de `ConfigurationOffre` côté Python.
// Pas de `locomotiveNumero` : il n'y a pas d'agrégat Locomotive/Flotte dans
// le domaine .NET (le contrôle C8 reste toujours "hors contrôle", voir
// PreSendControlsEvaluator côté API) ; âge et kilométrage sont donc
// toujours saisis à la main.
export interface CalculateQuoteRequest {
  customerCode: string;
  modelCode: string;
  annualMileageKm: number;
  durationMonths: number;
  quantity: number;
  startDate: string;
  ageAtStartYears: number;
  cumulativeMileageAtStartKm: number;
  heavyMaintenance8Done: boolean;
  heavyMaintenance16Done: boolean;
  includedLines: PriceLine[] | null;
  negotiatedPrices: Partial<Record<PriceLine, number>> | null;
  campaignCode: string | null;
}

export interface QuoteLineResponse {
  line: PriceLine;
  cost: number;
  catalogPrice: number;
  floor: number;
  negotiatedPrice: number | null;
  retainedPrice: number;
  status: QuoteLineStatus;
}

export interface ControlResultResponse {
  code: string;
  label: string;
  ok: boolean;
  detail: string;
}

// Sortie du calcul d'offre — équivalent de `DetailOffreApi` côté Python,
// plus l'identité et la version de l'offre persistée (le back-end .NET
// persiste chaque calcul, contrairement au prototype Python).
export interface QuoteResponse {
  quoteId: string;
  versionNumber: number;
  status: QuoteStatus;
  priceBookNumber: number;
  lines: QuoteLineResponse[];
  residualValueAtStart: number;
  residualValueAtEnd: number;
  monthlyValueLoss: number;
  additionalMileagePricePerKm: number;
  totalCatalogPerUnitMonthly: number;
  totalRetainedPerUnitMonthly: number;
  totalRetainedMonthly: number;
  totalRetainedContract: number;
  globalDiscount: number;
  monthlyReferenceCost: number;
  validationLevel: number;
  validationLevelReasons: string[];
  controls: ControlResultResponse[];
  allControlsOk: boolean;
}

export interface ModelSummaryResponse {
  modelCode: string;
  seriesCode: string;
  name: string;
  newValue: number;
}

export interface CampaignResponse {
  code: string;
  name: string;
  maxDurationMonths: number | null;
  startDate: string;
  endDate: string | null;
}

// Les erreurs de l'API .NET sont systématiquement `{ "error": "..." }"`
// (Results.UnprocessableEntity/Conflict/NotFound avec un objet anonyme),
// à la différence du `{ "detail": ... }` de FastAPI côté Python.
export interface ErreurApi {
  error: string;
}

// Demande de dérogation (M4-02) — équivalent de `DerogationApi` côté
// Python, mais liée à une offre déjà calculée et persistée (`quoteId` +
// `quoteVersion`) plutôt qu'à une configuration brute : le back-end .NET
// ne recalcule rien, il relit l'offre existante.
export interface ApprovalRequestResponse {
  number: number;
  status: ApprovalStatus;
  validationLevel: number;
  requestedBy: string;
  justification: string;
  quoteId: string;
  quoteVersion: number;
  priceBookNumber: number;
  customerCode: string;
  modelCode: string;
  monthlyRetainedAmount: number;
  validatorEmail: string | null;
  requestedAt: string;
  decidedAt: string | null;
  decidedBy: string | null;
  decisionComment: string | null;
}
