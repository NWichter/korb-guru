"""
Demo recipe data -- 3400+ Swiss/European recipes generated from templates.

Data sources:
- Templates inspired by Swiss/European cuisine, open/public-domain recipe
  collections including Chefkoch.de (user-generated), Wikibooks Cookbook
  (CC-BY-SA), and traditional Swiss/European recipes.
  All recipes are static demo data -- no live scraping is performed.
  Ingredient names are mapped to our demo product catalog (demo_data.py).
"""

from __future__ import annotations

import itertools
import re

# ---------------------------------------------------------------------------
# Product names must match demo_data.py exactly
# ---------------------------------------------------------------------------
# fmt: off
PROTEINS = {
    "Pouletbrust 300g":            {"cost": 8.9,  "tags": [],                         "type": "protein"},
    "Rindshackfleisch 500g":       {"cost": 9.5,  "tags": [],                         "type": "protein"},
    "Schweinsgeschnetzeltes 400g": {"cost": 11.9, "tags": [],                         "type": "protein"},
    "Lachs-Filet 200g":            {"cost": 8.5,  "tags": [],                         "type": "protein"},
    "Crevetten 200g":              {"cost": 9.8,  "tags": [],                         "type": "protein"},
    "Kalbsbratwurst 2 Stk":       {"cost": 6.8,  "tags": [],                         "type": "protein"},
    "Cervelat 4 Stk":             {"cost": 5.4,  "tags": [],                         "type": "protein"},
    "Tofu":                        {"cost": 3.5,  "tags": ["vegan", "vegetarian"],    "type": "veggie"},
    "Entenbrust 300g":             {"cost": 12.9, "tags": [],                         "type": "protein"},
    "Forelle Stk":                 {"cost": 7.9,  "tags": [],                         "type": "protein"},
}

VEGETABLES = ["Tomaten 500g", "Peperoni rot 500g", "Zucchetti 500g", "Broccoli 500g", "Rüebli 1kg", "Champignons 250g", "Aubergine Stk", "Zwiebeln 1kg", "Kopfsalat Stk", "Gurke Stk", "Spinat 250g", "Blumenkohl Stk", "Pak Choi 200g"]
CARBS = ["Spaghetti", "Penne", "Kartoffeln 2.5kg", "Reis", "Ruchbrot 500g", "Vollkornbrot 500g", "Quinoa 400g", "Couscous 500g"]
DAIRY_LIST = ["Emmentaler 200g", "Gruyère 200g", "Mozzarella 125g", "Bio Naturjoghurt 500g", "Cottage Cheese 200g", "Quark 250g", "Butter 250g", "Rahm 2dl", "Mascarpone 250g"]
CHEESE_LIST = ["Emmentaler 200g", "Gruyère 200g", "Mozzarella 125g", "Tilsiter 200g", "Appenzeller 200g"]
FRUITS = ["Bananen 1kg", "Äpfel Gala 1kg", "Bio Zitronen 500g", "Erdbeeren 250g", "Heidelbeeren 125g", "Orangen 1kg", "Mango Stk", "Birnen 1kg", "Kiwi 6 Stk", "Ananas Stk", "Himbeeren 125g", "Avocado Stk"]
BREADS = ["Ruchbrot 500g", "Vollkornbrot 500g", "Baguette Stk", "Toastbrot 500g", "Zopf 500g", "Gipfeli 4 Stk", "Tortillas 6 Stk", "Pita-Brot 5 Stk"]
GREENS = ["Kopfsalat Stk", "Nüsslisalat 100g", "Spinat 250g", "Federkohl 200g", "Pak Choi 200g"]

ALL_TAGS = ["gluten-free", "vegan", "vegetarian", "lactose-free", "budget", "family", "quick", "swiss", "italian", "asian", "mexican", "high-protein", "low-carb", "comfort-food"]
DIFFICULTIES = ["einfach", "mittel", "anspruchsvoll"]
# fmt: on

_PROTEINS_LIST = list(PROTEINS.keys())


def _label(name: str) -> str:
    """'Pouletbrust 300g' -> 'Pouletbrust', 'Gurke Stk' -> 'Gurke'."""
    parts = name.split()
    strip_suffixes = {"Stk", "stk"}
    if len(parts) > 1 and (
        any(c.isdigit() for c in parts[-1]) or parts[-1] in strip_suffixes
    ):
        return " ".join(parts[:-1])
    return name


def _ing(name: str, qty: str, unit: str) -> dict:
    return {"name": name, "quantity": qty, "unit": unit}


# ---------------------------------------------------------------------------
# Ingredient builder from spec tokens
# ---------------------------------------------------------------------------
_FIXED = {
    "cream": ("Rahm 2dl", "2", "dl"),
    "butter": ("Butter 250g", "30", "g"),
    "milk": ("Vollmilch 1L", "2", "dl"),
    "onion": ("Zwiebeln 1kg", "1", "Stk"),
    "tomato": ("Tomaten 500g", "300", "g"),
    "potato": ("Kartoffeln 2.5kg", "400", "g"),
    "mushroom": ("Champignons 250g", "200", "g"),
    "lemon": ("Bio Zitronen 500g", "1", "Stk"),
    "salad": ("Kopfsalat Stk", "1", "Stk"),
    "avocado": ("Avocado Stk", "1", "Stk"),
    "spinach": ("Spinat 250g", "200", "g"),
}


def _build_ings(spec: str, ctx: dict[str, str]) -> list[dict]:
    """Build ingredient list from spec like 'protein+carb+veg'."""
    ings: list[dict] = []
    seen: set[str] = set()
    dynamic = {
        "protein": (ctx["protein"], "200", "g"),
        "veg": (ctx["veg"], "300", "g"),
        "carb": (ctx["carb"], "200", "g"),
        "dairy": (ctx["dairy"], "100", "g"),
        "cheese": (ctx["cheese"], "100", "g"),
        "fruit": (ctx["fruit"], "200", "g"),
        "bread": (ctx["bread"], "200", "g"),
    }
    for tok in spec.split("+"):
        if tok in seen:
            continue
        seen.add(tok)
        if tok in dynamic:
            n, q, u = dynamic[tok]
        elif tok in _FIXED:
            n, q, u = _FIXED[tok]
        else:
            continue
        ings.append(_ing(n, q, u))
    return ings


# ---------------------------------------------------------------------------
# Template format: (title, desc, ing_spec, type, tags, cost, time)
# Compact: one tuple per line, ruff-skip formatting
# ---------------------------------------------------------------------------

