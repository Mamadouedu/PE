"""
Moteur de pricing Akiem — version Excel complète, portée formule à formule
depuis PricingHub (.NET) : src/PricingHub.Domain/Pricing/Calculations/*.cs,
src/PricingHub.Domain/Sales/QuoteAggregate/{Quote,QuoteVersion,QuoteLine}.cs
et src/PricingHub.Api/Services/PreSendControlsEvaluator.cs.

Ce script génère le classeur ; il n'est pas lui-même livré à l'utilisateur.
"""
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import FormulaRule

OUT_PATH = "/home/user/PE/outils/Moteur_Pricing_Akiem.xlsx"

# ---------------------------------------------------------------------------
# Constantes de nommage des feuilles de référence
# ---------------------------------------------------------------------------
SH_MODELS = "Catalogue_Modeles"
SH_CLIENTS = "Clients"
SH_CAMPAIGNS = "Campagnes"
SH_BRACKETS = "PriceBook_TranchesKm"
SH_GRID = "PriceBook_GrilleDryLease"
SH_BP = "PriceBook_BudgetPlan"
SH_DELEG = "Delegations"
SH_PARAMS = "PriceBook_Parametres"

# Plages fixes des tables de référence (ligne 1 = en-tête)
MODELS_RANGE = (2, 21)      # A..M
CLIENTS_RANGE = (2, 21)     # A..F
CAMPAIGNS_RANGE = (2, 21)   # A..F
BRACKETS_RANGE = (2, 11)    # A..E
GRID_RANGE = (2, 21)        # A..D
BP_RANGE = (2, 21)          # A..F
DELEG_RANGE = (2, 4)        # A..D (niveaux 1 à 3, fixe)

# ---------------------------------------------------------------------------
# Styles partagés
# ---------------------------------------------------------------------------
NAVY = "1F3864"
BLUE_LIGHT = "D9E2F3"
YELLOW_INPUT = "FFF2CC"
GRAY_TECH = "F2F2F2"
GREEN_OK = "C6E0B4"
ORANGE_ALERT = "FFE699"
RED_BAD = "F8CBAD"
GRAY_EXCLUDED = "D9D9D9"

FONT_TITLE = Font(bold=True, color="FFFFFF", size=13)
FONT_SECTION = Font(bold=True, color=NAVY, size=11)
FONT_HEADER = Font(bold=True, size=10)
FONT_LABEL = Font(size=10)
FONT_TECH = Font(size=9, italic=True, color="595959")
FONT_NOTE = Font(size=9, italic=True, color="7F7F7F")

FILL_TITLE = PatternFill("solid", fgColor=NAVY)
FILL_SECTION = PatternFill("solid", fgColor=BLUE_LIGHT)
FILL_INPUT = PatternFill("solid", fgColor=YELLOW_INPUT)
FILL_TECH = PatternFill("solid", fgColor=GRAY_TECH)

THIN = Side(style="thin", color="BFBFBF")
BORDER_THIN = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

MONEY_FMT = '#,##0.00" €"'
PCT_FMT = '0.00%'
PCT1_FMT = '0.0%'
INT_FMT = '#,##0'
NUM2_FMT = '#,##0.00'
RATE_FMT = '#,##0.0000" €/km"'
DATE_FMT = 'dd/mm/yyyy'

OUI_NON = '"Oui,Non"'

wb = openpyxl.Workbook()
wb.remove(wb.active)


def set_col_widths(ws, widths):
    for col, w in widths.items():
        ws.column_dimensions[col].width = w


def title_row(ws, row, text, span_to="H"):
    ws.merge_cells(f"A{row}:{span_to}{row}")
    c = ws.cell(row=row, column=1, value=text)
    c.font = FONT_TITLE
    c.fill = FILL_TITLE
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[row].height = 22
    return row + 1


def section_row(ws, row, text, span_to="H"):
    ws.merge_cells(f"A{row}:{span_to}{row}")
    c = ws.cell(row=row, column=1, value=text)
    c.font = FONT_SECTION
    c.fill = FILL_SECTION
    return row + 1


def note_row(ws, row, text, span_to="H"):
    ws.merge_cells(f"A{row}:{span_to}{row}")
    c = ws.cell(row=row, column=1, value=text)
    c.font = FONT_NOTE
    c.alignment = Alignment(wrap_text=True, vertical="top")
    return row + 1


def write_table(ws, header_row, headers, data_rows, col_widths=None, start_col=1):
    for j, h in enumerate(headers):
        c = ws.cell(row=header_row, column=start_col + j, value=h)
        c.font = FONT_HEADER
        c.fill = FILL_SECTION
        c.border = BORDER_THIN
        c.alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")
    for i, row_data in enumerate(data_rows):
        r = header_row + 1 + i
        for j, val in enumerate(row_data):
            cell = ws.cell(row=r, column=start_col + j)
            if isinstance(val, tuple):
                v, fmt = val
                cell.value = v
                if fmt:
                    cell.number_format = fmt
            else:
                cell.value = val
            cell.border = BORDER_THIN
    if col_widths:
        for j, w in enumerate(col_widths):
            ws.column_dimensions[get_column_letter(start_col + j)].width = w


# ===========================================================================
# Feuille : PriceBook_Parametres
# ===========================================================================
ws = wb.create_sheet(SH_PARAMS)
set_col_widths(ws, {"A": 42, "B": 14, "C": 70})
row = title_row(ws, 1, "Paramètres globaux de tarification (référentiel pricing)", span_to="C")
row = note_row(
    ws, row,
    "Ces valeurs sont celles de PricingParameters.Defaults() côté PricingHub (.NET) — "
    "modifiables ici sans développement, comme le prévoit le cahier des charges (section 6). "
    "Toute case « B » de ce tableau est utilisée directement par les onglets Configurateur et Comparateur.",
    span_to="C",
)
row += 1
hdr = row
ws.cell(row=hdr, column=1, value="Paramètre").font = FONT_HEADER
ws.cell(row=hdr, column=2, value="Valeur").font = FONT_HEADER
ws.cell(row=hdr, column=3, value="Remarque").font = FONT_HEADER
for col in "ABC":
    ws[f"{col}{hdr}"].fill = FILL_SECTION
row += 1

PARAM_CELL = {}


def param(label, value, fmt, note, used=True):
    global row
    ws.cell(row=row, column=1, value=label).font = FONT_LABEL
    vcell = ws.cell(row=row, column=2, value=value)
    vcell.number_format = fmt
    vcell.fill = FILL_INPUT
    vcell.border = BORDER_THIN
    ws.cell(row=row, column=3, value=note).font = FONT_NOTE
    key = label
    PARAM_CELL[key] = f"{SH_PARAMS}!$B${row}"
    row += 1
    return key


K_HM_MARGIN = param("Marge Heavy maintenance", 0.15, PCT_FMT, "Catalogue HM = max(coût × (1+marge), plancher BP).")
K_OM_MARGIN = param("Marge Operating maintenance", 0.12, PCT_FMT, "Catalogue OM = max(coût × (1+marge), plancher BP).")
K_INS_MARGIN = param("Marge Assurance", 0.05, PCT_FMT, "Catalogue Assurance = prime × (1+marge).")
K_MAX_DISCOUNT = param("Remise maximale KAM (Dry lease)", 0.10, PCT_FMT, "Plancher Dry lease = catalogue × (1 − remise max).")
K_ADDL_SURCHARGE = param("Majoration km supplémentaire", 0.25, PCT_FMT, "Appliquée au taux €/km de base (HM + OM variable).")
K_KAM_THRESHOLD = param("Seuil de remise KAM (niveau 1)", 0.05, PCT_FMT, "Remise globale > seuil ⇒ niveau de validation ≥ 1.")
K_BONUS_HM8 = param("Bonus VR — HM 8 ans réalisée", 0.04, PCT_FMT, "Ajouté à la valeur résiduelle si HM 8 ans déjà faite.")
K_BONUS_HM16 = param("Bonus VR — HM 16 ans réalisée", 0.04, PCT_FMT, "Ajouté à la valeur résiduelle si HM 16 ans déjà faite.")
K_VR_FLOOR_RATE = param("Taux plancher de la valeur résiduelle", 0.08, PCT_FMT, "VR ne descend jamais sous VN × ce taux.")
K_VALUE_LOSS_PER_KM = param("Perte de valeur hors référence (€/km)", 0.20, NUM2_FMT, "Pénalité sur le kilométrage excédentaire au-delà du théorique.")
K_MAX_CAMPAIGN_MONTHS = param("Durée max. de campagne (mois)", 3, INT_FMT, "Contrôle C1. Valeur GLOBALE : la durée max. propre à chaque campagne (onglet Campagnes) n'est pas câblée dans le moteur actuel — voir note.")
K_MAX_LOCOS = param("Nombre max. de locos par contrat", 2, INT_FMT, "Contrôle C2.")
K_HIGH_RATING_THRESHOLD = param("Seuil de rating client élevé", 7, INT_FMT, "Contrôle C3 : au-delà, durée courte + paiement d'avance exigés.")
K_MAX_HIGH_RATING_MONTHS = param("Durée max. si rating élevé (mois)", 1, INT_FMT, "Contrôle C3.")
row += 1
row = section_row(ws, row, "Paramètres stockés mais NON utilisés par le moteur de calcul à ce stade", span_to="C")
param("Indexation annuelle", 0.02, PCT_FMT, "Champ présent dans PricingParameters (persisté), mais aucun calculateur ne le lit aujourd'hui.", used=False)
param("Durée de validité d'une offre (jours)", 30, INT_FMT, "Idem — non lu par le moteur de calcul actuel.", used=False)
param("Dry lease minimum", 10500, MONEY_FMT, "Idem — non lu par le moteur de calcul actuel.", used=False)