# fmt: off
_HAUPTGERICHTE = [
    ("{P} mit {C}", "Zartes {P} serviert mit {C} und frischem Gemüse.", "protein+carb+veg", "protein", [], 14.0, 35),
    ("{P}-Pfanne mit {V}", "Schnelle Pfanne mit {P} und {V}.", "protein+veg", "protein", ["quick"], 12.0, 25),
    ("{C} mit {V}-Sauce", "Hausgemachte {V}-Sauce zu {C}.", "carb+veg+dairy", "carb", ["vegetarian"], 8.0, 30),
    ("{P} an Rahmsauce", "Feines {P} in cremiger Rahmsauce mit Champignons.", "protein+cream+mushroom", "protein", [], 18.0, 40),
    ("Überbackene {C} mit {P}", "{C} mit {P} und Käse überbacken.", "protein+carb+cheese", "protein", ["comfort-food", "family"], 15.0, 45),
    ("{P}-Spiess mit {V}", "Grillierte {P}-Spiesse mit {V} und Dip.", "protein+veg", "protein", ["high-protein"], 16.0, 35),
    ("{V}-{P}-Wok", "Asiatischer Wok mit {P} und {V}.", "protein+veg+carb", "protein", ["asian", "quick"], 13.0, 20),
    ("Gefüllte {V} mit {P}", "{V} gefüllt mit {P} und Käse.", "protein+veg+cheese", "protein", ["low-carb"], 14.5, 50),
    ("{C}-Gratin mit {V}", "Cremiges {C}-Gratin mit {V} und Gruyère.", "carb+veg+cheese+cream", "carb", ["vegetarian", "comfort-food"], 11.0, 55),
    ("{P} Stroganoff", "Klassisches Stroganoff mit {P} und Rahmsauce.", "protein+cream+mushroom+carb", "protein", ["comfort-food"], 17.0, 40),
    ("{P}-Geschnetzeltes", "Feines Geschnetzeltes mit {P} und Pilzen.", "protein+mushroom+cream", "protein", ["swiss"], 19.0, 35),
    ("{C} alla {P}", "Italienische {C} mit {P} und Tomaten.", "protein+carb+tomato", "carb", ["italian"], 13.0, 30),
    ("{P} mit Rösti", "Schweizer Rösti mit knusprigem {P}.", "protein+potato+butter", "protein", ["swiss", "gluten-free"], 16.0, 40),
    ("{P}-Bowl mit {C}", "Buddha Bowl mit {P}, {C} und Gemüse.", "protein+carb+veg", "protein", ["high-protein"], 14.0, 30),
    ("{P} Teriyaki", "Japanisch inspiriertes {P} in Teriyaki-Sauce.", "protein+carb+veg", "protein", ["asian"], 15.0, 30),
    ("{V}-Curry mit {C}", "Aromatisches Gemüsecurry mit {V} und {C}.", "veg+carb", "veggie", ["vegetarian", "vegan"], 10.0, 35),
    ("One-Pot {C} mit {P}", "Alles aus einem Topf: {C} mit {P}.", "protein+carb+veg+tomato", "carb", ["quick", "family"], 12.0, 25),
    ("{P} Piccata", "{P} Piccata mit Zitrone und Kapern.", "protein+carb+lemon", "protein", ["italian"], 16.0, 30),
    ("{P}-Ragout mit {C}", "Langsam geschmortes {P}-Ragout.", "protein+carb+veg+tomato", "protein", ["comfort-food"], 18.0, 90),
    ("{P} Tikka Masala", "Indisches {P} in würziger Tomatensauce.", "protein+tomato+cream+carb", "protein", ["asian"], 14.0, 45),
    ("{C}-Auflauf mit {V}", "Herzhafter Auflauf mit {C} und {V}.", "carb+veg+cheese+cream", "carb", ["vegetarian", "family"], 10.0, 50),
    ("{P} Cordon Bleu", "Paniertes {P} gefüllt mit Käse und Schinken.", "protein+cheese+carb", "protein", ["swiss", "comfort-food"], 18.0, 45),
    ("{P} Saltimbocca", "Italienisches {P} mit Salbei.", "protein+carb+butter", "protein", ["italian"], 19.0, 30),
    ("{V}-Lasagne", "Vegetarische Lasagne mit {V} und Béchamel.", "veg+cheese+cream+tomato", "carb", ["vegetarian", "italian"], 12.0, 60),
    ("{P}-{V}-Spiessli", "Bunte Spiessli mit {P} und {V}.", "protein+veg", "protein", ["quick", "high-protein"], 15.0, 25),
    ("{C} Carbonara", "Cremige {C} Carbonara mit Speck und Ei.", "carb+cream+cheese", "carb", ["italian", "quick"], 9.0, 25),
    ("{P}-Burger mit {B}", "Saftiger {P}-Burger mit {B}.", "protein+bread+veg", "protein", ["comfort-food", "family"], 13.0, 30),
    ("{V}-Risotto", "Cremiges Risotto mit {V} und Parmesan.", "veg+cream+cheese", "carb", ["vegetarian", "italian"], 11.0, 40),
    ("Wrap mit {P} und {V}", "Gefüllter Wrap mit {P} und frischem {V}.", "protein+veg+bread", "carb", ["quick"], 10.0, 15),
    ("{P} sweet & sour", "Süss-saures {P} mit Gemüse.", "protein+veg+carb", "protein", ["asian"], 13.0, 30),
    ("{P} Marsala", "{P} in Marsala-Wein-Sauce.", "protein+mushroom+cream", "protein", ["italian"], 17.0, 35),
    ("{P}-{C}-Pfanne", "Schnelle Pfanne mit {P} und {C}.", "protein+carb+veg", "protein", ["quick", "family"], 12.0, 20),
    ("{V}-Tarte", "Rustikale Tarte mit {V} und Ziegenkäse.", "veg+cheese+cream", "veggie", ["vegetarian"], 11.0, 50),
    ("{P} Bourguignon", "Französisch geschmortes {P} in Rotwein.", "protein+veg+carb", "protein", ["comfort-food"], 20.0, 120),
    ("{P} mit {V}-Pesto", "{P} serviert mit hausgemachtem {V}-Pesto.", "protein+veg+carb", "protein", ["quick"], 15.0, 25),
    ("{C} mit {V} und Feta", "Mediterrane {C} mit {V} und Fetakäse.", "carb+veg+cheese", "carb", ["vegetarian"], 9.0, 25),
    ("{P}-Pilaf mit {C}", "Orientalischer Pilaf mit {P}.", "protein+carb+veg", "protein", ["asian"], 14.0, 40),
    ("{P} Tajine", "Marokkanische Tajine mit {P} und Gemüse.", "protein+veg+carb", "protein", ["comfort-food"], 16.0, 60),
    ("{P}-Eintopf", "Herzhafter Eintopf mit {P} und Wurzelgemüse.", "protein+veg+potato", "protein", ["comfort-food", "family"], 13.0, 50),
    ("{C} Primavera mit {V}", "Frühlings-{C} mit buntem {V}.", "carb+veg+cheese", "carb", ["vegetarian", "quick"], 9.0, 20),
    ("{P} mit {V}-Gemüse", "{P} mit gebratenem {V}-Gemüse und Kräutern.", "protein+veg+butter", "protein", ["gluten-free"], 15.0, 30),
    ("{P}-Spiesse Satay", "Indonesische {P}-Spiesse mit Erdnuss-Dip.", "protein+veg+onion", "protein", ["asian", "high-protein"], 14.0, 35),
    ("{C} mit {P}-Sauce", "Cremige {P}-Sauce über {C}.", "protein+carb+cream+onion", "carb", ["comfort-food"], 13.0, 35),
    ("{P} Schnitzel mit {C}", "Knuspriges {P}-Schnitzel mit {C}.", "protein+carb+butter", "protein", ["comfort-food", "family"], 16.0, 40),
    ("{P} à la crème mit {V}", "{P} in Rahm mit {V} und Kräutern.", "protein+veg+cream+butter", "protein", ["swiss"], 18.0, 35),
]

_SALATE = [
    ("{P}-Salat mit {V}", "Frischer Salat mit {P} und {V}.", "protein+salad+veg", "veggie", ["high-protein", "low-carb", "quick"], 12.0, 15),
    ("Gemischter Salat mit {V}", "Bunter Salat mit saisonalem {V}.", "salad+veg", "veggie", ["vegan", "vegetarian", "gluten-free", "lactose-free", "quick", "budget"], 6.0, 10),
    ("{V}-Salat mit {D}", "Knackiger {V}-Salat mit {D}.", "salad+veg+dairy", "veggie", ["vegetarian", "quick"], 8.0, 10),
    ("Caesar Salat mit {P}", "Klassischer Caesar Salat mit {P}.", "protein+salad+cheese+bread", "protein", ["quick"], 13.0, 15),
    ("{F}-{V}-Salat", "Fruchtiger Salat mit {F} und {V}.", "salad+fruit+veg", "veggie", ["vegan", "vegetarian", "quick"], 7.0, 10),
    ("Nüsslisalat mit {P}", "Feiner Nüsslisalat mit warmem {P}.", "protein+salad", "protein", ["quick", "low-carb"], 14.0, 15),
    ("Griechischer Salat mit {V}", "Mediterran mit {V}, Oliven und Feta.", "salad+veg+cheese", "veggie", ["vegetarian", "quick"], 9.0, 15),
    ("Couscous-Salat mit {V}", "Leichter Couscous-Salat mit {V}.", "carb+veg+lemon", "carb", ["vegan", "vegetarian", "quick"], 8.0, 15),
    ("{P}-Reis-Salat", "Sättigender Salat mit {P} und Reis.", "protein+carb+veg", "protein", ["quick"], 11.0, 20),
    ("Caprese mit {V}", "Klassische Caprese mit Mozzarella und {V}.", "veg+cheese", "veggie", ["vegetarian", "italian", "quick", "gluten-free"], 8.0, 10),
    ("Linsensalat mit {V}", "Proteinreicher Linsensalat mit {V}.", "veg+lemon", "veggie", ["vegan", "vegetarian", "high-protein", "budget"], 7.0, 20),
    ("Glasnudelsalat mit {P}", "Asiatischer Glasnudelsalat mit {P}.", "protein+veg", "protein", ["asian", "quick"], 11.0, 15),
    ("Quinoa-Bowl mit {V}", "Superfood-Bowl mit Quinoa und {V}.", "veg+lemon", "veggie", ["vegan", "vegetarian", "high-protein"], 10.0, 20),
    ("{V}-Kartoffelsalat", "Schwäbischer Kartoffelsalat mit {V}.", "potato+veg", "carb", ["vegan", "vegetarian", "budget"], 7.0, 25),
    ("Randen-Salat mit {D}", "Erdiger Randensalat mit cremigem {D}.", "veg+dairy+salad", "veggie", ["vegetarian", "gluten-free"], 8.0, 15),
    ("{P}-Avocado-Salat", "Frischer Salat mit {P} und Avocado.", "protein+avocado+salad+lemon", "protein", ["quick", "low-carb", "gluten-free"], 13.0, 15),
    ("Taboulé mit {V}", "Libanesischer Taboulé mit {V} und Minze.", "carb+veg+lemon+onion", "carb", ["vegan", "vegetarian", "quick"], 7.0, 15),
    ("Orzo-Salat mit {V}", "Mediterraner Orzo-Salat mit {V}.", "carb+veg+cheese+lemon", "carb", ["vegetarian", "italian"], 9.0, 20),
    ("Thai-Salat mit {P}", "Würziger Thai-Salat mit {P} und Limette.", "protein+veg+lemon", "protein", ["asian", "quick", "gluten-free"], 12.0, 15),
    ("Fattoush mit {V}", "Libanesischer Brotsalat mit {V}.", "bread+veg+lemon+onion", "carb", ["vegan", "vegetarian"], 7.0, 15),
]

_SUPPEN = [
    ("{V}-Suppe", "Cremige {V}-Suppe mit Rahm.", "veg+cream+onion", "veggie", ["vegetarian", "comfort-food"], 7.0, 30),
    ("{P}-Suppe mit {V}", "Kräftige Suppe mit {P} und {V}.", "protein+veg+onion", "protein", ["comfort-food"], 11.0, 40),
    ("Minestrone mit {V}", "Italienische Gemüsesuppe mit {V} und Pasta.", "veg+tomato+carb", "veggie", ["vegan", "vegetarian", "italian", "budget"], 7.0, 35),
    ("{V}-Cremesuppe", "Samtige {V}-Cremesuppe mit Croutons.", "veg+cream+butter+bread", "veggie", ["vegetarian", "comfort-food"], 8.0, 30),
    ("Bouillon mit {P}", "Klare Bouillon mit {P}-Einlage.", "protein+veg+onion", "protein", ["quick", "low-carb"], 9.0, 25),
    ("{V}-Kokossuppe", "Exotische Suppe mit {V} und Kokosmilch.", "veg+onion", "veggie", ["vegan", "vegetarian", "asian", "lactose-free"], 8.0, 30),
    ("Gerstensuppe mit {V}", "Bündner Gerstensuppe mit {V}.", "veg+onion+carb", "carb", ["swiss", "comfort-food", "budget"], 6.0, 45),
    ("{P}-Eintopfsuppe", "Deftiger Eintopf mit {P} und Gemüse.", "protein+veg+potato+onion", "protein", ["comfort-food", "family"], 12.0, 50),
    ("{V}-Gazpacho", "Kalte spanische Suppe mit {V}.", "veg+tomato+lemon", "veggie", ["vegan", "vegetarian", "quick", "gluten-free", "lactose-free"], 6.0, 15),
    ("Käsesuppe mit {V}", "Reichhaltige Käsesuppe mit {V}.", "veg+cheese+cream+onion", "veggie", ["vegetarian", "comfort-food", "swiss"], 10.0, 35),
    ("Linsensuppe mit {V}", "Herzhafte Linsensuppe mit {V}.", "veg+onion+lemon", "veggie", ["vegan", "vegetarian", "budget", "high-protein"], 6.0, 40),
    ("{P}-Nudelsuppe", "Wärmende Nudelsuppe mit {P}.", "protein+carb+veg+onion", "protein", ["comfort-food", "family"], 10.0, 30),
    ("French Onion Suppe", "Klassische Zwiebelsuppe mit Käse-Croutons.", "onion+cheese+bread+butter", "veggie", ["vegetarian", "comfort-food"], 8.0, 45),
    ("Tom Kha mit {P}", "Thai-Suppe mit {P} und Galanga.", "protein+mushroom+lemon", "protein", ["asian", "gluten-free"], 13.0, 25),
    ("{V}-Kartoffelsuppe", "Sämige Kartoffelsuppe mit {V}.", "veg+potato+cream+onion", "carb", ["vegetarian", "comfort-food", "budget"], 7.0, 35),
    ("Miso-Suppe mit {V}", "Japanische Miso-Suppe mit {V} und Tofu.", "veg+onion", "veggie", ["vegan", "vegetarian", "asian", "quick"], 5.0, 15),
    ("Kürbissuppe mit {D}", "Samtige Kürbissuppe mit {D}.", "veg+cream+onion+dairy", "veggie", ["vegetarian", "comfort-food"], 7.0, 35),
    ("{P}-Gulaschsuppe", "Würzige Gulaschsuppe mit {P}.", "protein+veg+tomato+onion+potato", "protein", ["comfort-food"], 12.0, 60),
    ("Ribollita mit {V}", "Toskanische Brotsuppe mit {V}.", "veg+bread+tomato+onion", "carb", ["vegan", "vegetarian", "italian", "budget"], 7.0, 40),
    ("{V}-Pho", "Vietnamesische Gemüse-Pho.", "veg+carb+onion+lemon", "veggie", ["vegan", "vegetarian", "asian"], 8.0, 35),
]