# ===========================================================================
# Feuille : Catalogue_Modeles
# ===========================================================================
ws = wb.create_sheet(SH_MODELS)
row = title_row(ws, 1, "Catalogue — Modèles (le référentiel le plus fin : VN, durée de vie, coûts)", span_to="M")
row = note_row(
    ws, row,
    "Remplace l'onglet « Models » du Price Configurator Excel d'Akiem. Une ligne = un modèle "
    "(ModelAggregate côté PricingHub). Ajoutez des lignes dans la plage ci-dessous (20 lignes prévues) ; "
    "les menus déroulants des onglets Configurateur/Comparateur s'appuient sur cette même plage.",
    span_to="M",
)
row += 1
hdr_models = row
headers = [
    "ModelCode", "SeriesCode", "ProductCode", "Nom", "Valeur à neuf (VN)", "Durée de vie (ans)",
    "Taux VR fin de vie", "Km annuel référence", "Coût HM 8 ans", "Coût HM 16 ans",
    "OM fixe (€/an)", "OM variable (€/km)", "Taux assurance annuel",
]
data = [[
    "VECTRON", "VECTRON", "LOCOMOTIVE", "Vectron",
    (2_000_000, MONEY_FMT), (30, INT_FMT), (0.10, PCT_FMT), (120_000, INT_FMT),
    (150_000, MONEY_FMT), (200_000, MONEY_FMT), (6_000, MONEY_FMT), (0.05, NUM2_FMT), (0.03, PCT_FMT),
]]
while len(data) < (MODELS_RANGE[1] - MODELS_RANGE[0] + 1):
    data.append([None] * len(headers))
write_table(ws, hdr_models, headers, data, col_widths=[12, 12, 12, 14, 14, 12, 12, 14, 13, 13, 12, 13, 13])
MODELS_RANGE = (hdr_models + 1, hdr_models + (MODELS_RANGE[1] - MODELS_RANGE[0] + 1))

# ===========================================================================
# Feuille : Clients
# ===========================================================================
ws = wb.create_sheet(SH_CLIENTS)
row = title_row(ws, 1, "Clients (contrôles C3 et C5 avant envoi)", span_to="F")
row = note_row(
    ws, row,
    "Une ligne = un client (CustomerAggregate). « Paiement d'avance » et le rating conditionnent "
    "les contrôles C3 (client à rating élevé) et C5 (garantie de paiement).",
    span_to="F",
)
row += 1
hdr_clients = row
headers = ["ClientCode", "Nom", "Rating crédit (0-10)", "Segment", "Cash deposit", "Paiement d'avance"]
data = [[
    "CLIENTOK", "Client standard", (5, INT_FMT), "Fret", (0, MONEY_FMT), "Oui",
]]
while len(data) < (CLIENTS_RANGE[1] - CLIENTS_RANGE[0] + 1):
    data.append([None] * len(headers))
write_table(ws, hdr_clients, headers, data, col_widths=[13, 20, 16, 12, 13, 15])
CLIENTS_RANGE = (hdr_clients + 1, hdr_clients + (CLIENTS_RANGE[1] - CLIENTS_RANGE[0] + 1))
dv_oui_non = DataValidation(type="list", formula1=OUI_NON, allow_blank=True)
ws.add_data_validation(dv_oui_non)
dv_oui_non.add(f"F{hdr_clients+1}:F{hdr_clients+(CLIENTS_RANGE[1]-CLIENTS_RANGE[0]+1)}")

# ===========================================================================
# Feuille : Campagnes
# ===========================================================================
ws = wb.create_sheet(SH_CAMPAIGNS)
row = title_row(ws, 1, "Campagnes commerciales", span_to="F")
row = note_row(
    ws, row,
    "Une ligne = une campagne (CampaignAggregate). Attention : dans le moteur actuel, le contrôle C1 "
    "compare la durée du contrat à la durée MAX. GLOBALE (onglet Paramètres), jamais à la colonne "
    "« Durée max. (mois) » ci-dessous ni aux dates de la campagne — ce champ est stocké mais pas encore "
    "câblé dans PricingHub.Api, à l'identique de ce qui est livré aujourd'hui.",
    span_to="F",
)
row += 1
hdr_camp = row
headers = ["CodeCampagne", "Nom", "Durée max. (mois) — info seule", "Date début", "Date fin", "Active — info seule"]
data = [[
    "PROMO2026", "Campagne promotionnelle 2026", (36, INT_FMT), ("2026-01-01", DATE_FMT), ("2026-12-31", DATE_FMT), "Oui",
]]
while len(data) < (CAMPAIGNS_RANGE[1] - CAMPAIGNS_RANGE[0] + 1):
    data.append([None] * len(headers))
write_table(ws, hdr_camp, headers, data, col_widths=[14, 26, 20, 12, 12, 16])
CAMPAIGNS_RANGE = (hdr_camp + 1, hdr_camp + (CAMPAIGNS_RANGE[1] - CAMPAIGNS_RANGE[0] + 1))
dv2 = DataValidation(type="list", formula1=OUI_NON, allow_blank=True)
ws.add_data_validation(dv2)
dv2.add(f"F{hdr_camp+1}:F{hdr_camp+(CAMPAIGNS_RANGE[1]-CAMPAIGNS_RANGE[0]+1)}")

# ===========================================================================
# Feuille : Delegations
# ===========================================================================
ws = wb.create_sheet(SH_DELEG)
row = title_row(ws, 1, "Délégation — un validateur par niveau de validation (1 à 3)", span_to="D")
row = note_row(
    ws, row,
    "Le niveau 0 (« dans les règles ») n'a pas de validateur. Tant qu'une ligne n'est pas renseignée, "
    "le Configurateur affiche « aucun validateur configuré » pour ce niveau — à l'identique de l'état "
    "réel de la base PricingHub aujourd'hui (table vide).",
    span_to="D",
)
row += 1
hdr_deleg = row
headers = ["Niveau", "Nom", "Email", "Email secondaire"]
data = [
    [(1, INT_FMT), None, None, None],
    [(2, INT_FMT), None, None, None],
    [(3, INT_FMT), None, None, None],
]
write_table(ws, hdr_deleg, headers, data, col_widths=[9, 22, 28, 28])
DELEG_RANGE = (hdr_deleg + 1, hdr_deleg + (DELEG_RANGE[1] - DELEG_RANGE[0] + 1))

# ===========================================================================
# Feuille : PriceBook_TranchesKm
# ===========================================================================
ws = wb.create_sheet(SH_BRACKETS)
row = title_row(ws, 1, "Tranches de kilométrage annuel et coefficients", span_to="E")
row = note_row(
    ws, row,
    "Laissez « Max km » vide pour une tranche sans plafond (illimitée). Les coefficients multiplient "
    "les prix catalogue (ce ne sont pas des pourcentages : ils peuvent dépasser 1).",
    span_to="E",
)
row += 1
hdr_brackets = row
headers = ["Min km", "Max km (vide = illimité)", "Coef. Dry lease", "Coef. Heavy maintenance", "Coef. Operating maintenance"]
data = [
    [(80_000, INT_FMT), (149_999, INT_FMT), (1.00, NUM2_FMT), (1.00, NUM2_FMT), (1.00, NUM2_FMT)],
    [(150_000, INT_FMT), (200_000, INT_FMT), (1.05, NUM2_FMT), (1.10, NUM2_FMT), (1.05, NUM2_FMT)],
]
while len(data) < (BRACKETS_RANGE[1] - BRACKETS_RANGE[0] + 1):
    data.append([None] * len(headers))
write_table(ws, hdr_brackets, headers, data, col_widths=[12, 22, 15, 20, 24])
BRACKETS_RANGE = (hdr_brackets + 1, hdr_brackets + (BRACKETS_RANGE[1] - BRACKETS_RANGE[0] + 1))

# ===========================================================================
# Feuille : PriceBook_GrilleDryLease
# ===========================================================================
ws = wb.create_sheet(SH_GRID)
row = title_row(ws, 1, "Grille Dry lease — loyer catalogue par modèle × tranche de durée", span_to="D")
row = note_row(
    ws, row,
    "Laissez « Durée max » vide pour une tranche sans plafond. Le loyer est ensuite multiplié par le "
    "coefficient Dry lease de la tranche de kilométrage (onglet PriceBook_TranchesKm).",
    span_to="D",
)
row += 1
hdr_grid = row
headers = ["ModelCode", "Durée min (mois)", "Durée max (mois) — vide = illimité", "Loyer mensuel catalogue"]
data = [[
    "VECTRON", (0, INT_FMT), None, (20_000, MONEY_FMT),
]]
while len(data) < (GRID_RANGE[1] - GRID_RANGE[0] + 1):
    data.append([None] * len(headers))