_BEILAGEN = [
    ("Gebratene {V}", "Knusprig gebratene {V} mit Kräutern.", "veg+butter", "veggie", ["vegetarian", "quick", "gluten-free"], 5.0, 15),
    ("{C} mit Butter", "Einfache {C} mit zerlassener Butter.", "carb+butter", "carb", ["vegetarian", "quick"], 4.0, 15),
    ("{V}-Gratin", "Überbackenes {V}-Gratin mit Käse.", "veg+cheese+cream", "veggie", ["vegetarian", "comfort-food"], 7.0, 35),
    ("Ofenkartoffeln mit {D}", "Knusprige Ofenkartoffeln mit {D}.", "potato+dairy", "carb", ["vegetarian", "gluten-free"], 6.0, 45),
    ("Gedämpftes {V}", "Sanft gedämpftes {V} mit Zitrone.", "veg+lemon+butter", "veggie", ["vegetarian", "quick", "gluten-free"], 4.0, 10),
    ("{V} im Ofen", "Im Ofen geröstetes {V} mit Olivenöl.", "veg", "veggie", ["vegan", "vegetarian", "gluten-free", "lactose-free", "quick"], 4.0, 25),
    ("Kartoffelstock", "Cremiger Kartoffelstock mit Butter und Milch.", "potato+butter+milk", "carb", ["vegetarian", "comfort-food", "gluten-free"], 5.0, 25),
    ("Pommes frites", "Knusprige Pommes frites aus dem Ofen.", "potato", "carb", ["vegan", "vegetarian", "gluten-free", "lactose-free"], 4.0, 35),
    ("{V}-Püree", "Feines {V}-Püree mit Rahm.", "veg+cream+butter", "veggie", ["vegetarian", "gluten-free", "comfort-food"], 6.0, 25),
    ("Reis mit {V}", "Duftender Reis mit gebratenen {V}.", "carb+veg", "carb", ["vegan", "vegetarian", "quick"], 5.0, 20),
    ("Knoblauch-{C}", "Aromatische {C} mit Knoblauchbutter.", "carb+butter", "carb", ["vegetarian", "quick"], 5.0, 15),
    ("{V} Tempura", "Leicht frittiertes {V} im Teigmantel.", "veg+butter", "veggie", ["vegetarian", "asian"], 6.0, 20),
    ("Polenta mit {D}", "Cremige Polenta mit {D}.", "cream+dairy", "carb", ["vegetarian", "gluten-free", "comfort-food"], 5.0, 20),
    ("Coleslaw mit {V}", "Frischer Krautsalat mit {V}.", "veg+lemon", "veggie", ["vegan", "vegetarian", "quick", "budget"], 4.0, 10),
    ("Rösti", "Klassische Schweizer Rösti mit Butter.", "potato+butter", "carb", ["vegetarian", "swiss", "gluten-free"], 5.0, 30),
    ("Gebratener {C}", "Goldbraun gebratener {C} mit Gewürzen.", "carb+butter+onion", "carb", ["vegetarian", "quick"], 5.0, 15),
    ("{V}-Chips", "Selbstgemachte {V}-Chips aus dem Ofen.", "veg", "veggie", ["vegan", "vegetarian", "gluten-free", "lactose-free", "quick"], 4.0, 30),
    ("Kräuter-{C}", "{C} mit frischen Gartenkräutern.", "carb+butter", "carb", ["vegetarian", "quick"], 5.0, 15),
]

_DESSERTS = [
    ("{F}-Crème", "Luftige Crème mit frischen {F}.", "fruit+cream+dairy", "carb", ["vegetarian", "gluten-free"], 6.0, 20),
    ("{F}-Kuchen", "Saftiger Kuchen mit {F}.", "fruit+butter+dairy", "carb", ["vegetarian"], 8.0, 50),
    ("Schokoladen-Mousse mit {F}", "Dunkle Schokoladen-Mousse mit {F}.", "fruit+cream", "carb", ["vegetarian", "gluten-free"], 7.0, 30),
    ("{F}-Tiramisu", "Schweizer Variante des Tiramisu mit {F}.", "fruit+cream+dairy", "carb", ["vegetarian", "italian"], 9.0, 30),
    ("{D}-Panna-Cotta", "Zarte Panna Cotta mit {D}.", "cream+dairy", "carb", ["vegetarian", "gluten-free", "italian"], 6.0, 25),
    ("Meringue mit {F}", "Knusprige Meringue mit {F} und Rahm.", "fruit+cream", "carb", ["vegetarian", "gluten-free", "swiss"], 7.0, 20),
    ("{F}-Sorbet", "Erfrischendes {F}-Sorbet.", "fruit+lemon", "carb", ["vegan", "vegetarian", "gluten-free", "lactose-free"], 5.0, 15),
    ("{F}-Quark-Dessert", "Leichtes Quark-Dessert mit {F}.", "fruit+dairy", "carb", ["vegetarian", "quick"], 5.0, 10),
    ("Vermicelles", "Klassische Schweizer Vermicelles mit Rahm.", "cream+dairy", "carb", ["vegetarian", "swiss"], 8.0, 30),
    ("Crème brûlée mit {F}", "Französische Crème brûlée mit {F}.", "fruit+cream+dairy", "carb", ["vegetarian", "gluten-free"], 7.0, 40),
    ("{F}-Parfait", "Geschichtetes {F}-Parfait mit Rahm.", "fruit+cream+dairy", "carb", ["vegetarian", "gluten-free"], 7.0, 25),
    ("{F}-Gratin", "Warmes {F}-Gratin mit Sabayon.", "fruit+cream+butter", "carb", ["vegetarian"], 8.0, 30),
    ("Schokoladen-Fondant mit {F}", "Warmer Schoko-Fondant mit {F}.", "fruit+cream+butter", "carb", ["vegetarian"], 9.0, 25),
    ("{F}-Eis", "Selbstgemachtes {F}-Eis.", "fruit+cream+dairy", "carb", ["vegetarian", "gluten-free"], 6.0, 20),
]

_FRUEHSTUECK = [
    ("Birchermüesli mit {F}", "Klassisches Birchermüesli mit {F}.", "fruit+dairy", "carb", ["vegetarian", "swiss", "quick"], 5.0, 10),
    ("{F}-Smoothie-Bowl", "Bunte Smoothie-Bowl mit {F} und Toppings.", "fruit+dairy", "carb", ["vegetarian", "quick"], 6.0, 10),
    ("Rührei mit {V}", "Fluffiges Rührei mit {V}.", "veg+butter+dairy", "protein", ["vegetarian", "quick", "gluten-free", "low-carb"], 6.0, 10),
    ("{B} mit {D}", "Frisches {B} mit {D}.", "bread+dairy", "carb", ["vegetarian", "quick"], 5.0, 5),
    ("Porridge mit {F}", "Warmer Haferbrei mit {F}.", "fruit+milk", "carb", ["vegetarian", "vegan", "budget", "quick"], 4.0, 10),
    ("Zopf mit {D}", "Frischer Zopf mit {D} und Konfitüre.", "bread+dairy", "carb", ["vegetarian", "swiss"], 6.0, 5),
    ("{F}-Pancakes", "Fluffige Pancakes mit {F}.", "fruit+butter+milk", "carb", ["vegetarian"], 7.0, 20),
    ("Omelette mit {V}", "Französisches Omelette mit {V} und Käse.", "veg+cheese+butter", "protein", ["vegetarian", "quick", "gluten-free"], 7.0, 15),
    ("Avocado-Toast mit {V}", "Vollkorn-Toast mit Avocado und {V}.", "bread+veg+lemon", "carb", ["vegan", "vegetarian", "quick"], 6.0, 10),
    ("{D} mit Granola und {F}", "{D} mit knusprigem Granola und {F}.", "dairy+fruit", "carb", ["vegetarian", "quick"], 5.0, 5),
    ("{F}-Overnight-Oats", "Über Nacht eingeweichte Haferflocken mit {F}.", "fruit+dairy+milk", "carb", ["vegetarian", "quick"], 4.0, 5),
    ("French Toast mit {F}", "Gebackener French Toast mit {F}.", "bread+fruit+butter+milk", "carb", ["vegetarian"], 7.0, 15),
    ("Shakshuka-Frühstück mit {V}", "Orientalisches Eiergericht mit {V}.", "veg+tomato+onion+bread", "protein", ["vegetarian"], 8.0, 25),
]

_SNACKS = [
    ("{V}-Sticks mit Dip", "Knackige {V}-Sticks mit Kräuterquark.", "veg+dairy", "veggie", ["vegetarian", "quick", "budget", "gluten-free", "low-carb"], 4.0, 5),
    ("{F}-{D}-Snack", "Schneller Snack mit {F} und {D}.", "fruit+dairy", "carb", ["vegetarian", "quick", "budget"], 4.0, 5),
    ("Bruschetta mit {V}", "Geröstetes Brot mit {V}.", "bread+veg+cheese", "carb", ["vegetarian", "italian", "quick"], 5.0, 10),
    ("{V}-Muffins", "Herzhafte Muffins mit {V} und Käse.", "veg+cheese+butter", "carb", ["vegetarian"], 6.0, 30),
    ("Hummus mit {V}", "Cremiger Hummus mit {V}-Sticks.", "veg+lemon", "veggie", ["vegan", "vegetarian", "quick", "budget", "gluten-free"], 4.0, 10),
    ("{D}-Dip mit {B}", "Cremiger {D}-Dip mit {B}.", "dairy+bread", "carb", ["vegetarian", "quick"], 5.0, 10),
    ("Mini-Pizza mit {V}", "Kleine Pizzen mit {V} und Käse.", "bread+veg+cheese", "carb", ["vegetarian", "family", "quick"], 7.0, 20),
    ("{F}-Riegel", "Selbstgemachte {F}-Energieriegel.", "fruit", "carb", ["vegan", "vegetarian", "quick", "budget"], 3.0, 20),
    ("Käse-{V}-Spiessli", "Bunte Spiessli mit Käse und {V}.", "veg+cheese", "veggie", ["vegetarian", "quick", "gluten-free"], 5.0, 10),
    ("Guacamole mit {B}", "Frische Guacamole mit {B}.", "veg+lemon+bread", "veggie", ["vegan", "vegetarian", "mexican", "quick"], 6.0, 10),
    ("{V}-Quesadilla", "Knusprige Quesadilla mit {V} und Käse.", "veg+cheese+bread", "carb", ["vegetarian", "mexican", "quick"], 7.0, 15),
    ("{F}-Joghurt-Eis", "Gefrorener {F}-Joghurt am Stiel.", "fruit+dairy", "carb", ["vegetarian", "quick"], 4.0, 10),
    ("Baba Ganoush mit {B}", "Rauchiges Auberginen-Dip mit {B}.", "veg+lemon+bread", "veggie", ["vegan", "vegetarian", "quick"], 5.0, 15),
]

_SWISS = [
    ("Fondue mit {B}", "Original Schweizer Käsefondue mit {B}.", "cheese+bread+lemon", "protein", ["swiss", "vegetarian", "comfort-food", "family"], 18.0, 30),
    ("Raclette mit {V}", "Raclette mit {V} und Kartoffeln.", "cheese+potato+veg", "protein", ["swiss", "vegetarian", "gluten-free", "family"], 16.0, 45),
    ("Älplermagronen mit {P}", "Schweizer Älplermagronen mit {P}.", "carb+cheese+cream+protein", "carb", ["swiss", "comfort-food"], 12.0, 35),
    ("Berner Platte mit {P}", "Deftige Berner Platte mit {P} und Sauerkraut.", "protein+potato+veg", "protein", ["swiss", "comfort-food", "family"], 22.0, 60),
    ("Rösti mit {P}", "Knusprige Rösti mit {P}.", "potato+butter+protein", "protein", ["swiss", "gluten-free"], 14.0, 35),
    ("Zürcher Geschnetzeltes mit {P}", "Rahm-Geschnetzeltes Zürcher Art mit {P}.", "protein+cream+mushroom+butter", "protein", ["swiss"], 20.0, 35),
    ("Capuns mit {P}", "Bündner Capuns mit {P} und Käse.", "protein+cheese+cream", "protein", ["swiss", "comfort-food"], 15.0, 50),
    ("Cholera mit {V}", "Walliser Cholera-Kuchen mit {V}.", "veg+cheese+potato", "carb", ["swiss", "vegetarian"], 10.0, 60),
    ("Maluns mit {D}", "Bündner Maluns mit Apfelmus und {D}.", "potato+butter+dairy", "carb", ["swiss", "vegetarian", "gluten-free"], 8.0, 40),
    ("Ghackets mit Hörnli und {V}", "Hackfleisch mit Hörnli und {V}.", "carb+veg+cheese", "carb", ["swiss", "comfort-food", "family", "budget"], 10.0, 30),
    ("Papet Vaudois mit {P}", "Waadtländer Lauchgemüse mit {P}.", "protein+veg+cream", "protein", ["swiss"], 14.0, 45),
    ("Chäschüechli mit {V}", "Schweizer Chäschüechli mit {V}-Salat.", "cheese+cream+butter+salad+veg", "carb", ["swiss", "vegetarian"], 9.0, 40),
    ("Birchermüesli Deluxe mit {F}", "Birchermüesli mit Rahm und {F}.", "fruit+dairy+cream", "carb", ["swiss", "vegetarian", "quick"], 7.0, 10),
    ("Bündnerfleisch mit {V}", "Bündnerfleisch an {V}-Salat.", "veg+lemon", "protein", ["swiss", "quick", "gluten-free", "high-protein"], 12.0, 10),
    ("Sonntagszopf mit {D}", "Sonntagszopf mit {D} und Konfitüre.", "bread+dairy+butter", "carb", ["swiss", "vegetarian"], 6.0, 5),
    ("Basler Mehlsuppe mit {V}", "Traditionelle Basler Mehlsuppe mit {V}.", "veg+butter+onion+cheese", "carb", ["swiss", "comfort-food"], 7.0, 40),
    ("Zürigschnetzlets mit {C}", "Zürcher Geschnetzeltes mit {C}.", "protein+carb+cream+mushroom", "protein", ["swiss", "comfort-food"], 19.0, 35),
    ("Engadiner Nusstorte mit {D}", "Engadiner Nusstorte mit {D}.", "butter+cream+dairy", "carb", ["swiss", "vegetarian"], 12.0, 60),
]