write_table(ws, hdr_grid, headers, data, col_widths=[12, 16, 28, 20])
GRID_RANGE = (hdr_grid + 1, hdr_grid + (GRID_RANGE[1] - GRID_RANGE[0] + 1))

# ===========================================================================
# Feuille : PriceBook_BudgetPlan
# ===========================================================================
ws = wb.create_sheet(SH_BP)
row = title_row(ws, 1, "Budget Plan — planchers HM/OM par modèle × tranche de km", span_to="F")
row = note_row(
    ws, row,
    "Le prix retenu HM/OM ne descend jamais sous ces planchers, quelle que soit la remise négociée "
    "(section 12.3 du cahier des charges) — contrôle C6.",
    span_to="F",
)
row += 1
hdr_bp = row
headers = ["ModelCode", "Min km", "Max km (vide = illimité)", "Plancher HM", "Plancher OM", "Exercice"]
data = [
    ["VECTRON", (80_000, INT_FMT), (149_999, INT_FMT), (2_000, MONEY_FMT), (1_500, MONEY_FMT), "2026"],
    ["VECTRON", (150_000, INT_FMT), (200_000, INT_FMT), (2_400, MONEY_FMT), (1_800, MONEY_FMT), "2026"],
]
while len(data) < (BP_RANGE[1] - BP_RANGE[0] + 1):
    data.append([None] * len(headers))
write_table(ws, hdr_bp, headers, data, col_widths=[12, 12, 22, 13, 13, 11])
BP_RANGE = (hdr_bp + 1, hdr_bp + (BP_RANGE[1] - BP_RANGE[0] + 1))

# ===========================================================================
# Moteur de calcul réutilisable (un bloc = un scénario : A, B ou C)
# ===========================================================================
MODEL_ROW_RANGE = f"${get_column_letter(1)}${MODELS_RANGE[0]}:${get_column_letter(1)}${MODELS_RANGE[1]}"


def rng(sheet, col, r0, r1):
    return f"{sheet}!${col}${r0}:${col}${r1}"


class EngineBlock:
    """Un bloc complet : entrées KAM + moteur de prix + contrôles C1-C8 +
    niveau de validation. Colonnes A-H = zone utilisateur, colonnes J-K =
    zone technique (valeurs intermédiaires, calquées sur les calculateurs
    PricingHub.Domain.Pricing.Calculations.*)."""

    def __init__(self, ws, r0, label, defaults):
        self.ws = ws
        self.r0 = r0
        self.row = r0
        self.trow = r0
        self.label = label
        self.d = defaults
        self.cells = {}
        self.tech = {}

    # -- zone utilisateur (A label / B valeur) ------------------------------
    def title(self, text):
        self.row = title_row(self.ws, self.row, text)

    def section(self, text):
        self.row = section_row(self.ws, self.row, text)

    def note(self, text):
        self.row = note_row(self.ws, self.row, text)

    def inp(self, key, label, default, fmt=None, dropdown_formula=None, allow_blank=False):
        r = self.row
        self.ws.cell(row=r, column=1, value=label).font = FONT_LABEL
        c = self.ws.cell(row=r, column=2, value=default)
        c.fill = FILL_INPUT
        c.border = BORDER_THIN
        if fmt:
            c.number_format = fmt
        if dropdown_formula:
            dv = DataValidation(type="list", formula1=dropdown_formula, allow_blank=allow_blank)
            self.ws.add_data_validation(dv)
            dv.add(f"B{r}")
        addr = f"${get_column_letter(2)}${r}"
        self.cells[key] = f"{self.ws.title}!{addr}"
        self.cells[key + "_local"] = addr
        self.row += 1
        return addr

    def out(self, key, label, formula, fmt=None):
        r = self.row
        self.ws.cell(row=r, column=1, value=label).font = FONT_LABEL
        c = self.ws.cell(row=r, column=2, value=formula)
        c.fill = FILL_TECH
        c.border = BORDER_THIN
        if fmt:
            c.number_format = fmt
        addr = f"${get_column_letter(2)}${r}"
        self.cells[key] = f"{self.ws.title}!{addr}"
        self.cells[key + "_local"] = addr
        self.row += 1
        return addr

    # -- zone technique (J label / K valeur) --------------------------------
    def t(self, key, formula, fmt=None):
        r = self.trow
        self.ws.cell(row=r, column=10, value=key).font = FONT_TECH
        c = self.ws.cell(row=r, column=11, value=formula)
        c.font = FONT_TECH
        if fmt:
            c.number_format = fmt
        addr = f"${get_column_letter(11)}${r}"
        self.tech[key] = addr
        self.trow += 1
        return addr

    def tech_header(self, text):
        self.ws.cell(row=self.trow, column=10, value=text).font = Font(bold=True, size=9, color=NAVY)
        self.trow += 1

    def bottom(self):
        return max(self.row, self.trow)