_INTERNATIONAL = [
    ("Pad Thai mit {P}", "Thailändisches Pad Thai mit {P}.", "protein+carb+veg+lemon", "carb", ["asian", "quick"], 13.0, 25),
    ("{P}-Tacos mit {V}", "Mexikanische Tacos mit {P} und {V}.", "protein+veg+lemon", "protein", ["mexican", "quick"], 12.0, 20),
    ("Sushi-Bowl mit {P}", "Dekonstruierte Sushi-Bowl mit {P}.", "protein+carb+veg", "protein", ["asian"], 14.0, 30),
    ("{P}-Gyros mit {V}", "Griechischer Gyros mit {P} und Tzatziki.", "protein+veg+bread+dairy", "protein", ["quick"], 12.0, 25),
    ("Bibimbap mit {P}", "Koreanischer Bibimbap mit {P} und Gemüse.", "protein+carb+veg", "protein", ["asian"], 14.0, 35),
    ("{P} Tikka mit {C}", "Indisches Tikka mit {P} und {C}.", "protein+carb+cream+tomato", "protein", ["asian"], 13.0, 40),
    ("Burrito mit {P} und {V}", "Mexikanischer Burrito mit {P} und {V}.", "protein+veg+carb", "carb", ["mexican", "family"], 11.0, 25),
    ("Pho mit {P}", "Vietnamesische Pho-Suppe mit {P}.", "protein+carb+veg+lemon", "protein", ["asian"], 12.0, 45),
    ("{P} Satay mit {V}", "Indonesische Satay-Spiesse mit Erdnusssauce.", "protein+veg", "protein", ["asian", "gluten-free"], 13.0, 30),
    ("Falafel mit {V}", "Knusprige Falafel mit {V} und Hummus.", "veg+bread+lemon", "veggie", ["vegan", "vegetarian", "budget"], 8.0, 30),
    ("Ramen mit {P}", "Japanische Ramen mit {P}.", "protein+carb+veg", "protein", ["asian", "comfort-food"], 13.0, 40),
    ("Quesadilla mit {P}", "Käse-Quesadilla mit {P} und Salsa.", "protein+cheese+veg", "protein", ["mexican", "quick"], 10.0, 15),
    ("Thai-Curry mit {P}", "Rotes Thai-Curry mit {P} und Gemüse.", "protein+veg+cream+carb", "protein", ["asian"], 14.0, 30),
    ("Empanadas mit {P}", "Südamerikanische Empanadas mit {P}-Füllung.", "protein+veg+onion", "protein", ["mexican", "comfort-food"], 11.0, 45),
    ("{P} Teriyaki Bowl", "Japanische Teriyaki-Bowl mit {P} und Reis.", "protein+carb+veg", "protein", ["asian", "quick"], 13.0, 25),
    ("Shakshuka mit {V}", "Nordafrikanische Shakshuka mit {V}.", "veg+tomato+onion+bread", "veggie", ["vegetarian"], 8.0, 25),
    ("Nasi Goreng mit {P}", "Indonesischer gebratener Reis mit {P}.", "protein+carb+veg", "carb", ["asian", "quick"], 12.0, 20),
    ("Enchiladas mit {P}", "Mexikanische Enchiladas mit {P} und Käse.", "protein+cheese+tomato+veg", "protein", ["mexican", "comfort-food", "family"], 13.0, 40),
    ("Dhal mit {V}", "Indisches Linsengericht mit {V}.", "veg+tomato+onion+carb", "veggie", ["vegan", "vegetarian", "asian", "budget"], 7.0, 35),
    ("Spring Rolls mit {V}", "Frische Sommerrollen mit {V}.", "veg+lemon", "veggie", ["vegan", "vegetarian", "asian", "quick"], 7.0, 20),
    ("Japanisches Curry mit {P}", "Mildes japanisches Curry mit {P}.", "protein+carb+veg+onion", "protein", ["asian", "comfort-food"], 12.0, 40),
    ("Banh Mi mit {P}", "Vietnamesisches Baguette-Sandwich mit {P}.", "protein+bread+veg+lemon", "protein", ["asian", "quick"], 11.0, 20),
    ("Kimchi-Fried-Rice mit {P}", "Gebratener Reis mit Kimchi und {P}.", "protein+carb+veg+onion", "carb", ["asian", "quick"], 11.0, 15),
    ("Moussaka mit {V}", "Griechische Moussaka mit {V}.", "veg+cheese+cream+tomato+onion", "veggie", ["vegetarian", "comfort-food"], 12.0, 60),
    ("Poke Bowl mit {P}", "Hawaiianische Poke Bowl mit {P}.", "protein+carb+veg+avocado", "protein", ["asian", "quick"], 14.0, 20),
]

_BUDGET = [
    ("{C} aglio e olio", "Einfache {C} mit Knoblauch und Olivenöl.", "carb+onion", "carb", ["vegan", "vegetarian", "budget", "quick", "italian", "lactose-free"], 4.0, 15),
    ("{V}-Omelette", "Schnelles Omelette mit {V}.", "veg+butter", "protein", ["vegetarian", "budget", "quick", "gluten-free", "low-carb"], 5.0, 10),
    ("Reis mit {V}", "Einfacher Reis mit gebratenem {V}.", "carb+veg", "carb", ["vegan", "vegetarian", "budget", "quick"], 5.0, 20),
    ("{C} mit {D}", "Einfache {C} mit {D}.", "carb+dairy", "carb", ["vegetarian", "budget", "quick"], 5.0, 15),
    ("{V}-Pfanne mit Ei", "Bunte {V}-Pfanne mit Spiegelei.", "veg+butter+onion", "veggie", ["vegetarian", "budget", "quick", "gluten-free"], 5.0, 15),
    ("Brot-Salat mit {V}", "Toskanischer Brotsalat mit {V}.", "bread+veg+tomato+lemon", "carb", ["vegan", "vegetarian", "budget", "italian"], 5.0, 15),
    ("{V}-Flammkuchen", "Einfacher Flammkuchen mit {V} und Rahm.", "veg+cream+onion", "carb", ["vegetarian", "budget"], 6.0, 25),
    ("Kartoffelsuppe mit {V}", "Günstige Kartoffelsuppe mit {V}.", "potato+veg+onion+cream", "carb", ["vegetarian", "budget", "comfort-food"], 5.0, 30),
    ("{C} mit Tomatensauce", "Klassische {C} mit einfacher Tomatensauce.", "carb+tomato+onion", "carb", ["vegan", "vegetarian", "budget", "quick", "lactose-free"], 4.0, 20),
    ("Fried Rice mit {V}", "Gebratener Reis mit {V} und Sojasauce.", "carb+veg+onion", "carb", ["vegan", "vegetarian", "budget", "asian", "quick"], 5.0, 15),
    ("Rösti mit {V}", "Budget-Rösti mit {V} und Spiegelei.", "potato+veg+butter", "carb", ["vegetarian", "budget", "swiss", "gluten-free"], 5.0, 25),
    ("{V}-Rührei auf {B}", "Schnelles Rührei mit {V} auf {B}.", "veg+butter+bread", "protein", ["vegetarian", "budget", "quick"], 5.0, 10),
]

# ---------------------------------------------------------------------------
# New categories: smoothies, salad_bowls, wraps, one_pot, grill
# ---------------------------------------------------------------------------

_SMOOTHIES = [
    ("{F}-Smoothie", "Cremiger Smoothie mit {F} und Joghurt.", "fruit+dairy", "carb", ["vegetarian", "quick"], 5.0, 5),
    ("{F}-Power-Smoothie", "Energiegeladener Smoothie mit {F}.", "fruit+dairy", "carb", ["vegetarian", "quick", "high-protein"], 6.0, 5),
    ("Grüner Smoothie mit {F}", "Gesunder grüner Smoothie mit {F} und Spinat.", "fruit+spinach", "veggie", ["vegan", "vegetarian", "quick", "lactose-free"], 5.0, 5),
    ("{F}-Protein-Shake", "Proteinreicher Shake mit {F} und Quark.", "fruit+dairy", "carb", ["vegetarian", "quick", "high-protein"], 6.0, 5),
    ("{F}-Kokos-Smoothie", "Tropischer Smoothie mit {F} und Kokosmilch.", "fruit", "carb", ["vegan", "vegetarian", "quick", "lactose-free"], 5.0, 5),
    ("{F}-Hafermilch-Smoothie", "Veganer Smoothie mit {F} und Hafermilch.", "fruit", "carb", ["vegan", "vegetarian", "quick", "lactose-free"], 5.0, 5),
    ("{F}-Beeren-Mix-Smoothie", "Bunter Beeren-Smoothie mit {F}.", "fruit+dairy", "carb", ["vegetarian", "quick"], 5.0, 5),
    ("{F}-Matcha-Smoothie", "Matcha-Smoothie mit {F} und Mandelmilch.", "fruit", "carb", ["vegan", "vegetarian", "quick", "lactose-free"], 6.0, 5),
    ("{F}-Joghurt-Shake", "Erfrischender Joghurt-Shake mit {F}.", "fruit+dairy", "carb", ["vegetarian", "quick"], 5.0, 5),
    ("{F}-Spinat-Power-Smoothie", "Grüner Power-Smoothie mit {F} und Spinat.", "fruit+spinach+dairy", "veggie", ["vegetarian", "quick", "high-protein"], 6.0, 5),
]