def build_engine_block(ws, r0, label, defaults):
    b = EngineBlock(ws, r0, label, defaults)
    d = defaults

    b.title(f"SCÉNARIO {label} — Chiffrage")
    b.tech_header(f"ZONE TECHNIQUE — scénario {label} (valeurs intermédiaires, ne pas modifier)")

    # ---- Entrées -----------------------------------------------------------
    b.section("Entrées")
    model_dd = f"={SH_MODELS}!$A${MODELS_RANGE[0]}:$A${MODELS_RANGE[1]}"
    client_dd = f"={SH_CLIENTS}!$A${CLIENTS_RANGE[0]}:$A${CLIENTS_RANGE[1]}"
    camp_dd = f"={SH_CAMPAIGNS}!$A${CAMPAIGNS_RANGE[0]}:$A${CAMPAIGNS_RANGE[1]}"

    client = b.inp("client", "Client", d["client"], dropdown_formula=client_dd)
    model = b.inp("model", "Modèle", d["model"], dropdown_formula=model_dd)
    km_an = b.inp("km_an", "Kilométrage annuel (km)", d["km_an"], fmt=INT_FMT)
    duree = b.inp("duree", "Durée (mois)", d["duree"], fmt=INT_FMT)
    qte = b.inp("qte", "Quantité (nombre de locos)", d["qte"], fmt=INT_FMT)
    b.inp("date_debut", "Date de début (informatif — non utilisé par le calcul)", d["date_debut"], fmt=DATE_FMT)
    age_debut = b.inp("age_debut", "Âge au début (années)", d["age_debut"], fmt=NUM2_FMT)
    km_cumules_debut = b.inp("km_cumules_debut", "Km cumulés au début", d["km_cumules_debut"], fmt=INT_FMT)
    hm8 = b.inp("hm8", "HM 8 ans déjà réalisée ?", d["hm8"], dropdown_formula=OUI_NON)
    hm16 = b.inp("hm16", "HM 16 ans déjà réalisée ?", d["hm16"], dropdown_formula=OUI_NON)
    campagne = b.inp("campagne", "Campagne commerciale (optionnel)", d["campagne"], dropdown_formula=camp_dd, allow_blank=True)

    # ---- Zone technique : référentiel ---------------------------------------
    model_pos = b.t("Model_Position", f'=IFERROR(MATCH({model},{rng(SH_MODELS,"A",*MODELS_RANGE)},0),"")')
    model_name = b.t("Model_Nom", f'=IF({model_pos}="","introuvable",INDEX({rng(SH_MODELS,"D",*MODELS_RANGE)},{model_pos}))')
    model_newvalue = b.t("Model_ValeurANeuf", f'=IFERROR(INDEX({rng(SH_MODELS,"E",*MODELS_RANGE)},{model_pos}),0)', MONEY_FMT)
    model_servicelife = b.t("Model_DureeVieAns", f'=IFERROR(INDEX({rng(SH_MODELS,"F",*MODELS_RANGE)},{model_pos}),1)', INT_FMT)
    model_eol_rate = b.t("Model_TauxVRFinDeVie", f'=IFERROR(INDEX({rng(SH_MODELS,"G",*MODELS_RANGE)},{model_pos}),0)', PCT_FMT)
    model_ref_km = b.t("Model_KmAnnuelRef", f'=IFERROR(INDEX({rng(SH_MODELS,"H",*MODELS_RANGE)},{model_pos}),1)', INT_FMT)
    model_hm8cost = b.t("Model_CoutHM8ans", f'=IFERROR(INDEX({rng(SH_MODELS,"I",*MODELS_RANGE)},{model_pos}),0)', MONEY_FMT)
    model_hm16cost = b.t("Model_CoutHM16ans", f'=IFERROR(INDEX({rng(SH_MODELS,"J",*MODELS_RANGE)},{model_pos}),0)', MONEY_FMT)
    model_om_fixed = b.t("Model_OMFixe", f'=IFERROR(INDEX({rng(SH_MODELS,"K",*MODELS_RANGE)},{model_pos}),0)', MONEY_FMT)
    model_om_var = b.t("Model_OMVariable", f'=IFERROR(INDEX({rng(SH_MODELS,"L",*MODELS_RANGE)},{model_pos}),0)', NUM2_FMT)
    model_ins_rate = b.t("Model_TauxAssurance", f'=IFERROR(INDEX({rng(SH_MODELS,"M",*MODELS_RANGE)},{model_pos}),0)', PCT_FMT)
    model_hm_cost_per_km = b.t("Model_CoutHMauKm", f'=IFERROR(({model_hm8cost}+{model_hm16cost})/(16*{model_ref_km}),0)', RATE_FMT)

    client_pos = b.t("Client_Position", f'=IFERROR(MATCH({client},{rng(SH_CLIENTS,"A",*CLIENTS_RANGE)},0),"")')
    client_found = b.t("Client_Trouve", f'=ISNUMBER({client_pos})')
    client_rating = b.t("Client_Rating", f'=IF({client_found},INDEX({rng(SH_CLIENTS,"C",*CLIENTS_RANGE)},{client_pos}),"")')
    client_cashdeposit = b.t("Client_CashDeposit", f'=IF({client_found},INDEX({rng(SH_CLIENTS,"E",*CLIENTS_RANGE)},{client_pos}),0)', MONEY_FMT)
    client_pays_advance = b.t("Client_PaiementAvance", f'=IF({client_found},INDEX({rng(SH_CLIENTS,"F",*CLIENTS_RANGE)},{client_pos})="Oui",FALSE)')
    client_guarantee = b.t("Client_GarantiePaiement", f'=OR({client_cashdeposit}>0,{client_pays_advance})')
    client_high_risk = b.t("Client_RatingEleve", f'=IF({client_found},{client_rating}>{PARAM_CELL[K_HIGH_RATING_THRESHOLD]},FALSE)')

    bracket_absrow = b.t(
        "Tranche_LigneAbsolue",
        # Garde (A<>"") : sans clé de type ModelCode sur cette table, une
        # ligne vide (placeholder d'extension) satisferait sinon aussi
        # "km >= 0" et "max vide = illimité", et gagnerait le MAX (ROW() le
        # plus grand) face à la vraie tranche.
        f'=SUMPRODUCT(MAX(({rng(SH_BRACKETS,"A",*BRACKETS_RANGE)}<>"")'
        f'*({km_an}>={rng(SH_BRACKETS,"A",*BRACKETS_RANGE)})'
        f'*(({rng(SH_BRACKETS,"B",*BRACKETS_RANGE)}="")+({km_an}<={rng(SH_BRACKETS,"B",*BRACKETS_RANGE)}))'
        f'*ROW({rng(SH_BRACKETS,"A",*BRACKETS_RANGE)})))',
    )
    coef_dl = b.t("Tranche_CoefDL", f'=IFERROR(INDEX({rng(SH_BRACKETS,"C",*BRACKETS_RANGE)},{bracket_absrow}-{BRACKETS_RANGE[0]}+1),0)', NUM2_FMT)
    coef_hm = b.t("Tranche_CoefHM", f'=IFERROR(INDEX({rng(SH_BRACKETS,"D",*BRACKETS_RANGE)},{bracket_absrow}-{BRACKETS_RANGE[0]}+1),0)', NUM2_FMT)
    coef_om = b.t("Tranche_CoefOM", f'=IFERROR(INDEX({rng(SH_BRACKETS,"E",*BRACKETS_RANGE)},{bracket_absrow}-{BRACKETS_RANGE[0]}+1),0)', NUM2_FMT)

    grid_absrow = b.t(
        "GrilleDL_LigneAbsolue",
        f'=SUMPRODUCT(MAX(({model}={rng(SH_GRID,"A",*GRID_RANGE)})'
        f'*({duree}>={rng(SH_GRID,"B",*GRID_RANGE)})'
        f'*(({rng(SH_GRID,"C",*GRID_RANGE)}="")+({duree}<={rng(SH_GRID,"C",*GRID_RANGE)}))'
        f'*ROW({rng(SH_GRID,"A",*GRID_RANGE)})))',
    )
    grid_rent = b.t("GrilleDL_LoyerCatalogue", f'=IFERROR(INDEX({rng(SH_GRID,"D",*GRID_RANGE)},{grid_absrow}-{GRID_RANGE[0]}+1),0)', MONEY_FMT)

    bp_absrow = b.t(
        "BudgetPlan_LigneAbsolue",
        f'=SUMPRODUCT(MAX(({model}={rng(SH_BP,"A",*BP_RANGE)})'
        f'*({km_an}>={rng(SH_BP,"B",*BP_RANGE)})'
        f'*(({rng(SH_BP,"C",*BP_RANGE)}="")+({km_an}<={rng(SH_BP,"C",*BP_RANGE)}))'
        f'*ROW({rng(SH_BP,"A",*BP_RANGE)})))',
    )
    bp_hmfloor = b.t("BudgetPlan_PlancherHM", f'=IFERROR(INDEX({rng(SH_BP,"D",*BP_RANGE)},{bp_absrow}-{BP_RANGE[0]}+1),0)', MONEY_FMT)
    bp_omfloor = b.t("BudgetPlan_PlancherOM", f'=IFERROR(INDEX({rng(SH_BP,"E",*BP_RANGE)},{bp_absrow}-{BP_RANGE[0]}+1),0)', MONEY_FMT)

    is_campaign = b.t("EstCampagne", f'={campagne}<>""')

    # ---- Zone technique : valeur résiduelle (VR(âge, km), section 6.2) -----
    vr_bonus = b.t(
        "VR_Bonus",
        f'=IF({hm8}="Oui",{model_newvalue}*{PARAM_CELL[K_BONUS_HM8]},0)'
        f'+IF({hm16}="Oui",{model_newvalue}*{PARAM_CELL[K_BONUS_HM16]},0)',
        MONEY_FMT,
    )
    vr_floor = b.t("VR_Plancher", f'={model_newvalue}*{PARAM_CELL[K_VR_FLOOR_RATE]}', MONEY_FMT)

    age_fin = b.t("Age_Fin", f'={age_debut}+{duree}/12', NUM2_FMT)
    km_cumules_fin = b.t("KmCumules_Fin", f'={km_cumules_debut}+{km_an}*{duree}/12', INT_FMT)

    def vr_chain(suffix, age_cell, mileage_cell):
        aging = b.t(f"VR_RatioUsure_{suffix}", f'=MIN(1,{age_cell}/{model_servicelife})', NUM2_FMT)
        wear_ratio = b.t(f"VR_TauxUsure_{suffix}", f'=1-(1-{model_eol_rate})*{aging}', NUM2_FMT)
        wear = b.t(f"VR_Usure_{suffix}", f'={model_newvalue}*{wear_ratio}', MONEY_FMT)
        theoretical = b.t(f"VR_KmTheorique_{suffix}", f'={model_ref_km}*{age_cell}', INT_FMT)
        excess = b.t(f"VR_KmExcedentaire_{suffix}", f'=MAX(0,{mileage_cell}-{theoretical})', INT_FMT)
        penalty = b.t(f"VR_PenaliteKm_{suffix}", f'={PARAM_CELL[K_VALUE_LOSS_PER_KM]}*{excess}', MONEY_FMT)
        base = b.t(f"VR_ValeurBase_{suffix}", f'={wear}+{vr_bonus}-{penalty}', MONEY_FMT)
        vr = b.t(f"VR_{suffix}", f'=MAX({vr_floor},{base})', MONEY_FMT)
        return vr

    vr_debut = vr_chain("Debut", age_debut, km_cumules_debut)
    vr_fin = vr_chain("Fin", age_fin, km_cumules_fin)
    vr_moyenne = b.t("VR_Moyenne", f'=({vr_debut}+{vr_fin})/2', MONEY_FMT)
    perte_valeur_totale = b.t("ValeurPerte_Totale", f'={vr_debut}-{vr_fin}', MONEY_FMT)
    perte_valeur_mensuelle = b.t("ValeurPerte_Mensuelle", f'={perte_valeur_totale}/{duree}', MONEY_FMT)

    prix_km_suppl = b.t(
        "PrixKmSupplementaire",
        f'=({model_hm_cost_per_km}*{coef_hm}+{model_om_var}*{coef_om})*(1+{PARAM_CELL[K_ADDL_SURCHARGE]})',
        RATE_FMT,
    )

    # ---- Zone technique : les 4 briques (coût / catalogue / plancher) ------
    dl_cost = b.t("DL_Cout", f'={grid_rent}', MONEY_FMT)
    dl_catalog = b.t("DL_Catalogue", f'={grid_rent}*{coef_dl}', MONEY_FMT)
    dl_floor = b.t("DL_Plancher", f'={dl_catalog}*(1-{PARAM_CELL[K_MAX_DISCOUNT]})', MONEY_FMT)

    hm_cost = b.t("HM_Cout", f'={model_hm_cost_per_km}*{km_an}/12*{coef_hm}', MONEY_FMT)
    hm_catalog = b.t("HM_Catalogue", f'=MAX({hm_cost}*(1+{PARAM_CELL[K_HM_MARGIN]}),{bp_hmfloor})', MONEY_FMT)
    hm_floor = b.t("HM_Plancher", f'={bp_hmfloor}', MONEY_FMT)

    om_cost = b.t("OM_Cout", f'=({model_om_fixed}+{model_om_var}*{km_an})*(1/12)*{coef_om}', MONEY_FMT)
    om_catalog = b.t("OM_Catalogue", f'=MAX({om_cost}*(1+{PARAM_CELL[K_OM_MARGIN]}),{bp_omfloor})', MONEY_FMT)
    om_floor = b.t("OM_Plancher", f'={bp_omfloor}', MONEY_FMT)

    ins_cost = b.t("ASSURANCE_Cout", f'={vr_moyenne}*{model_ins_rate}/12', MONEY_FMT)
    ins_catalog = b.t("ASSURANCE_Catalogue", f'={ins_cost}*(1+{PARAM_CELL[K_INS_MARGIN]})', MONEY_FMT)
    ins_floor = b.t("ASSURANCE_Plancher", f'={ins_cost}', MONEY_FMT)

    return b, dict(
        client=client, model=model, km_an=km_an, duree=duree, qte=qte,
        age_debut=age_debut, km_cumules_debut=km_cumules_debut, hm8=hm8, hm16=hm16, campagne=campagne,
        model_name=model_name, client_found=client_found, client_rating=client_rating,
        client_cashdeposit=client_cashdeposit, client_pays_advance=client_pays_advance,
        client_guarantee=client_guarantee, client_high_risk=client_high_risk,
        coef_dl=coef_dl, coef_hm=coef_hm, coef_om=coef_om, grid_rent=grid_rent,
        bp_hmfloor=bp_hmfloor, bp_omfloor=bp_omfloor, is_campaign=is_campaign,
        vr_debut=vr_debut, vr_fin=vr_fin, vr_moyenne=vr_moyenne,
        perte_valeur_mensuelle=perte_valeur_mensuelle, prix_km_suppl=prix_km_suppl,
        dl_cost=dl_cost, dl_catalog=dl_catalog, dl_floor=dl_floor,
        hm_cost=hm_cost, hm_catalog=hm_catalog, hm_floor=hm_floor,
        om_cost=om_cost, om_catalog=om_catalog, om_floor=om_floor,
        ins_cost=ins_cost, ins_catalog=ins_catalog, ins_floor=ins_floor,
    )