_SALAD_BOWLS = [
    ("{P}-Buddha-Bowl mit {V}", "Bunte Buddha-Bowl mit {P} und {V}.", "protein+veg+carb+avocado", "protein", ["high-protein", "quick"], 14.0, 20),
    ("Poke-Bowl mit {P} und {V}", "Hawaiianische Poke-Bowl mit {P}.", "protein+carb+veg+lemon", "protein", ["asian", "quick"], 14.0, 20),
    ("{V}-Grain-Bowl", "Nährstoffreiche Grain-Bowl mit {V}.", "veg+carb+lemon+dairy", "carb", ["vegetarian", "high-protein"], 10.0, 25),
    ("Falafel-Bowl mit {V}", "Falafel-Bowl mit {V} und Hummus.", "veg+carb+lemon", "veggie", ["vegan", "vegetarian"], 9.0, 25),
    ("{P}-Teriyaki-Bowl mit {V}", "Teriyaki-Bowl mit {P} und {V}.", "protein+carb+veg", "protein", ["asian", "quick"], 13.0, 25),
    ("Mediterranean-Bowl mit {V}", "Mediterrane Bowl mit {V} und Feta.", "veg+carb+cheese+lemon", "carb", ["vegetarian"], 10.0, 20),
    ("{P}-Burrito-Bowl", "Mexikanische Burrito-Bowl mit {P}.", "protein+carb+veg+avocado", "protein", ["mexican"], 13.0, 25),
    ("Acai-Bowl mit {F}", "Brasilianische Acai-Bowl mit {F}.", "fruit+dairy", "carb", ["vegetarian", "quick"], 8.0, 10),
    ("{V}-Rainbow-Bowl", "Bunte Rainbow-Bowl mit {V} und Dressing.", "veg+carb+lemon+avocado", "veggie", ["vegan", "vegetarian", "quick"], 9.0, 20),
    ("{P}-Protein-Bowl mit {C}", "Proteinreiche Bowl mit {P} und {C}.", "protein+carb+veg+dairy", "protein", ["high-protein"], 14.0, 25),
]

_WRAPS = [
    ("{P}-Wrap mit {V}", "Knuspriger Wrap mit {P} und {V}.", "protein+veg+bread+dairy", "carb", ["quick"], 10.0, 15),
    ("{V}-Hummus-Wrap", "Veganer Wrap mit {V} und Hummus.", "veg+bread+lemon", "carb", ["vegan", "vegetarian", "quick", "budget"], 7.0, 10),
    ("{P}-Caesar-Wrap", "Caesar-Wrap mit {P} und Parmesan.", "protein+bread+cheese+salad", "protein", ["quick"], 11.0, 15),
    ("Falafel-Wrap mit {V}", "Falafel-Wrap mit {V} und Tahini.", "veg+bread+lemon", "veggie", ["vegan", "vegetarian", "quick"], 8.0, 15),
    ("{P}-Avocado-Wrap", "Frischer Wrap mit {P} und Avocado.", "protein+bread+avocado+veg", "protein", ["quick"], 12.0, 15),
    ("{V}-Käse-Wrap", "Wrap mit {V} und geschmolzenem Käse.", "veg+bread+cheese", "carb", ["vegetarian", "quick"], 8.0, 10),
    ("{P}-BBQ-Wrap", "BBQ-Wrap mit {P} und Coleslaw.", "protein+bread+veg", "protein", ["quick", "comfort-food"], 11.0, 15),
    ("Griechischer Wrap mit {P}", "Wrap mit {P}, Tzatziki und Oliven.", "protein+bread+veg+dairy", "protein", ["quick"], 11.0, 15),
    ("{V}-Spinat-Wrap", "Grüner Wrap mit {V} und Spinat.", "veg+spinach+bread+cheese", "carb", ["vegetarian", "quick"], 8.0, 10),
    ("Breakfast-Wrap mit {V}", "Frühstücks-Wrap mit {V} und Ei.", "veg+bread+butter+cheese", "protein", ["vegetarian", "quick"], 8.0, 15),
]

_ONE_POT = [
    ("One-Pot-Pasta mit {V}", "Alles-aus-einem-Topf Pasta mit {V}.", "carb+veg+tomato+onion+cheese", "carb", ["vegetarian", "quick", "family"], 8.0, 25),
    ("One-Pot {P}-Reis", "Reis mit {P} aus einem Topf.", "protein+carb+veg+onion", "protein", ["quick", "family"], 12.0, 30),
    ("One-Pot {V}-Curry", "Schnelles Gemüsecurry aus einem Topf.", "veg+carb+cream+onion", "veggie", ["vegetarian", "vegan", "asian", "quick"], 9.0, 25),
    ("One-Pot {P}-Eintopf", "Herzhafter Eintopf mit {P}.", "protein+veg+potato+onion", "protein", ["comfort-food", "family"], 13.0, 40),
    ("One-Pot Chili mit {P}", "Feuriges One-Pot Chili mit {P}.", "protein+veg+tomato+onion+carb", "protein", ["mexican", "comfort-food", "family"], 12.0, 35),
    ("One-Pot Risotto mit {V}", "Cremiges Risotto aus einem Topf mit {V}.", "veg+carb+cream+cheese+onion", "carb", ["vegetarian", "italian"], 10.0, 30),
    ("One-Pot {P} mit {C}", "Einfaches One-Pot Gericht mit {P} und {C}.", "protein+carb+veg+tomato", "protein", ["quick", "family"], 11.0, 25),
    ("One-Pot Linsen mit {V}", "Linsengericht mit {V} aus einem Topf.", "veg+onion+tomato+carb", "veggie", ["vegan", "vegetarian", "budget"], 7.0, 30),
    ("One-Pot Thai-Suppe mit {P}", "Thai-Suppe mit {P} aus einem Topf.", "protein+veg+carb+onion", "protein", ["asian", "quick"], 12.0, 25),
    ("One-Pot {V}-Bolognese", "Vegane Bolognese aus einem Topf mit {V}.", "veg+carb+tomato+onion", "carb", ["vegan", "vegetarian", "italian", "family"], 8.0, 30),
    ("One-Pot Mac & Cheese mit {V}", "Cremige Mac & Cheese mit {V}.", "carb+cheese+cream+veg+milk", "carb", ["vegetarian", "comfort-food", "family"], 9.0, 20),
    ("One-Pot Couscous mit {P}", "Schneller Couscous mit {P} und Gemüse.", "protein+carb+veg+onion+lemon", "carb", ["quick"], 11.0, 20),
]