def apply_status_cf(ws, rng_str):
    ws.conditional_formatting.add(
        rng_str, FormulaRule(formula=[f'{rng_str.split(":")[0]}="Dans les règles"'], fill=PatternFill("solid", fgColor=GREEN_OK))
    )
    ws.conditional_formatting.add(
        rng_str, FormulaRule(formula=[f'{rng_str.split(":")[0]}="Négocié sous catalogue"'], fill=PatternFill("solid", fgColor=ORANGE_ALERT))
    )
    ws.conditional_formatting.add(
        rng_str, FormulaRule(formula=[f'{rng_str.split(":")[0]}="Sous plancher"'], fill=PatternFill("solid", fgColor=RED_BAD))
    )
    ws.conditional_formatting.add(
        rng_str, FormulaRule(formula=[f'{rng_str.split(":")[0]}="Exclue"'], fill=PatternFill("solid", fgColor=GRAY_EXCLUDED))
    )


def apply_bool_cf(ws, rng_str):
    ws.conditional_formatting.add(
        rng_str, FormulaRule(formula=[f'{rng_str.split(":")[0]}=TRUE'], fill=PatternFill("solid", fgColor=GREEN_OK))
    )
    ws.conditional_formatting.add(
        rng_str, FormulaRule(formula=[f'{rng_str.split(":")[0]}=FALSE'], fill=PatternFill("solid", fgColor=RED_BAD))
    )


def build_lines_and_controls(b, refs):
    ws = b.ws
    d = b.d

    # ---- Détail par brique --------------------------------------------------
    b.section("Détail par brique (M3-07 : la colonne Coût n'est jamais montrée au KAM dans l'outil web)")
    hdr = b.row
    headers = ["Brique", "Incluse ?", "Coût", "Catalogue", "Plancher", "Négocié", "Retenu", "Statut"]
    for j, h in enumerate(headers):
        c = ws.cell(row=hdr, column=2 + j, value=h)
        c.font = FONT_HEADER
        c.fill = FILL_SECTION
        c.border = BORDER_THIN
        c.alignment = Alignment(horizontal="center", wrap_text=True)
    b.row += 1

    def line_row(name, cost, catalog, floor, inc_default, neg_default):
        r = b.row
        ws.cell(row=r, column=2, value=name).font = FONT_LABEL
        ws.cell(row=r, column=2).border = BORDER_THIN

        c_inc = ws.cell(row=r, column=3, value=inc_default)
        c_inc.fill = FILL_INPUT
        c_inc.border = BORDER_THIN
        dv = DataValidation(type="list", formula1=OUI_NON, allow_blank=False)
        ws.add_data_validation(dv)
        dv.add(f"C{r}")
        inc_addr = f"$C${r}"

        c_cost = ws.cell(row=r, column=4, value=f"={cost}")
        c_cost.number_format = MONEY_FMT
        c_cost.fill = FILL_TECH
        c_cost.border = BORDER_THIN

        c_cat = ws.cell(row=r, column=5, value=f"={catalog}")
        c_cat.number_format = MONEY_FMT
        c_cat.fill = FILL_TECH
        c_cat.border = BORDER_THIN
        cat_addr = f"$E${r}"

        c_floor = ws.cell(row=r, column=6, value=f"={floor}")
        c_floor.number_format = MONEY_FMT
        c_floor.fill = FILL_TECH
        c_floor.border = BORDER_THIN
        floor_addr = f"$F${r}"

        c_neg = ws.cell(row=r, column=7, value=neg_default)
        c_neg.number_format = MONEY_FMT
        c_neg.fill = FILL_INPUT
        c_neg.border = BORDER_THIN
        neg_addr = f"$G${r}"

        c_ret = ws.cell(
            row=r, column=8,
            value=f'=IF({inc_addr}<>"Oui",0,IF({neg_addr}="",{cat_addr},{neg_addr}))',
        )
        c_ret.number_format = MONEY_FMT
        c_ret.fill = FILL_TECH
        c_ret.border = BORDER_THIN
        ret_addr = f"$H${r}"

        c_stat = ws.cell(
            row=r, column=9,
            value=(
                f'=IF({inc_addr}<>"Oui","Exclue",'
                f'IF({ret_addr}<{floor_addr},"Sous plancher",'
                f'IF(AND({neg_addr}<>"",{neg_addr}<{cat_addr}),"Négocié sous catalogue","Dans les règles")))'
            ),
        )
        c_stat.fill = FILL_TECH
        c_stat.border = BORDER_THIN
        stat_addr = f"$I${r}"

        b.row += 1
        return dict(inc=inc_addr, ret=ret_addr, stat=stat_addr)

    dl = line_row("Dry lease", refs["dl_cost"], refs["dl_catalog"], refs["dl_floor"], d["inc_dl"], d["neg_dl"])
    hm = line_row("Heavy maintenance", refs["hm_cost"], refs["hm_catalog"], refs["hm_floor"], d["inc_hm"], d["neg_hm"])
    om = line_row("Operating maintenance", refs["om_cost"], refs["om_catalog"], refs["om_floor"], d["inc_om"], d["neg_om"])
    ins = line_row("Assurance", refs["ins_cost"], refs["ins_catalog"], refs["ins_floor"], d["inc_ass"], d["neg_ass"])

    apply_status_cf(ws, f"I{hdr+1}:I{hdr+4}")
    ws.column_dimensions["B"].width = 20
    for col in "CDEFGHI":
        ws.column_dimensions[col].width = 14

    sheet = ws.title

    def q(addr):
        return f"{sheet}!{addr}"

    # ---- Totaux --------------------------------------------------------------
    b.section("Totaux")
    total_catalog = b.out(
        "total_catalog", "Total catalogue / loco / mois",
        f'=IF({dl["stat"]}<>"Exclue",{refs["dl_catalog"]},0)+IF({hm["stat"]}<>"Exclue",{refs["hm_catalog"]},0)'
        f'+IF({om["stat"]}<>"Exclue",{refs["om_catalog"]},0)+IF({ins["stat"]}<>"Exclue",{refs["ins_catalog"]},0)',
        MONEY_FMT,
    )
    total_floor = b.out(
        "total_floor", "Total plancher / loco / mois",
        f'=IF({dl["stat"]}<>"Exclue",{refs["dl_floor"]},0)+IF({hm["stat"]}<>"Exclue",{refs["hm_floor"]},0)'
        f'+IF({om["stat"]}<>"Exclue",{refs["om_floor"]},0)+IF({ins["stat"]}<>"Exclue",{refs["ins_floor"]},0)',
        MONEY_FMT,
    )
    total_retenu_unit = b.out(
        "total_retenu_unit", "Total retenu / loco / mois",
        f'={dl["ret"]}+{hm["ret"]}+{om["ret"]}+{ins["ret"]}', MONEY_FMT,
    )
    total_retenu_mensuel = b.out("total_retenu_mensuel", "Total retenu mensuel (× quantité)", f'={total_retenu_unit}*{refs["qte"]}', MONEY_FMT)
    total_retenu_contrat = b.out("total_retenu_contrat", "Total retenu sur la durée du contrat", f'={total_retenu_unit}*{refs["qte"]}*{refs["duree"]}', MONEY_FMT)
    remise_globale = b.out("remise_globale", "Remise globale", f'=IF({total_catalog}>0,1-{total_retenu_unit}/{total_catalog},0)', PCT1_FMT)
    cout_reference = b.out(
        "cout_reference", "Coût de référence mensuel",
        f'={refs["perte_valeur_mensuelle"]}+{refs["hm_cost"]}+{refs["om_cost"]}+{refs["ins_cost"]}', MONEY_FMT,
    )

    # ---- Contrôles avant envoi (C1 à C8, section 6.4) -------------------------
    b.section("Contrôles avant envoi (C1 à C8)")
    chdr = b.row
    for j, h in enumerate(["Code", "Libellé", "OK ?", "Détail"]):
        c = ws.cell(row=chdr, column=2 + j, value=h)
        c.font = FONT_HEADER
        c.fill = FILL_SECTION
        c.border = BORDER_THIN
    b.row += 1

    def ctrl_row(code, label, ok_formula, detail_formula):
        r = b.row
        ws.cell(row=r, column=2, value=code).border = BORDER_THIN
        ws.cell(row=r, column=3, value=label).border = BORDER_THIN
        c_ok = ws.cell(row=r, column=4, value=ok_formula)
        c_ok.border = BORDER_THIN
        c_ok.alignment = Alignment(horizontal="center")
        c_det = ws.cell(row=r, column=5, value=detail_formula)
        c_det.border = BORDER_THIN
        c_det.alignment = Alignment(wrap_text=True)
        b.row += 1
        return f"$D${r}"

    c1_ok = ctrl_row(
        "C1_DUREE_CAMPAGNE", "Durée ≤ durée maximale de campagne",
        f'=IF(NOT({refs["is_campaign"]}),TRUE,{refs["duree"]}<={PARAM_CELL[K_MAX_CAMPAIGN_MONTHS]})',
        f'=IF(NOT({refs["is_campaign"]}),"non applicable (offre hors campagne)",'
        f'{refs["duree"]}&" mois (max campagne "&{PARAM_CELL[K_MAX_CAMPAIGN_MONTHS]}&")")',
    )
    c2_ok = ctrl_row(
        "C2_NB_LOCOS", "Nombre de locos ≤ maximum par contrat",
        f'={refs["qte"]}<={PARAM_CELL[K_MAX_LOCOS]}',
        f'={refs["qte"]}&" loco(s) (max "&{PARAM_CELL[K_MAX_LOCOS]}&")"',
    )
    c3_ok = ctrl_row(
        "C3_CLIENT_RATING", "Client à rating élevé : durée courte et paiement d'avance",
        f'=IF(NOT({refs["client_found"]}),FALSE,IF({refs["client_high_risk"]},'
        f'AND({refs["duree"]}<={PARAM_CELL[K_MAX_HIGH_RATING_MONTHS]},{refs["client_pays_advance"]}),TRUE))',
        f'=IF(NOT({refs["client_found"]}),"Client "&{refs["client"]}&" introuvable au référentiel",'
        f'"rating "&{refs["client_rating"]}&" / seuil "&{PARAM_CELL[K_HIGH_RATING_THRESHOLD]})',
    )
    c4_ok = ctrl_row("C4_ASSURANCE_INCLUSE", "Assurance incluse", f'={ins["inc"]}="Oui"', f'={ins["inc"]}="Oui"')
    c5_ok = ctrl_row(
        "C5_GARANTIE_PAIEMENT", "Garantie de paiement (cash deposit ou paiement d'avance)",
        f'=IF(NOT({refs["client_found"]}),FALSE,{refs["client_guarantee"]})',
        f'=IF(NOT({refs["client_found"]}),"Client "&{refs["client"]}&" introuvable au référentiel",'
        f'"cash_deposit="&TEXT({refs["client_cashdeposit"]},"#,##0.00")&", paiement_avance="&{refs["client_pays_advance"]})',
    )
    c6_ok = ctrl_row(
        "C6_AUCUN_PRIX_SOUS_PLANCHER_BP", "Aucun prix sous le plancher BP",
        f'=AND({hm["stat"]}<>"Sous plancher",{om["stat"]}<>"Sous plancher")',
        '="HM/OM comparés au BP"',
    )
    c7_ok = ctrl_row(
        "C7_DL_COUVRE_PERTE_VALEUR", "Le Dry lease couvre la perte de valeur mensuelle",
        f'=IF({dl["stat"]}="Exclue",TRUE,{dl["ret"]}>={refs["perte_valeur_mensuelle"]})',
        f'=IF({dl["stat"]}="Exclue","Dry lease exclu de l\'offre",'
        f'"DL retenu "&TEXT({dl["ret"]},"#,##0.00")&" vs perte de valeur mensuelle "&TEXT({refs["perte_valeur_mensuelle"]},"#,##0.00"))',
    )
    c8_ok = ctrl_row(
        "C8_LOCO_DISPONIBLE_BONNE_SERIE", "Locomotive disponible et de la bonne série",
        "=TRUE", '="Aucune locomotive de flotte affectée (hors contrôle)"',
    )
    apply_bool_cf(ws, f"D{chdr+1}:D{chdr+8}")
    ws.column_dimensions["E"].width = 46

    all_ok = b.out(
        "all_controls_ok", "Tous les contrôles sont-ils OK ?",
        f'=AND({c1_ok},{c2_ok},{c3_ok},{c4_ok},{c5_ok},{c6_ok},{c7_ok},{c8_ok})',
    )
    any_below_floor = b.t(
        "UneBriqueSousPlancher",
        f'=OR({dl["stat"]}="Sous plancher",{hm["stat"]}="Sous plancher",{om["stat"]}="Sous plancher",{ins["stat"]}="Sous plancher")',
    )

    # ---- Niveau de validation (M4-01, section 6.3) ----------------------------
    b.section("Niveau de validation (jamais choisi par le KAM — toujours déduit des faits)")
    niveau = b.out(
        "niveau_validation", "Niveau de validation",
        f'=MAX(IF({remise_globale}>{PARAM_CELL[K_KAM_THRESHOLD]},1,0),'
        f'IF(OR({any_below_floor},NOT({all_ok})),2,0),'
        f'IF({total_retenu_unit}<{cout_reference},3,0))',
        INT_FMT,
    )
    b.out(
        "motifs", "Motif(s)",
        '=_xlfn.TEXTJOIN(CHAR(10),TRUE,'
        f'IF({remise_globale}>{PARAM_CELL[K_KAM_THRESHOLD]},"Remise globale "&TEXT({remise_globale},"0.0%")&" > seuil KAM "&TEXT({PARAM_CELL[K_KAM_THRESHOLD]},"0.0%"),""),'
        f'IF({any_below_floor},"Au moins une brique sous son plancher",""),'
        f'IF(NOT({all_ok}),"Contrôle(s) avant envoi en échec",""),'
        f'IF({total_retenu_unit}<{cout_reference},"Prix retenu "&TEXT({total_retenu_unit},"#,##0.00")&" < coût de référence "&TEXT({cout_reference},"#,##0.00"),""),'
        f'IF(AND({remise_globale}<={PARAM_CELL[K_KAM_THRESHOLD]},NOT({any_below_floor}),{all_ok},{total_retenu_unit}>={cout_reference}),"Dans les règles : validation KAM (niveau 0)",""))',
    )
    ws.row_dimensions[b.row - 1].height = 32
    b.out("envoi_direct", "Envoi direct possible (niveau = 0) ?", f'={niveau}=0')
    apply_bool_cf(ws, ws[b.cells["envoi_direct_local"]].coordinate + ":" + ws[b.cells["envoi_direct_local"]].coordinate)

    # ---- Appendice : détail du calcul (vérification) --------------------------
    b.section("Détail du calcul (vérification — référentiel utilisé)")
    b.out("diag_modele", "Modèle", f'={refs["model_name"]}')
    b.out("diag_tranche", "Tranche de kilométrage (coef. DL / HM / OM)", f'=TEXT({refs["coef_dl"]},"0.00")&" / "&TEXT({refs["coef_hm"]},"0.00")&" / "&TEXT({refs["coef_om"]},"0.00")')
    b.out("diag_grille", "Grille Dry lease — loyer catalogue", f'={refs["grid_rent"]}', MONEY_FMT)
    b.out("diag_bp", "Budget Plan — plancher HM / OM", f'=TEXT({refs["bp_hmfloor"]},"#,##0")&" € / "&TEXT({refs["bp_omfloor"]},"#,##0")&" €"')
    b.out("diag_campagne", "Campagne", f'=IF({refs["is_campaign"]},"Oui — "&{refs["campagne"]},"Non")')
    b.out("diag_vr_debut", "Valeur résiduelle au début", f'={refs["vr_debut"]}', MONEY_FMT)
    b.out("diag_vr_fin", "Valeur résiduelle à la fin", f'={refs["vr_fin"]}', MONEY_FMT)
    b.out("diag_perte_mensuelle", "Perte de valeur mensuelle", f'={refs["perte_valeur_mensuelle"]}', MONEY_FMT)
    b.out("diag_prix_km", "Prix du km supplémentaire", f'={refs["prix_km_suppl"]}', RATE_FMT)

    return dict(
        client=refs["client"], model=refs["model"], qte=refs["qte"],
        dl_ret=dl["ret"], hm_ret=hm["ret"], om_ret=om["ret"], ins_ret=ins["ret"],
        dl_stat=dl["stat"], hm_stat=hm["stat"], om_stat=om["stat"], ins_stat=ins["stat"],
        total_retenu_unit=total_retenu_unit, total_retenu_mensuel=total_retenu_mensuel,
        total_retenu_contrat=total_retenu_contrat, remise_globale=remise_globale,
        niveau_validation=niveau, all_controls_ok=all_ok,
    )