_GRILL = [
    ("Grilliertes {P} mit {V}", "Vom Grill: {P} mit {V} und Marinade.", "protein+veg+lemon", "protein", ["high-protein", "gluten-free"], 15.0, 25),
    ("{P}-Spiess vom Grill", "Bunte {P}-Spiesse mit Gemüse vom Grill.", "protein+veg+onion", "protein", ["high-protein", "quick"], 14.0, 20),
    ("Grill-{V} mit {D}", "Gegrilltes {V} mit {D}-Dip.", "veg+dairy+lemon", "veggie", ["vegetarian", "gluten-free", "quick"], 7.0, 15),
    ("{P}-Burger vom Grill", "Saftiger {P}-Burger frisch vom Grill.", "protein+bread+veg+cheese", "protein", ["comfort-food", "family"], 14.0, 25),
    ("Grill-{V}-Salat", "Warmer Grillgemüse-Salat mit {V}.", "veg+lemon+cheese", "veggie", ["vegetarian", "gluten-free", "quick"], 8.0, 20),
    ("{P} mit Kräuterbutter", "Gegrilltes {P} mit hausgemachter Kräuterbutter.", "protein+butter+lemon", "protein", ["gluten-free"], 16.0, 25),
    ("Grill-Platte mit {P}", "Gemischte Grillplatte mit {P} und Beilagen.", "protein+veg+bread+potato", "protein", ["family", "comfort-food"], 18.0, 35),
    ("{V} im Grillkorb", "Im Grillkorb gegartes {V} mit Olivenöl.", "veg+lemon", "veggie", ["vegan", "vegetarian", "gluten-free", "lactose-free", "quick"], 6.0, 15),
    ("Cervelat vom Grill mit {V}", "Klassischer Cervelat vom Grill mit {V}.", "protein+veg+bread", "protein", ["swiss", "quick", "family"], 8.0, 15),
    ("{P}-Steak vom Grill mit {C}", "Saftiges {P}-Steak mit {C} als Beilage.", "protein+carb+butter", "protein", ["high-protein"], 18.0, 25),
]
# fmt: on


# ---------------------------------------------------------------------------
# Variant generator — enumerates unique title combos via cartesian product
# ---------------------------------------------------------------------------

# Map format keys to their swap pools
_POOL = {
    "P": _PROTEINS_LIST,
    "V": VEGETABLES,
    "C": CARBS,
    "D": DAIRY_LIST,
    "F": FRUITS,
    "B": BREADS,
}
# Keys that also affect ingredients
_CTX_KEY = {
    "P": "protein",
    "V": "veg",
    "C": "carb",
    "D": "dairy",
    "F": "fruit",
    "B": "bread",
}
_TITLE_KEYS_RE = re.compile(r"\{([PVCDFB])\}")


def _difficulty_from_time(time_min: int) -> str:
    """Derive difficulty from prep time."""
    if time_min <= 20:
        return "einfach"
    if time_min <= 45:
        return "mittel"
    return "anspruchsvoll"


def _servings_from_type(rtype: str, idx: int) -> int:
    """Deterministic servings 1-6 based on recipe type and index."""
    if rtype in ("carb", "protein"):
        base = [2, 4, 3, 4, 2, 6]
    elif rtype == "veggie":
        base = [2, 2, 4, 3, 1, 2]
    else:
        base = [2, 3, 4, 2, 1, 4]
    return base[idx % len(base)]


def _gen(templates: list[tuple], n_variants: int) -> list[dict]:
    """Generate up to *n_variants* unique recipes per template."""
    out: list[dict] = []
    for t in templates:
        title_f, desc_f, spec, rtype, tags, cost, time_min = t
        # Detect which swap keys appear in the title
        keys_in_title = list(dict.fromkeys(_TITLE_KEYS_RE.findall(title_f)))
        if not keys_in_title:
            # Static title (e.g. "Pommes frites") — emit once
            keys_in_title = []

        # Build pools for title-relevant keys
        pools = [_POOL.get(k, ["?"]) for k in keys_in_title]

        # Also need pools for non-title keys (for ingredient variety)
        all_keys = ["P", "V", "C", "D", "F", "B"]
        non_title_keys = [k for k in all_keys if k not in keys_in_title]

        if pools:
            combos = list(itertools.product(*pools))
        else:
            combos = [()]  # one combo for static titles

        count = 0
        for ci, combo in enumerate(combos):
            if count >= n_variants:
                break
            # Build the swap context
            swap = {}
            for ki, k in enumerate(keys_in_title):
                swap[k] = combo[ki]
            # Fill non-title keys deterministically
            for k in non_title_keys:
                pool = _POOL.get(k, ["?"])
                swap[k] = pool[ci % len(pool)]
            # Always need cheese
            swap.setdefault("cheese", CHEESE_LIST[ci % len(CHEESE_LIST)])

            fmt = {k: _label(v) for k, v in swap.items()}
            ctx = {
                "protein": swap.get("P", _PROTEINS_LIST[0]),
                "veg": swap.get("V", VEGETABLES[0]),
                "carb": swap.get("C", CARBS[0]),
                "dairy": swap.get("D", DAIRY_LIST[0]),
                "cheese": swap.get("cheese", CHEESE_LIST[0]),
                "fruit": swap.get("F", FRUITS[0]),
                "bread": swap.get("B", BREADS[0]),
            }

            try:
                title = title_f.format(**fmt)
                desc = desc_f.format(**fmt)
            except KeyError:
                continue

            pinfo = PROTEINS.get(
                ctx["protein"], {"cost": 5.0, "tags": [], "type": "protein"}
            )
            adj_cost = round(max(3.0, cost + (pinfo["cost"] - 8.0) * 0.5), 1)
            adj_time = max(5, time_min + (count % 5 - 2) * 5)

            merged: list[str] = list(tags) + pinfo.get("tags", [])
            seen_t: set[str] = set()
            utags = [tg for tg in merged if not (tg in seen_t or seen_t.add(tg))]  # type: ignore[func-returns-value]

            final_type = rtype
            if rtype == "protein":
                final_type = pinfo.get("type", rtype)
            if ("vegan" in tags or "vegetarian" in tags) and ctx["protein"] == "Tofu":
                final_type = rtype

            out.append(
                {
                    "title": title,
                    "description": desc,
                    "cost": adj_cost,
                    "time_minutes": adj_time,
                    "type": final_type,
                    "tags": utags,
                    "ingredients": _build_ings(spec, ctx),
                    "difficulty": _difficulty_from_time(adj_time),
                    "servings": _servings_from_type(rtype, count),
                }
            )
            count += 1
    return out


def _generate_all() -> list[dict]:
    """Generate 3400+ recipes, deduplicate by title."""
    # (templates, variants_per_template)
    cats: list[tuple[list[tuple], int]] = [
        (_HAUPTGERICHTE, 27),  # 45 tmpl
        (_SALATE, 23),  # 20 tmpl
        (_SUPPEN, 22),  # 20 tmpl
        (_BEILAGEN, 20),  # 18 tmpl
        (_DESSERTS, 21),  # 14 tmpl
        (_FRUEHSTUECK, 24),  # 13 tmpl
        (_SNACKS, 20),  # 13 tmpl
        (_SWISS, 20),  # 18 tmpl
        (_INTERNATIONAL, 27),  # 25 tmpl
        (_BUDGET, 24),  # 12 tmpl
        (_SMOOTHIES, 22),  # 10 tmpl
        (_SALAD_BOWLS, 20),  # 10 tmpl
        (_WRAPS, 20),  # 10 tmpl
        (_ONE_POT, 20),  # 12 tmpl
        (_GRILL, 22),  # 10 tmpl
    ]
    all_r: list[dict] = []
    for tmpls, nvars in cats:
        all_r.extend(_gen(tmpls, nvars))

    seen: set[str] = set()
    unique: list[dict] = []
    for r in all_r:
        if r["title"] not in seen:
            seen.add(r["title"])
            unique.append(r)
    return unique


DEMO_RECIPES: list[dict] = _generate_all()
RECIPE_COUNT: int = len(DEMO_RECIPES)