DEFAULTS_A = dict(
    client="CLIENTOK", model="VECTRON", km_an=120_000, duree=24, qte=1,
    date_debut="2026-11-23", age_debut=5, km_cumules_debut=600_000,
    hm8="Non", hm16="Non", campagne=None,
    inc_dl="Oui", inc_hm="Oui", inc_om="Oui", inc_ass="Oui",
    neg_dl=None, neg_hm=None, neg_om=None, neg_ass=None,
)


def full_scenario(ws, r0, label, defaults):
    b, refs = build_engine_block(ws, r0, label, defaults)
    summary = build_lines_and_controls(b, refs)
    return b, summary


# ===========================================================================
# Feuille : Configurateur (scénario A — l'outil principal)
# ===========================================================================
ws = wb.create_sheet(SH_CONFIG := "Configurateur")
ws.sheet_view.showGridLines = False
ws.column_dimensions["A"].width = 38
b_a, sum_a = full_scenario(ws, 1, "A", DEFAULTS_A)
ws.freeze_panes = "A2"

print("Configurateur OK — hauteur du bloc :", b_a.bottom())

# ===========================================================================
# Feuille : Comparateur (M3-04) — A (= Configurateur, en direct) + B + C
# ===========================================================================
ws = wb.create_sheet("Comparateur")
ws.sheet_view.showGridLines = False
set_col_widths(ws, {"A": 38, "B": 22, "C": 22, "D": 22})

row = title_row(ws, 1, "Comparateur de 3 scénarios (M3-04)", span_to="D")
row = note_row(
    ws, row,
    "Scénario A reprend en direct l'onglet Configurateur (lecture seule ici). B et C sont deux "
    "configurateurs complets indépendants, détaillés plus bas sur cette même feuille — changez-y les "
    "entrées pour comparer des hypothèses différentes à prix/contrôles/niveau réels, recalculés en direct.",
    span_to="D",
)
row += 1

SUMMARY_TOP = row
hdr = row
ws.cell(row=hdr, column=1, value="").fill = FILL_SECTION
for j, h in enumerate(["Scénario A (Configurateur)", "Scénario B", "Scénario C"]):
    c = ws.cell(row=hdr, column=2 + j, value=h)
    c.font = FONT_HEADER
    c.fill = FILL_SECTION
    c.border = BORDER_THIN
    c.alignment = Alignment(horizontal="center", wrap_text=True)
row += 1

# Les blocs B et C sont construits plus bas ; on réserve l'espace du tableau
# récapitulatif ici et on le remplit à la fin (une fois leurs adresses connues).
SUMMARY_LABELS = [
    ("client", "Client"),
    ("model", "Modèle"),
    ("qte", "Quantité"),
    ("dl_ret", "Dry lease retenu"),
    ("hm_ret", "Heavy maintenance retenu"),
    ("om_ret", "Operating maintenance retenu"),
    ("ins_ret", "Assurance retenue"),
    ("total_retenu_unit", "Total retenu / loco / mois"),
    ("total_retenu_mensuel", "Total retenu mensuel"),
    ("total_retenu_contrat", "Total retenu sur la durée"),
    ("remise_globale", "Remise globale"),
    ("niveau_validation", "Niveau de validation"),
    ("all_controls_ok", "Tous contrôles OK ?"),
]
summary_rows = {}
for key, label in SUMMARY_LABELS:
    ws.cell(row=row, column=1, value=label).font = FONT_LABEL
    ws.cell(row=row, column=1).border = BORDER_THIN
    summary_rows[key] = row
    row += 1
row += 1

B_START = row
b_b, refs_b = build_engine_block(ws, B_START, "B", DEFAULTS_A)
sum_b = build_lines_and_controls(b_b, refs_b)

C_START = b_b.bottom() + 2
b_c, refs_c = build_engine_block(ws, C_START, "C", DEFAULTS_A)
sum_c = build_lines_and_controls(b_c, refs_c)

# ---- Remplissage du tableau récapitulatif (A = Configurateur, B, C) -------
MONEY_KEYS = {"dl_ret", "hm_ret", "om_ret", "ins_ret", "total_retenu_unit", "total_retenu_mensuel", "total_retenu_contrat"}


def fill_summary_col(col_letter, source_sheet, src):
    for key, _ in SUMMARY_LABELS:
        r = summary_rows[key]
        addr = src[key]
        cell = ws.cell(row=r, column=ord(col_letter) - ord("A") + 1, value=f"={source_sheet}!{addr}" if "!" not in addr else f"={addr}")
        if key in MONEY_KEYS:
            cell.number_format = MONEY_FMT
        elif key == "remise_globale":
            cell.number_format = PCT1_FMT
        elif key == "niveau_validation":
            cell.number_format = INT_FMT
        cell.border = BORDER_THIN


fill_summary_col("B", SH_CONFIG, sum_a)
fill_summary_col("C", "Comparateur", sum_b)
fill_summary_col("D", "Comparateur", sum_c)
apply_bool_cf(ws, f"B{summary_rows['all_controls_ok']}:D{summary_rows['all_controls_ok']}")
ws.conditional_formatting.add(
    f"B{summary_rows['niveau_validation']}:D{summary_rows['niveau_validation']}",
    FormulaRule(formula=[f'B{summary_rows["niveau_validation"]}=0'], fill=PatternFill("solid", fgColor=GREEN_OK)),
)
ws.conditional_formatting.add(
    f"B{summary_rows['niveau_validation']}:D{summary_rows['niveau_validation']}",
    FormulaRule(formula=[f'B{summary_rows["niveau_validation"]}>0'], fill=PatternFill("solid", fgColor=ORANGE_ALERT)),
)
ws.freeze_panes = f"A{SUMMARY_TOP}"

print("Comparateur OK.")

# ===========================================================================
# Feuille : Registre_Derogations (M4-05) — journal manuel
# ===========================================================================
ws = wb.create_sheet("Registre_Derogations")
row = title_row(ws, 1, "Registre des dérogations (M4-05)", span_to="N")
row = note_row(
    ws, row,
    "Journal manuel : il n'y a pas de backend partagé dans ce classeur, donc pas de numérotation "
    "automatique ni de notification — contrairement à PricingHub.Api (POST /api/approval-requests), "
    "qui gère ce registre en base et notifie le validateur. Reportez ici chaque dérogation demandée "
    "dès que l'onglet Configurateur (ou Comparateur) affiche un niveau de validation > 0. "
    "« Validateur » se déduit automatiquement du niveau via l'onglet Delegations.",
    span_to="N",
)
row += 1
hdr_der = row
headers = [
    "N°", "Date demande", "Réf. offre (libre)", "Client", "Modèle", "Niveau", "Montant mensuel retenu",
    "Demandeur", "Justification", "Validateur (auto)", "Statut", "Décidé par", "Date décision", "Commentaire",
]
for j, h in enumerate(headers):
    c = ws.cell(row=hdr_der, column=1 + j, value=h)
    c.font = FONT_HEADER
    c.fill = FILL_SECTION
    c.border = BORDER_THIN
    c.alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")
N_DER_ROWS = 20
for i in range(N_DER_ROWS):
    r = hdr_der + 1 + i
    ws.cell(row=r, column=1, value=i + 1).border = BORDER_THIN
    for col in range(2, 10):
        ws.cell(row=r, column=col).border = BORDER_THIN
        ws.cell(row=r, column=col).fill = FILL_INPUT
    niveau_cell = f"F{r}"
    validateur = ws.cell(
        row=r, column=10,
        value=(
            f'=IF(OR({niveau_cell}="",{niveau_cell}=0),"",'
            f'IFERROR(INDEX({rng(SH_DELEG,"B",*DELEG_RANGE)},MATCH({niveau_cell},{rng(SH_DELEG,"A",*DELEG_RANGE)},0))'
            f'&" — "&INDEX({rng(SH_DELEG,"C",*DELEG_RANGE)},MATCH({niveau_cell},{rng(SH_DELEG,"A",*DELEG_RANGE)},0)),'
            '"aucun validateur configuré pour ce niveau"))'
        ),
    )
    validateur.fill = FILL_TECH
    validateur.border = BORDER_THIN
    statut_cell = ws.cell(row=r, column=11, value="En attente")
    statut_cell.fill = FILL_INPUT
    statut_cell.border = BORDER_THIN
    for col in (13,):
        ws.cell(row=r, column=col).number_format = DATE_FMT
    ws.cell(row=r, column=2).number_format = DATE_FMT
    for col in (12, 14):
        ws.cell(row=r, column=col).border = BORDER_THIN
        ws.cell(row=r, column=col).fill = FILL_INPUT
dv_statut = DataValidation(type="list", formula1='"En attente,Approuvée,Rejetée"', allow_blank=True)
ws.add_data_validation(dv_statut)
dv_statut.add(f"K{hdr_der+1}:K{hdr_der+N_DER_ROWS}")
ws.conditional_formatting.add(
    f"K{hdr_der+1}:K{hdr_der+N_DER_ROWS}",
    FormulaRule(formula=[f'K{hdr_der+1}="Approuvée"'], fill=PatternFill("solid", fgColor=GREEN_OK)),
)
ws.conditional_formatting.add(
    f"K{hdr_der+1}:K{hdr_der+N_DER_ROWS}",
    FormulaRule(formula=[f'K{hdr_der+1}="Rejetée"'], fill=PatternFill("solid", fgColor=RED_BAD)),
)
ws.conditional_formatting.add(
    f"K{hdr_der+1}:K{hdr_der+N_DER_ROWS}",
    FormulaRule(formula=[f'K{hdr_der+1}="En attente"'], fill=PatternFill("solid", fgColor=ORANGE_ALERT)),
)
set_col_widths(ws, {
    "A": 6, "B": 12, "C": 16, "D": 12, "E": 10, "F": 8, "G": 16,
    "H": 16, "I": 28, "J": 28, "K": 13, "L": 16, "M": 13, "N": 24,
})
ws.freeze_panes = f"A{hdr_der+1}"

print("Registre_Derogations OK.")

# ===========================================================================
# Feuille : Lisez-moi
# ===========================================================================
ws = wb.create_sheet("Lisez-moi")
ws.sheet_view.showGridLines = False
set_col_widths(ws, {"A": 95})
row = title_row(ws, 1, "Moteur de pricing Akiem — version Excel", span_to="A")
row = note_row(
    ws, row,
    "Ce classeur porte, formule à formule, le moteur de prix construit jusqu'à ce stade dans PricingHub "
    "(.NET) : les 4 briques (Dry lease, Heavy maintenance, Operating maintenance, Assurance), la valeur "
    "résiduelle VR(âge, km), le prix du km supplémentaire, le niveau de validation (0 à 3) et les 8 "
    "contrôles avant envoi C1-C8 (section 6 du cahier des charges). Aucune valeur n'est câblée en dur : "
    "tout vient des onglets de référentiel (catalogue, référentiel pricing, clients, campagnes), comme "
    "dans PricingHub.",
    span_to="A",
)
row += 1
row = section_row(ws, row, "Structure du classeur")
for text in [
    "• Configurateur — l'outil principal : une offre, en direct (équivalent de POST /api/quotes/calculate).",
    "• Comparateur — scénario A (= Configurateur) + deux scénarios B/C indépendants, et un tableau récapitulatif "
    "côte à côte (M3-04).",
    "• Registre_Derogations — journal manuel des dérogations (M4-05) ; sans backend partagé, la numérotation "
    "et la notification du validateur ne sont pas automatiques, contrairement à PricingHub.Api.",
    "• Catalogue_Modeles, Clients, Campagnes, Delegations — le référentiel métier. Ajoutez des lignes "
    "librement dans les plages prévues (20 lignes chacune, sauf Delegations : 3 niveaux fixes).",
    "• PriceBook_Parametres, PriceBook_TranchesKm, PriceBook_GrilleDryLease, PriceBook_BudgetPlan — le "
    "référentiel pricing versionné (section 6).",
]:
    row = note_row(ws, row, text)
row += 1

row = section_row(ws, row, "Lecture d'un Configurateur/Comparateur")
for text in [
    "• Cases jaunes = à saisir. Cases grises = calculées, ne pas modifier.",
    "• Colonnes J/K (« ZONE TECHNIQUE ») = les étapes intermédiaires du calcul, visibles pour pouvoir "
    "vérifier chaque chiffre pas à pas — à l'image des « étapes de calcul » du prototype Python d'origine. "
    "Ne pas modifier, mais libres à l'audit.",
    "• La colonne « Coût » du tableau des briques n'est JAMAIS montrée au KAM dans le configurateur web "
    "(règle M3-07 : les coûts et marges restent invisibles du KAM). Elle est visible ici car cet outil "
    "Excel est un instrument de pricing interne, pas l'écran KAM — si ce classeur est partagé avec des "
    "KAM, masquez/protégez cette colonne au préalable.",
]:
    row = note_row(ws, row, text)
row += 1

row = section_row(ws, row, "Écarts de périmètre assumés (fidèles à l'état réel de PricingHub aujourd'hui)")
for text in [
    "• Contrôle C1 (durée de campagne) : compare la durée du contrat à la durée maximale GLOBALE "
    "(onglet PriceBook_Parametres), jamais à la durée propre à chaque campagne (onglet Campagnes, colonne "
    "« Durée max. (mois) ») ni aux dates de la campagne — ce champ est stocké mais n'est pas encore lu par "
    "PricingHub.Api lui-même ; ce classeur reproduit fidèlement ce comportement actuel, pas un comportement "
    "idéalisé.",
    "• Trois paramètres (Indexation annuelle, Durée de validité d'une offre, Dry lease minimum) sont "
    "présents dans PricingParameters côté .NET mais ne sont lus par aucun calculateur à ce stade — "
    "affichés ici pour mémoire, sans effet sur le calcul, exactement comme côté .NET.",
    "• Contrôle C8 (locomotive de flotte) : toujours « hors contrôle ». Il n'existe pas d'agrégat "
    "Locomotive/Flotte dans PricingHub à ce stade ; âge et kilométrage sont donc toujours saisis à la main.",
    "• Cas limite d'arrondi (C7) : quand le prix négocié du Dry lease est EXACTEMENT égal à la perte de "
    "valeur mensuelle (cas rarissime), Excel (calcul en virgule flottante binaire) et l'API .NET (calcul en "
    "decimal, via 1m/durée) peuvent diverger d'un cheveu sur ce seul contrôle, à cause d'un écart d'arrondi "
    "de l'ordre de 10⁻²⁶ — sans aucune incidence dès que les deux valeurs diffèrent, même légèrement.",
    "• Pas de génération de PDF, pas de numérotation séquentielle des offres envoyées, pas de CRM "
    "(Opportunity/Pipedrive) : ces fonctionnalités vivent côté API/base de données et n'ont pas de sens "
    "dans un classeur autonome sans backend partagé.",
]:
    row = note_row(ws, row, text)
row += 1

row = section_row(ws, row, "Sources (pour qui veut vérifier formule contre code)")
for text in [
    "PricingHub/src/PricingHub.Domain/Pricing/Calculations/*.cs (les 4 calculateurs + VR + km supplémentaire "
    "+ niveau de validation), PricingHub/src/PricingHub.Domain/Sales/QuoteAggregate/{Quote,QuoteVersion,"
    "QuoteLine}.cs (totaux, statuts de ligne), PricingHub/src/PricingHub.Api/Services/"
    "PreSendControlsEvaluator.cs (C1 à C8).",
]:
    row = note_row(ws, row, text)

for r in range(2, row):
    ws.row_dimensions[r].height = 15 if r < 4 else None

# ===========================================================================
# Finalisation : ordre des feuilles, couleurs d'onglet, feuille active
# ===========================================================================
ORDER = [
    "Lisez-moi", SH_CONFIG, "Comparateur", "Registre_Derogations",
    SH_MODELS, SH_CLIENTS, SH_CAMPAIGNS, SH_DELEG,
    SH_PARAMS, SH_BRACKETS, SH_GRID, SH_BP,
]
wb._sheets = [wb[name] for name in ORDER]  # noqa: SLF001 — ordre d'affichage des onglets

TAB_COLORS = {
    "Lisez-moi": "808080",
    SH_CONFIG: "1F3864",
    "Comparateur": "2E74B5",
    "Registre_Derogations": "BF8F00",
}
for name, color in TAB_COLORS.items():
    wb[name].sheet_properties.tabColor = color

wb.properties.title = "Moteur de pricing Akiem"
wb.properties.subject = "Portage Excel du moteur PricingHub (.NET) — chiffrage, contrôles C1-C8, niveau de validation"
wb.properties.creator = "PricingHub"
wb.active = 1  # Configurateur

wb.save(OUT_PATH)
print("OK:", OUT_PATH)
