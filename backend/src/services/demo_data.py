"""Demo product data generator — 12,000+ realistic Swiss grocery products."""

from __future__ import annotations

import hashlib
import random
import uuid
from decimal import Decimal
from urllib.parse import quote

RETAILERS = ["migros", "coop", "aldi", "denner", "lidl"]

# Brand mappings per retailer: (budget, standard, premium/bio)
RETAILER_BRANDS: dict[str, dict[str, str]] = {
    "migros": {
        "budget": "M-Budget",
        "standard": "M-Classic",
        "bio": "Alnatura",
        "extra": "Farmer",
        "fairtrade": "Fairtrade",
        "demeter": "Demeter",
        "ip_suisse": "IP-Suisse",
    },
    "coop": {
        "budget": "Prix Garantie",
        "standard": "Qualité & Prix",
        "bio": "Naturaplan",
        "extra": "Betty Bossi",
        "fairtrade": "Fairtrade",
        "demeter": "Demeter",
        "ip_suisse": "IP-Suisse",
    },
    "aldi": {
        "budget": "Aldi Budget",
        "standard": "Alpengut",
        "bio": "Gut Bio",
        "extra": "Milsani",
        "fairtrade": "Fairtrade",
        "demeter": "Demeter",
        "ip_suisse": "IP-Suisse",
    },
    "denner": {
        "budget": "Primess",
        "standard": "Denner",
        "bio": "Denner Bio",
        "extra": "Denner Selection",
        "fairtrade": "Fairtrade",
        "demeter": "Demeter",
        "ip_suisse": "IP-Suisse",
    },
    "lidl": {
        "budget": "Milbona",
        "standard": "Sondey",
        "bio": "Bio Organic",
        "extra": "Cien",
        "fairtrade": "Fairtrade",
        "demeter": "Demeter",
        "ip_suisse": "IP-Suisse",
    },
}

# Discount percentages to pick from
DISCOUNT_VALUES = [10, 15, 20, 25, 30, 33, 40]

# --------------------------------------------------------------------------
# Nutritional info defaults per category (calories_per_100g, protein_g, fat_g, carbs_g)
# --------------------------------------------------------------------------
CATEGORY_NUTRITION: dict[str, tuple[float, float, float, float]] = {
    "dairy": (80, 5.0, 4.5, 5.0),
    "fruits": (50, 0.8, 0.3, 12.0),
    "vegetables": (30, 1.5, 0.3, 5.0),
    "meat": (180, 22.0, 9.0, 0.5),
    "bakery": (260, 8.0, 3.5, 50.0),
    "beverages": (40, 0.2, 0.0, 9.0),
    "snacks": (450, 5.0, 22.0, 58.0),
    "frozen": (200, 8.0, 8.0, 24.0),
    "pasta_rice": (350, 11.0, 1.5, 72.0),
    "canned": (90, 5.0, 2.0, 12.0),
    "sauces": (120, 1.5, 8.0, 10.0),
    "breakfast": (370, 9.0, 8.0, 65.0),
    "sweets": (400, 4.0, 18.0, 58.0),
    "hygiene": (0, 0, 0, 0),
    "cleaning": (0, 0, 0, 0),
    "baby": (70, 2.0, 3.0, 9.0),
    "pet": (100, 8.0, 5.0, 4.0),
    "alcohol": (45, 0.0, 0.0, 3.0),
    "spices": (250, 10.0, 5.0, 40.0),
    "organic": (120, 5.0, 4.0, 15.0),
    "baby_food": (65, 2.5, 2.0, 10.0),
    "coffee_tea": (5, 0.3, 0.0, 0.5),
    "oils_vinegar": (700, 0.0, 80.0, 0.5),
    "nuts_seeds": (580, 18.0, 48.0, 15.0),
    "ready_meals": (150, 8.0, 6.0, 18.0),
}

# --------------------------------------------------------------------------
# Allergen defaults per category
# --------------------------------------------------------------------------
CATEGORY_ALLERGENS: dict[str, list[str]] = {
    "dairy": ["lactose"],
    "fruits": [],
    "vegetables": [],
    "meat": [],
    "bakery": ["gluten"],
    "beverages": [],
    "snacks": ["gluten"],
    "frozen": ["gluten"],
    "pasta_rice": ["gluten"],
    "canned": [],
    "sauces": [],
    "breakfast": ["gluten"],
    "sweets": ["lactose", "gluten"],
    "hygiene": [],
    "cleaning": [],
    "baby": ["lactose"],
    "pet": [],
    "alcohol": ["gluten"],
    "spices": [],
    "organic": [],
    "baby_food": ["lactose"],
    "coffee_tea": [],
    "oils_vinegar": [],
    "nuts_seeds": ["nuts"],
    "ready_meals": ["gluten", "lactose"],
}

# --------------------------------------------------------------------------
# 25 categories, each with 20-30 base products: (name_template, base_price, size_variants)
#
# size_variants is a list of (suffix, price_multiplier) tuples.
# If empty, the product has no size variants (just the base).
# --------------------------------------------------------------------------

CATEGORY_PRODUCTS: dict[str, list[tuple[str, float, list[tuple[str, float]]]]] = {
    "dairy": [
        ("Vollmilch", 1.60, [("0.5L", 0.55), ("1L", 1.0), ("1.5L", 1.40)]),
        ("Halbfettmilch", 1.50, [("0.5L", 0.55), ("1L", 1.0), ("1.5L", 1.40)]),
        ("Naturjoghurt", 2.30, [("180g", 0.50), ("500g", 1.0)]),
        ("Emmentaler", 4.50, [("200g", 1.0), ("400g", 1.85)]),
        ("Butter", 3.20, [("100g", 0.50), ("250g", 1.0)]),
        ("Mozzarella", 1.80, [("125g", 1.0), ("250g", 1.80)]),
        ("Rahm", 1.90, [("2dl", 1.0), ("5dl", 2.20)]),
        ("Gruyère", 5.40, [("200g", 1.0), ("400g", 1.85)]),
        ("Cottage Cheese", 2.60, [("200g", 1.0)]),
        ("Quark", 1.95, [("250g", 1.0), ("500g", 1.80)]),
        ("Tilsiter", 4.80, [("200g", 1.0), ("400g", 1.85)]),
        ("Raclette Käse", 6.50, [("200g", 1.0), ("400g", 1.80)]),
        ("Appenzeller", 5.90, [("200g", 1.0)]),
        ("Mascarpone", 2.80, [("250g", 1.0)]),
        ("Crème fraîche", 2.10, [("200g", 1.0)]),
        ("Sbrinz", 6.20, [("100g", 1.0), ("200g", 1.85)]),
        ("Ziger", 3.40, [("200g", 1.0)]),
        ("Sauermilch", 1.30, [("5dl", 1.0), ("1L", 1.80)]),
        ("Fruchtjoghurt", 1.20, [("180g", 1.0), ("4×180g", 3.50)]),
        ("Skyr", 2.40, [("170g", 1.0), ("400g", 2.10)]),
        ("Kafferahm", 1.50, [("12 Portionen", 1.0)]),
        ("Schlagrahm", 2.80, [("2.5dl", 1.0), ("5dl", 1.80)]),
        ("Frischkäse", 2.30, [("150g", 1.0), ("300g", 1.80)]),
        ("Fondue Mischung", 9.80, [("400g", 1.0), ("800g", 1.85)]),
        ("Ricotta", 2.50, [("250g", 1.0)]),
        ("Hüttenkäse", 2.40, [("200g", 1.0)]),
        ("Ziegenfrischkäse", 3.90, [("150g", 1.0)]),
        ("Griechischer Joghurt", 2.80, [("200g", 1.0), ("500g", 2.20)]),
        ("Sauerrahm", 1.80, [("200g", 1.0)]),
        ("Kefir", 2.20, [("500ml", 1.0)]),
    ],
    "fruits": [
        ("Bananen", 2.40, [("1kg", 1.0)]),
        ("Äpfel Gala", 3.50, [("1kg", 1.0), ("2kg", 1.80)]),
        ("Zitronen", 2.90, [("500g", 1.0), ("1kg", 1.80)]),
        ("Erdbeeren", 4.50, [("250g", 1.0), ("500g", 1.80)]),
        ("Trauben weiss", 3.90, [("500g", 1.0), ("1kg", 1.85)]),
        ("Orangen", 3.20, [("1kg", 1.0), ("2kg", 1.80)]),
        ("Birnen", 3.80, [("1kg", 1.0)]),
        ("Kiwi", 2.95, [("6 Stk", 1.0)]),
        ("Heidelbeeren", 3.90, [("125g", 1.0), ("250g", 1.80)]),
        ("Mango", 2.50, [("Stk", 1.0)]),
        ("Ananas", 3.40, [("Stk", 1.0)]),
        ("Himbeeren", 4.90, [("125g", 1.0), ("250g", 1.80)]),
        ("Nektarinen", 3.80, [("500g", 1.0), ("1kg", 1.80)]),
        ("Wassermelone", 4.50, [("Stk", 1.0)]),
        ("Pflaumen", 3.20, [("500g", 1.0)]),
        ("Clementinen", 3.50, [("1kg", 1.0), ("2kg", 1.80)]),
        ("Avocado", 1.90, [("Stk", 1.0), ("2 Stk", 1.80)]),
        ("Granatapfel", 2.90, [("Stk", 1.0)]),
        ("Kirschen", 6.90, [("500g", 1.0)]),
        ("Aprikosen", 4.80, [("500g", 1.0)]),
        ("Limetten", 1.20, [("3 Stk", 1.0)]),
        ("Passionsfrucht", 1.60, [("2 Stk", 1.0)]),
        ("Trauben rot", 3.90, [("500g", 1.0), ("1kg", 1.85)]),
        ("Äpfel Braeburn", 3.60, [("1kg", 1.0)]),
        ("Äpfel Golden", 3.40, [("1kg", 1.0)]),
        ("Feigen", 4.20, [("4 Stk", 1.0)]),
        ("Litschi", 5.50, [("300g", 1.0)]),
        ("Papaya", 3.80, [("Stk", 1.0)]),
        ("Datteln", 4.80, [("200g", 1.0)]),
    ],
    "vegetables": [
        ("Rüebli", 1.80, [("500g", 0.55), ("1kg", 1.0)]),
        ("Tomaten", 2.50, [("500g", 1.0), ("1kg", 1.85)]),
        ("Gurke", 1.20, [("Stk", 1.0)]),
        ("Broccoli", 2.90, [("500g", 1.0)]),
        ("Zucchetti", 2.40, [("500g", 1.0), ("1kg", 1.80)]),
        ("Peperoni rot", 3.20, [("500g", 1.0)]),
        ("Kartoffeln", 3.90, [("1.5kg", 0.65), ("2.5kg", 1.0)]),
        ("Zwiebeln", 1.90, [("500g", 0.55), ("1kg", 1.0)]),
        ("Kopfsalat", 1.50, [("Stk", 1.0)]),
        ("Champignons", 2.80, [("250g", 1.0), ("500g", 1.80)]),
        ("Aubergine", 1.90, [("Stk", 1.0)]),
        ("Spinat", 2.60, [("250g", 1.0), ("500g", 1.80)]),
        ("Blumenkohl", 3.40, [("Stk", 1.0)]),
        ("Lauch", 1.60, [("Stk", 1.0)]),
        ("Fenchel", 2.80, [("Stk", 1.0)]),
        ("Rosenkohl", 3.50, [("500g", 1.0)]),
        ("Nüsslisalat", 2.90, [("100g", 1.0)]),
        ("Peperoncini", 1.80, [("100g", 1.0)]),
        ("Knoblauch", 1.50, [("3 Stk", 1.0)]),
        ("Süsskartoffeln", 3.40, [("500g", 1.0), ("1kg", 1.80)]),
        ("Randen", 2.20, [("500g", 1.0)]),
        ("Sellerie", 2.40, [("Stk", 1.0)]),
        ("Federkohl", 3.20, [("200g", 1.0)]),
        ("Cherrytomaten", 3.30, [("250g", 1.0), ("500g", 1.80)]),
        ("Peperoni gelb", 3.20, [("500g", 1.0)]),
        ("Peperoni grün", 2.80, [("500g", 1.0)]),
        ("Pak Choi", 2.50, [("200g", 1.0)]),
        ("Radieschen", 1.60, [("Bund", 1.0)]),
        ("Kohlrabi", 2.20, [("Stk", 1.0)]),
    ],
    "meat": [
        ("Pouletbrust", 8.90, [("300g", 1.0), ("500g", 1.55)]),
        ("Rindshackfleisch", 9.50, [("250g", 0.55), ("500g", 1.0)]),
        ("Schweinsgeschnetzeltes", 11.90, [("400g", 1.0)]),
        ("Kalbsbratwurst", 6.80, [("2 Stk", 1.0), ("4 Stk", 1.85)]),
        ("Lachs-Filet", 8.50, [("200g", 1.0), ("400g", 1.85)]),
        ("Pouletschenkel", 6.90, [("500g", 1.0), ("1kg", 1.80)]),
        ("Cervelat", 5.40, [("4 Stk", 1.0)]),
        ("Rindsfilet", 18.90, [("200g", 1.0)]),
        ("Poulet ganz", 12.50, [("1.2kg", 1.0)]),
        ("Crevetten", 9.80, [("200g", 1.0), ("400g", 1.85)]),
        ("Trockenfleisch", 7.90, [("100g", 1.0)]),
        ("Schweinssteak", 7.80, [("300g", 1.0), ("500g", 1.55)]),
        ("Rindssteak", 14.90, [("250g", 1.0)]),
        ("Poulet-Nuggets", 5.90, [("300g", 1.0), ("500g", 1.55)]),
        ("Hackfleisch gemischt", 8.90, [("500g", 1.0)]),
        ("Schinken gekocht", 4.50, [("150g", 1.0), ("300g", 1.85)]),
        ("Salami", 3.90, [("100g", 1.0), ("200g", 1.80)]),
        ("Lammkoteletts", 16.80, [("300g", 1.0)]),
        ("Forelle", 7.90, [("Stk", 1.0)]),
        ("Poulet-Geschnetzeltes", 9.50, [("350g", 1.0)]),
        ("Landjäger", 3.40, [("2 Stk", 1.0), ("4 Stk", 1.80)]),
        ("Wienerli", 4.80, [("4 Stk", 1.0), ("8 Stk", 1.85)]),
        ("Truthahn-Aufschnitt", 4.20, [("150g", 1.0)]),
        ("Schweinshals", 9.80, [("500g", 1.0)]),
        ("Entenbrust", 12.90, [("300g", 1.0)]),
        ("Rindsragout", 11.50, [("500g", 1.0)]),
        ("Kalbsschnitzel", 14.50, [("300g", 1.0)]),
    ],
    "bakery": [
        ("Ruchbrot", 2.80, [("500g", 1.0), ("1kg", 1.80)]),
        ("Zopf", 3.50, [("500g", 1.0)]),
        ("Vollkornbrot", 3.20, [("500g", 1.0)]),
        ("Gipfeli", 3.60, [("4 Stk", 1.0)]),
        ("Weggli", 2.90, [("6 Stk", 1.0)]),
        ("Toastbrot", 2.40, [("500g", 1.0)]),
        ("Laugenbrezel", 3.80, [("4 Stk", 1.0)]),
        ("Baguette", 1.80, [("Stk", 1.0)]),
        ("Dinkelbrötli", 4.20, [("4 Stk", 1.0)]),
        ("Butterzopf", 4.50, [("400g", 1.0)]),
        ("Nussgipfel", 3.90, [("2 Stk", 1.0)]),
        ("Tessiner Brot", 3.40, [("500g", 1.0)]),
        ("Bauernbrot", 3.80, [("500g", 1.0), ("1kg", 1.80)]),
        ("Knäckebrot", 2.60, [("250g", 1.0)]),
        ("Tortillas", 2.80, [("6 Stk", 1.0), ("12 Stk", 1.80)]),
        ("Pita-Brot", 2.50, [("5 Stk", 1.0)]),
        ("Sandwichbrot", 2.90, [("500g", 1.0)]),
        ("Silserli", 3.20, [("4 Stk", 1.0)]),
        ("Panettone", 6.50, [("500g", 1.0)]),
        ("Mailänderli", 4.80, [("200g", 1.0)]),
        ("Ciabatta", 2.40, [("Stk", 1.0)]),
        ("Focaccia", 3.50, [("Stk", 1.0)]),
        ("Roggenbrot", 3.60, [("500g", 1.0)]),
        ("Maisbrötli", 2.80, [("4 Stk", 1.0)]),
        ("Naan-Brot", 2.90, [("3 Stk", 1.0)]),
    ],
    "beverages": [
        ("Rivella rot", 2.50, [("0.5L", 0.45), ("1.5L", 1.0)]),
        ("Mineralwasser", 0.85, [("0.5L", 0.50), ("1.5L", 1.0), ("6×1.5L", 5.20)]),
        ("Orangensaft", 2.90, [("0.33L", 0.45), ("1L", 1.0), ("1.5L", 1.35)]),
        ("Eistee Pfirsich", 1.90, [("0.5L", 0.50), ("1.5L", 1.0)]),
        ("Apfelschorle", 1.80, [("0.5L", 0.50), ("1L", 1.0)]),
        ("Kaffee gemahlen", 4.20, [("250g", 0.55), ("500g", 1.0), ("1kg", 1.85)]),
        ("Ovomaltine", 3.90, [("500g", 1.0)]),
        ("Milchkaffee", 1.60, [("230ml", 1.0)]),
        ("Grüntee", 2.40, [("20er", 1.0)]),
        ("Sirup Himbeer", 3.50, [("75cl", 1.0)]),
        ("Coca-Cola", 2.60, [("0.5L", 0.50), ("1.5L", 1.0), ("6×1.5L", 4.80)]),
        ("Espresso Kapseln", 5.90, [("10 Stk", 1.0), ("20 Stk", 1.85)]),
        ("Tonic Water", 1.80, [("0.5L", 1.0), ("4×0.5L", 3.50)]),
        ("Apfelsaft", 2.60, [("1L", 1.0), ("1.5L", 1.35)]),
        ("Multivitaminsaft", 3.20, [("1L", 1.0)]),
        ("Rivella blau", 2.50, [("0.5L", 0.45), ("1.5L", 1.0)]),
        ("Pfefferminztee", 2.20, [("20er", 1.0)]),
        ("Schwarztee", 2.40, [("20er", 1.0), ("50er", 2.20)]),
        ("Kakao-Pulver", 3.80, [("400g", 1.0)]),
        ("Kräutertee", 2.60, [("20er", 1.0)]),
        ("Energy Drink", 1.50, [("250ml", 1.0), ("4×250ml", 3.50)]),
        ("Grapefruitsaft", 2.80, [("1L", 1.0)]),
        ("Kokoswasser", 2.90, [("330ml", 1.0)]),
        ("Kombucha", 3.50, [("330ml", 1.0)]),
        ("Eistee Zitrone", 1.90, [("0.5L", 0.50), ("1.5L", 1.0)]),
        ("Sprite", 2.40, [("0.5L", 0.50), ("1.5L", 1.0)]),
    ],
    "snacks": [
        ("Chips Original", 3.90, [("90g", 0.55), ("170g", 1.0)]),
        ("Chips Paprika", 3.90, [("90g", 0.55), ("170g", 1.0)]),
        ("Schokolade Milch", 2.20, [("100g", 1.0), ("200g", 1.85)]),
        ("Studentenfutter", 3.50, [("200g", 1.0)]),
        ("Guetzli Butter", 2.80, [("200g", 1.0)]),
        ("Salzstängeli", 1.80, [("200g", 1.0)]),
        ("Popcorn süss", 2.40, [("100g", 1.0)]),
        ("Nussmischung", 4.50, [("150g", 1.0), ("300g", 1.85)]),
        ("Dunkle Schokolade", 2.90, [("100g", 1.0)]),
        ("Reiswaffeln", 1.80, [("130g", 1.0)]),
        ("Gummibärli", 2.60, [("150g", 0.55), ("300g", 1.0)]),
        ("Biberli", 4.90, [("3 Stk", 1.0)]),
        ("Erdnüsse geröstet", 2.80, [("200g", 1.0), ("500g", 2.20)]),
        ("Crackers", 2.40, [("200g", 1.0)]),
        ("Müsliriegel", 3.20, [("6 Stk", 1.0)]),
        ("Nussriegel", 3.50, [("5 Stk", 1.0)]),
        ("Chips Sour Cream", 3.90, [("170g", 1.0)]),
        ("Schokolade weiss", 2.20, [("100g", 1.0)]),
        ("Schokolade Nuss", 2.90, [("100g", 1.0), ("200g", 1.85)]),
        ("Trockenfrüchte", 4.20, [("200g", 1.0)]),
        ("Grissini", 2.50, [("125g", 1.0)]),
        ("Tortilla Chips", 3.20, [("200g", 1.0)]),
        ("Dörrbohnen", 3.80, [("150g", 1.0)]),
        ("Beef Jerky", 5.90, [("75g", 1.0)]),
        ("Mikrowellen-Popcorn", 2.20, [("3×100g", 1.0)]),
    ],
    "frozen": [
        ("Pommes Frites", 3.20, [("500g", 1.0), ("1kg", 1.80)]),
        ("Pizza Margherita", 3.90, [("Stk", 1.0), ("2 Stk", 1.80)]),
        ("Pizza Prosciutto", 4.50, [("Stk", 1.0)]),
        ("Rahmspinat", 2.80, [("500g", 1.0)]),
        ("Gemüse-Mix", 3.40, [("500g", 1.0), ("1kg", 1.80)]),
        ("Glacé Vanille", 5.90, [("500ml", 1.0), ("1L", 1.75)]),
        ("Glacé Schokolade", 5.90, [("500ml", 1.0), ("1L", 1.75)]),
        ("Fischstäbchen", 4.50, [("300g", 1.0), ("600g", 1.80)]),
        ("Poulet-Cordon-Bleu", 7.80, [("2 Stk", 1.0)]),
        ("Blätterteig", 2.90, [("Stk", 1.0), ("2 Stk", 1.80)]),
        ("Tiefkühl-Beeren-Mix", 4.20, [("300g", 1.0), ("500g", 1.55)]),
        ("Kroketten", 3.50, [("500g", 1.0)]),
        ("Lasagne", 5.90, [("600g", 1.0)]),
        ("Spring Rolls", 4.80, [("300g", 1.0)]),
        ("Ravioli", 4.50, [("500g", 1.0)]),
        ("Rösti", 2.80, [("500g", 1.0), ("1kg", 1.80)]),
        ("Glacé Cornet", 6.50, [("6 Stk", 1.0)]),
        ("Beerenmix", 4.90, [("500g", 1.0)]),
        ("Bratgemüse", 3.80, [("500g", 1.0)]),
        ("Hamburger", 5.50, [("4 Stk", 1.0)]),
        ("Pizza Quattro Formaggi", 4.90, [("Stk", 1.0)]),
        ("Tiefkühl-Edamame", 3.80, [("400g", 1.0)]),
        ("Glacé Erdbeer", 5.90, [("500ml", 1.0)]),
        ("Chicken Wings", 6.50, [("500g", 1.0)]),
        ("Tiefkühl-Spinat Blatt", 2.60, [("500g", 1.0)]),
    ],
    "pasta_rice": [
        ("Spaghetti", 1.60, [("500g", 1.0), ("1kg", 1.80)]),
        ("Penne", 1.60, [("500g", 1.0)]),
        ("Fusilli", 1.60, [("500g", 1.0)]),
        ("Hörnli", 1.80, [("500g", 1.0)]),
        ("Risotto-Reis", 3.20, [("500g", 1.0), ("1kg", 1.80)]),
        ("Basmati-Reis", 3.50, [("500g", 1.0), ("1kg", 1.80)]),
        ("Langkorn-Reis", 2.40, [("500g", 1.0), ("1kg", 1.80)]),
        ("Tagliatelle", 2.20, [("500g", 1.0)]),
        ("Farfalle", 1.80, [("500g", 1.0)]),
        ("Lasagne-Blätter", 2.40, [("250g", 1.0)]),
        ("Gnocchi", 2.90, [("500g", 1.0)]),
        ("Tortellini", 3.50, [("250g", 1.0), ("500g", 1.80)]),
        ("Couscous", 2.80, [("500g", 1.0)]),
        ("Polenta", 2.20, [("500g", 1.0)]),
        ("Älplermagronen", 3.90, [("400g", 1.0)]),
        ("Vollkorn-Spaghetti", 2.20, [("500g", 1.0)]),
        ("Ebly Weizen", 3.20, [("500g", 1.0)]),
        ("Glasnudeln", 2.40, [("250g", 1.0)]),
        ("Reisnudeln", 2.80, [("250g", 1.0)]),
        ("Spätzli", 2.90, [("500g", 1.0)]),
        ("Knöpfli", 2.80, [("500g", 1.0)]),
        ("Orzo", 2.40, [("500g", 1.0)]),
        ("Rigatoni", 1.80, [("500g", 1.0)]),
        ("Quinoa", 4.90, [("400g", 1.0)]),
        ("Bulgur", 2.80, [("500g", 1.0)]),
        ("Jasmin-Reis", 3.80, [("500g", 1.0), ("1kg", 1.80)]),
    ],
    "canned": [
        ("Pelati", 1.50, [("280g", 0.55), ("400g", 1.0), ("800g", 1.80)]),
        ("Thunfisch", 2.80, [("150g", 1.0), ("3×150g", 2.70)]),
        ("Kichererbsen", 1.60, [("400g", 1.0)]),
        ("Kidney-Bohnen", 1.60, [("400g", 1.0)]),
        ("Mais", 1.80, [("285g", 1.0), ("570g", 1.80)]),
        ("Ananas Scheiben", 2.20, [("340g", 1.0)]),
        ("Champignons", 1.90, [("230g", 1.0)]),
        ("Oliven schwarz", 2.50, [("150g", 1.0), ("350g", 2.10)]),
        ("Oliven grün", 2.50, [("150g", 1.0), ("350g", 2.10)]),
        ("Tomatenmark", 1.80, [("70g", 0.45), ("140g", 1.0)]),
        ("Ravioli (Dose)", 2.90, [("430g", 1.0), ("870g", 1.80)]),
        ("Bohnen weiss", 1.60, [("400g", 1.0)]),
        ("Linsen", 1.80, [("400g", 1.0)]),
        ("Sardinen", 2.40, [("125g", 1.0)]),
        ("Marroni", 3.80, [("200g", 1.0)]),
        ("Rote Bete", 2.10, [("400g", 1.0)]),
        ("Sauerkraut", 1.90, [("400g", 1.0)]),
        ("Erbsen & Rüebli", 1.80, [("300g", 1.0)]),
        ("Kokosmilch", 2.20, [("400ml", 1.0)]),
        ("Pesto Basilico", 3.40, [("190g", 1.0)]),
        ("Artischockenherzen", 3.80, [("280g", 1.0)]),
        ("Getrocknete Tomaten", 4.20, [("200g", 1.0)]),
        ("Schwarze Bohnen", 1.80, [("400g", 1.0)]),
        ("Bambussprossen", 2.20, [("220g", 1.0)]),
        ("Pesto Rosso", 3.60, [("190g", 1.0)]),
    ],
    "sauces": [
        ("Tomatensugo", 2.80, [("350g", 1.0), ("500g", 1.40)]),
        ("Ketchup", 2.40, [("340g", 1.0), ("700g", 1.80)]),
        ("Senf mild", 1.80, [("200g", 1.0)]),
        ("Senf scharf", 1.90, [("200g", 1.0)]),
        ("Mayonnaise", 2.50, [("265g", 1.0), ("500g", 1.75)]),
        ("Sojasauce", 2.90, [("150ml", 1.0), ("500ml", 2.80)]),
        ("Balsamico", 3.80, [("250ml", 1.0), ("500ml", 1.80)]),
        ("Olivenöl", 5.90, [("500ml", 1.0), ("1L", 1.80)]),
        ("Sonnenblumenöl", 2.80, [("500ml", 1.0), ("1L", 1.80)]),
        ("Salatsauce French", 2.40, [("350ml", 1.0)]),
        ("Salatsauce Italian", 2.40, [("350ml", 1.0)]),
        ("Currysauce", 3.20, [("250ml", 1.0)]),
        ("BBQ-Sauce", 3.50, [("300ml", 1.0)]),
        ("Tabasco", 4.90, [("60ml", 1.0)]),
        ("Bouillon Rind", 2.80, [("6 Stk", 1.0), ("12 Stk", 1.80)]),
        ("Bouillon Gemüse", 2.60, [("6 Stk", 1.0), ("12 Stk", 1.80)]),
        ("Bratensauce", 1.90, [("Btl", 1.0)]),
        ("Essig", 1.80, [("500ml", 1.0), ("1L", 1.75)]),
        ("Rapsöl", 3.20, [("500ml", 1.0), ("1L", 1.80)]),
        ("Thaisauce süss-sauer", 3.40, [("250ml", 1.0)]),
        ("Sriracha", 3.80, [("250ml", 1.0)]),
        ("Worcestersauce", 3.50, [("150ml", 1.0)]),
        ("Teriyaki-Sauce", 3.60, [("250ml", 1.0)]),
        ("Aioli", 3.20, [("150g", 1.0)]),
        ("Chimichurri", 4.20, [("200ml", 1.0)]),
    ],
    "breakfast": [
        ("Birchermüesli", 3.80, [("500g", 1.0), ("1kg", 1.80)]),
        ("Haferflocken", 1.60, [("500g", 1.0), ("1kg", 1.80)]),
        ("Cornflakes", 3.20, [("375g", 1.0), ("750g", 1.80)]),
        ("Konfitüre Erdbeere", 3.50, [("250g", 1.0), ("500g", 1.75)]),
        ("Konfitüre Aprikose", 3.50, [("250g", 1.0)]),
        ("Honig", 5.80, [("250g", 1.0), ("500g", 1.80)]),
        ("Nutella", 4.50, [("400g", 1.0), ("750g", 1.80)]),
        ("Crunchy Müesli", 4.20, [("500g", 1.0)]),
        ("Schoko-Müesli", 4.50, [("500g", 1.0)]),
        ("Porridge", 3.80, [("350g", 1.0)]),
        ("Zopfmehl", 2.20, [("1kg", 1.0)]),
        ("Pancake-Mix", 3.50, [("300g", 1.0)]),
        ("Ahornsirup", 6.90, [("250ml", 1.0)]),
        ("Mehl Weiss", 1.20, [("1kg", 1.0), ("2kg", 1.80)]),
        ("Halbweissmehl", 1.40, [("1kg", 1.0)]),
        ("Zucker", 1.50, [("1kg", 1.0), ("5kg", 4.20)]),
        ("Eier Freiland", 4.20, [("6 Stk", 1.0), ("10 Stk", 1.55)]),
        ("Eier Bodenhaltung", 3.20, [("6 Stk", 1.0), ("10 Stk", 1.55)]),
        ("Orangenkonfitüre", 3.50, [("250g", 1.0)]),
        ("Knuspermüesli Beeren", 4.80, [("500g", 1.0)]),
        ("Brioche", 3.20, [("4 Stk", 1.0)]),
        ("Dinkelflocken", 2.40, [("500g", 1.0)]),
        ("Chia-Samen", 4.50, [("200g", 1.0)]),
        ("Erdnussbutter", 3.90, [("350g", 1.0)]),
        ("Agavendicksaft", 4.20, [("250ml", 1.0)]),
        ("Protein-Müesli", 5.50, [("500g", 1.0)]),
    ],
    "sweets": [
        ("Toblerone", 4.50, [("100g", 1.0), ("360g", 3.20)]),
        ("Lindor Kugeln", 7.90, [("200g", 1.0)]),
        ("Ragusa", 2.90, [("50g", 1.0), ("4×50g", 3.50)]),
        ("Cailler Milch", 3.20, [("100g", 1.0)]),
        ("Frey Giandor", 3.50, [("100g", 1.0)]),
        ("Kambly Bretzeli", 3.80, [("100g", 1.0), ("300g", 2.70)]),
        ("Läckerli", 5.90, [("250g", 1.0)]),
        ("Tiramisù", 4.50, [("Stk", 1.0)]),
        ("Crème Brûlée", 3.90, [("2 Stk", 1.0)]),
        ("Panna Cotta", 3.50, [("2 Stk", 1.0)]),
        ("Pudding Schoko", 1.80, [("4 Stk", 1.0)]),
        ("Pudding Vanille", 1.80, [("4 Stk", 1.0)]),
        ("Vermicelles", 5.50, [("Stk", 1.0), ("2 Stk", 1.80)]),
        ("Berliner", 3.90, [("3 Stk", 1.0)]),
        ("Schokoladenmousse", 2.80, [("2 Stk", 1.0)]),
        ("Wähe Apfel", 5.90, [("Stk", 1.0)]),
        ("Meringue", 3.20, [("4 Stk", 1.0)]),
        ("Bonbons", 2.20, [("200g", 1.0)]),
        ("Kaugummi", 1.50, [("10 Stk", 1.0)]),
        ("Zuckerwatte", 2.90, [("80g", 1.0)]),
        ("Glacé-Stängel", 4.50, [("6 Stk", 1.0)]),
        ("Brownies", 4.80, [("4 Stk", 1.0)]),
        ("Macarons", 6.90, [("6 Stk", 1.0)]),
        ("Muffins Schoko", 4.20, [("4 Stk", 1.0)]),
        ("Wähe Zwetschgen", 5.90, [("Stk", 1.0)]),
    ],
    "hygiene": [
        ("Zahnpasta", 2.80, [("75ml", 1.0), ("125ml", 1.55)]),
        ("Duschgel", 2.90, [("250ml", 1.0), ("500ml", 1.75)]),
        ("Shampoo", 3.50, [("250ml", 1.0), ("500ml", 1.75)]),
        ("Deo Spray", 3.20, [("150ml", 1.0)]),
        ("Deo Roll-on", 2.80, [("50ml", 1.0)]),
        ("Handseife", 1.90, [("300ml", 1.0)]),
        ("Bodylotion", 4.50, [("250ml", 1.0), ("400ml", 1.55)]),
        ("Rasierer Einweg", 3.80, [("5 Stk", 1.0)]),
        ("Taschentücher", 1.80, [("10×10 Stk", 1.0)]),
        ("Toilettenpapier", 4.90, [("8 Rollen", 1.0), ("16 Rollen", 1.85)]),
        ("Wattepads", 1.60, [("80 Stk", 1.0)]),
        ("Zahnbürste", 2.50, [("Stk", 1.0), ("3 Stk", 2.50)]),
        ("Haargel", 3.20, [("150ml", 1.0)]),
        ("Gesichtscreme", 5.90, [("50ml", 1.0)]),
        ("Lippenpflege", 2.40, [("Stk", 1.0)]),
        ("Sonnencreme", 8.90, [("200ml", 1.0)]),
        ("Spülung Haar", 3.80, [("250ml", 1.0)]),
        ("Feuchttücher", 2.40, [("60 Stk", 1.0)]),
        ("Damenbinden", 3.50, [("16 Stk", 1.0)]),
        ("Pflaster", 2.80, [("20 Stk", 1.0)]),
        ("Mundspülung", 3.90, [("500ml", 1.0)]),
        ("Rasierschaum", 2.80, [("200ml", 1.0)]),
        ("Haarspray", 3.50, [("250ml", 1.0)]),
        ("Trockenshampoo", 4.20, [("200ml", 1.0)]),
        ("Abschminkpads", 3.80, [("30 Stk", 1.0)]),
    ],
    "cleaning": [
        ("Abwaschmittel", 2.20, [("500ml", 1.0), ("1L", 1.80)]),
        ("WC-Reiniger", 2.80, [("750ml", 1.0)]),
        ("Allzweckreiniger", 3.20, [("750ml", 1.0), ("1L", 1.30)]),
        ("Waschmittel flüssig", 8.90, [("1L", 1.0), ("2L", 1.80)]),
        ("Waschmittel Pulver", 7.80, [("1.5kg", 1.0), ("3kg", 1.80)]),
        ("Weichspüler", 3.90, [("1L", 1.0), ("2L", 1.80)]),
        ("Glasreiniger", 3.50, [("500ml", 1.0)]),
        ("Entkalker", 4.90, [("500ml", 1.0)]),
        ("Müllsäcke", 2.80, [("20 Stk", 1.0)]),
        ("Kehrichtsäcke", 3.50, [("10 Stk", 1.0)]),
        ("Schwämme", 2.20, [("3 Stk", 1.0)]),
        ("Küchenpapier", 3.20, [("4 Rollen", 1.0), ("8 Rollen", 1.85)]),
        ("Backpapier", 2.80, [("Rolle", 1.0)]),
        ("Alufolie", 2.40, [("Rolle 10m", 1.0), ("Rolle 30m", 2.50)]),
        ("Frischhaltefolie", 2.20, [("Rolle", 1.0)]),
        ("Geschirrspültabs", 6.90, [("30 Stk", 1.0), ("60 Stk", 1.80)]),
        ("Klarspüler", 3.50, [("500ml", 1.0)]),
        ("Spülmaschinensalz", 1.90, [("1kg", 1.0)]),
        ("Bodenwischer", 5.90, [("Stk", 1.0)]),
        ("Microfasertuch", 2.80, [("3 Stk", 1.0)]),
        ("Schimmelentferner", 5.50, [("500ml", 1.0)]),
        ("Backofen-Reiniger", 4.80, [("500ml", 1.0)]),
        ("Handschuhe Einweg", 2.90, [("50 Stk", 1.0)]),
        ("Staubsaugerbeutel", 8.90, [("5 Stk", 1.0)]),
    ],
    "baby": [
        ("Windeln Grösse 3", 12.90, [("36 Stk", 1.0), ("72 Stk", 1.80)]),
        ("Windeln Grösse 4", 13.90, [("30 Stk", 1.0), ("60 Stk", 1.80)]),
        ("Windeln Grösse 5", 14.50, [("26 Stk", 1.0), ("52 Stk", 1.80)]),
        ("Baby-Feuchttücher", 2.90, [("72 Stk", 1.0), ("3×72 Stk", 2.50)]),
        ("Babybrei Karotte", 1.80, [("190g", 1.0)]),
        ("Babybrei Apfel-Birne", 1.80, [("190g", 1.0)]),
        ("Babymilch 1", 14.90, [("800g", 1.0)]),
        ("Babymilch 2", 14.90, [("800g", 1.0)]),
        ("Babybrei Griess", 1.90, [("190g", 1.0)]),
        ("Babyshampoo", 4.50, [("250ml", 1.0)]),
        ("Babycreme", 3.80, [("100ml", 1.0)]),
        ("Nuggi", 5.90, [("2 Stk", 1.0)]),
        ("Flasche", 8.90, [("Stk", 1.0)]),
        ("Babylotion", 4.20, [("250ml", 1.0)]),
        ("Baby-Wundcreme", 5.50, [("75ml", 1.0)]),
        ("Beissring", 4.90, [("Stk", 1.0)]),
        ("Babybrei Gemüse", 1.80, [("190g", 1.0)]),
        ("Kinderzahncreme", 3.20, [("50ml", 1.0)]),
        ("Baby-Waschmittel", 6.50, [("1L", 1.0)]),
        ("Trinkbecher Baby", 6.90, [("Stk", 1.0)]),
    ],
    "pet": [
        ("Katzenfutter nass", 1.20, [("100g", 1.0), ("4×100g", 3.50)]),
        ("Katzenfutter trocken", 5.90, [("500g", 1.0), ("2kg", 3.20)]),
        ("Hundefutter nass", 2.50, [("400g", 1.0), ("800g", 1.80)]),
        ("Hundefutter trocken", 8.90, [("2kg", 1.0), ("5kg", 2.20)]),
        ("Katzenstreu", 5.50, [("5L", 1.0), ("10L", 1.80)]),
        ("Leckerli Hund", 3.80, [("200g", 1.0)]),
        ("Leckerli Katze", 2.90, [("60g", 1.0)]),
        ("Hundefutter Welpen", 9.80, [("2kg", 1.0)]),
        ("Katzen-Snack Sticks", 1.80, [("6 Stk", 1.0)]),
        ("Hunde-Kaustange", 3.50, [("3 Stk", 1.0)]),
        ("Katzenmilch", 1.50, [("200ml", 1.0)]),
        ("Hundeknochen", 2.90, [("Stk", 1.0)]),
        ("Vogelstreufutter", 3.80, [("1kg", 1.0)]),
        ("Fischfutter", 4.50, [("100g", 1.0)]),
        ("Hamsterfutter", 3.20, [("500g", 1.0)]),
        ("Katzengras Samen", 2.80, [("Btl", 1.0)]),
        ("Zeckenhalsband", 12.90, [("Stk", 1.0)]),
        ("Flohspray", 9.80, [("200ml", 1.0)]),
        ("Hundeshampoo", 6.50, [("250ml", 1.0)]),
        ("Katzenspielzeug", 4.90, [("Stk", 1.0)]),
    ],
    "alcohol": [
        ("Bier Lager", 1.40, [("330ml", 1.0), ("500ml", 1.40), ("6×330ml", 5.20)]),
        ("Bier Weizen", 1.80, [("500ml", 1.0)]),
        ("Feldschlösschen", 1.50, [("330ml", 1.0), ("6×330ml", 5.20)]),
        ("Appenzeller Bier", 1.80, [("330ml", 1.0), ("6×330ml", 5.80)]),
        ("Rotwein Merlot", 6.90, [("75cl", 1.0)]),
        ("Rotwein Pinot Noir", 8.50, [("75cl", 1.0)]),
        ("Weisswein Chasselas", 7.50, [("75cl", 1.0)]),
        ("Weisswein Sauvignon", 8.90, [("75cl", 1.0)]),
        ("Rosé", 7.80, [("75cl", 1.0)]),
        ("Prosecco", 6.50, [("75cl", 1.0)]),
        ("Aperol", 14.90, [("70cl", 1.0)]),
        ("Gin", 18.90, [("70cl", 1.0)]),
        ("Wodka", 12.90, [("70cl", 1.0)]),
        ("Whisky", 24.90, [("70cl", 1.0)]),
        ("Rum", 16.90, [("70cl", 1.0)]),
        ("Kirsch", 19.80, [("50cl", 1.0)]),
        ("Williamine", 22.50, [("50cl", 1.0)]),
        ("Cider", 2.40, [("330ml", 1.0), ("4×330ml", 3.50)]),
        ("Bier alkoholfrei", 1.40, [("330ml", 1.0), ("6×330ml", 5.20)]),
        ("Hugo", 3.50, [("75cl", 1.0)]),
        ("Campari", 13.90, [("70cl", 1.0)]),
        ("Limoncello", 11.90, [("50cl", 1.0)]),
        ("Tequila", 19.90, [("70cl", 1.0)]),
        ("Grappa", 18.50, [("50cl", 1.0)]),
        ("IPA Bier", 2.40, [("330ml", 1.0)]),
    ],
    "spices": [
        ("Salz", 0.90, [("500g", 1.0), ("1kg", 1.80)]),
        ("Pfeffer schwarz", 2.80, [("Mühle", 1.0)]),
        ("Paprika edelsüss", 2.20, [("50g", 1.0)]),
        ("Zimt gemahlen", 2.40, [("40g", 1.0)]),
        ("Muskatnuss", 3.80, [("5 Stk", 1.0)]),
        ("Basilikum getrocknet", 2.10, [("15g", 1.0)]),
        ("Oregano", 2.10, [("15g", 1.0)]),
        ("Knoblauchpulver", 2.50, [("50g", 1.0)]),
        ("Currypulver", 2.80, [("50g", 1.0)]),
        ("Kurkuma", 2.60, [("40g", 1.0)]),
        ("Chili gemahlen", 2.80, [("40g", 1.0)]),
        ("Kräuter der Provence", 2.90, [("20g", 1.0)]),
        ("Rosmarin", 2.10, [("15g", 1.0)]),
        ("Thymian", 2.10, [("15g", 1.0)]),
        ("Lorbeerblätter", 2.40, [("10g", 1.0)]),
        ("Vanillezucker", 1.20, [("5 Btl", 1.0)]),
        ("Backpulver", 0.90, [("4 Btl", 1.0)]),
        ("Hefe frisch", 0.60, [("42g", 1.0)]),
        ("Aromat", 3.50, [("90g", 1.0), ("250g", 2.50)]),
        ("Fondor", 3.20, [("90g", 1.0)]),
        ("Gemüsebouillon", 3.80, [("250g", 1.0)]),
        ("Koriander gemahlen", 2.40, [("30g", 1.0)]),
        ("Kreuzkümmel", 2.60, [("40g", 1.0)]),
        ("Ingwerpulver", 2.50, [("40g", 1.0)]),
        ("Sumach", 3.80, [("30g", 1.0)]),
        ("Za'atar", 4.20, [("40g", 1.0)]),
    ],
    "organic": [
        ("Bio Vollmilch", 2.20, [("1L", 1.0)]),
        ("Bio Eier Freiland", 5.90, [("6 Stk", 1.0), ("10 Stk", 1.55)]),
        ("Bio Rüebli", 2.80, [("500g", 1.0), ("1kg", 1.80)]),
        ("Bio Tomaten", 3.90, [("500g", 1.0)]),
        ("Bio Äpfel", 4.90, [("1kg", 1.0)]),
        ("Bio Bananen", 3.20, [("1kg", 1.0)]),
        ("Bio Pouletbrust", 13.90, [("300g", 1.0)]),
        ("Bio Hackfleisch Rind", 12.50, [("500g", 1.0)]),
        ("Bio Joghurt Natur", 1.80, [("180g", 1.0), ("500g", 2.50)]),
        ("Bio Butter", 4.50, [("250g", 1.0)]),
        ("Bio Haferflocken", 2.40, [("500g", 1.0)]),
        ("Bio Olivenöl", 8.90, [("500ml", 1.0)]),
        ("Bio Spaghetti", 2.40, [("500g", 1.0)]),
        ("Bio Tofu", 3.50, [("250g", 1.0), ("400g", 1.50)]),
        ("Bio Kichererbsen", 2.40, [("400g", 1.0)]),
        ("Bio Reis", 4.20, [("500g", 1.0), ("1kg", 1.80)]),
        ("Bio Müesli", 5.50, [("500g", 1.0)]),
        ("Bio Honig", 8.90, [("250g", 1.0)]),
        ("Bio Kartoffeln", 4.80, [("1.5kg", 1.0)]),
        ("Bio Dinkelmehl", 2.80, [("1kg", 1.0)]),
        ("Bio Quinoa", 4.90, [("400g", 1.0)]),
        ("Bio Mandeln", 5.50, [("200g", 1.0)]),
        ("Bio Kokosmilch", 2.80, [("400ml", 1.0)]),
        ("Bio Leinsamen", 2.40, [("250g", 1.0)]),
        ("Bio Agavendicksaft", 4.80, [("250ml", 1.0)]),
        ("Bio Erdnussbutter", 4.90, [("350g", 1.0)]),
        ("Bio Hirse", 3.20, [("500g", 1.0)]),
    ],
    # --------------------------------------------------------------------------
    # 5 new categories
    # --------------------------------------------------------------------------
    "baby_food": [
        ("Babygläschen Kürbis", 1.90, [("125g", 1.0), ("190g", 1.40)]),
        ("Babygläschen Pastinake", 1.90, [("125g", 1.0), ("190g", 1.40)]),
        ("Babygläschen Banane", 1.80, [("125g", 1.0), ("190g", 1.40)]),
        ("Babygläschen Birne", 1.80, [("125g", 1.0), ("190g", 1.40)]),
        ("Babybrei Reis-Karotte", 2.20, [("190g", 1.0)]),
        ("Babybrei Dinkel", 2.40, [("250g", 1.0)]),
        ("Babybrei Hafer", 2.40, [("250g", 1.0)]),
        ("Folgemilch 3", 15.90, [("800g", 1.0)]),
        ("Kindermilch 1+", 12.90, [("600g", 1.0)]),
        ("Baby-Snack Reiswaffeln", 2.50, [("40g", 1.0)]),
        ("Baby-Snack Maisstangen", 2.20, [("45g", 1.0)]),
        ("Babywasser", 1.20, [("1L", 1.0)]),
        ("Babygläschen Rindfleisch-Gemüse", 2.80, [("190g", 1.0)]),
        ("Babygläschen Poulet-Reis", 2.80, [("190g", 1.0)]),
        ("Babybrei 3-Korn", 2.60, [("250g", 1.0)]),
        ("Baby-Zwieback", 2.40, [("100g", 1.0)]),
        ("Babygläschen Apfel-Mango", 1.90, [("125g", 1.0)]),
        ("Babygläschen Erbse-Kartoffel", 2.50, [("190g", 1.0)]),
        ("Baby-Keks", 2.80, [("150g", 1.0)]),
        ("Babygläschen Tomate-Nudel", 2.60, [("190g", 1.0)]),
    ],
    "coffee_tea": [
        ("Espresso Bohnen", 8.90, [("250g", 1.0), ("500g", 1.80), ("1kg", 3.40)]),
        ("Filterkaffee gemahlen", 5.90, [("250g", 1.0), ("500g", 1.80)]),
        ("Instant-Kaffee", 7.50, [("100g", 1.0), ("200g", 1.80)]),
        ("Kaffee entkoffeiniert", 6.20, [("250g", 1.0), ("500g", 1.80)]),
        ("Earl Grey Tee", 3.20, [("20er", 1.0), ("50er", 2.20)]),
        ("Kamillentee", 2.40, [("20er", 1.0)]),
        ("Rooibos Tee", 2.80, [("20er", 1.0)]),
        ("Ingwer-Zitrone Tee", 2.90, [("20er", 1.0)]),
        ("Fencheltee", 2.20, [("20er", 1.0)]),
        ("Chai Tee", 3.50, [("20er", 1.0)]),
        ("Matcha Pulver", 9.80, [("30g", 1.0), ("80g", 2.40)]),
        ("Kaffee Crema Bohnen", 9.50, [("500g", 1.0), ("1kg", 1.85)]),
        ("Lungo Kapseln", 5.50, [("10 Stk", 1.0), ("20 Stk", 1.85)]),
        ("Ristretto Kapseln", 5.50, [("10 Stk", 1.0), ("20 Stk", 1.85)]),
        ("Türkischer Kaffee", 4.80, [("250g", 1.0)]),
        ("Früchtetee", 2.40, [("20er", 1.0)]),
        ("Jasmin Tee", 3.80, [("20er", 1.0)]),
        ("Oolong Tee", 4.20, [("50g", 1.0)]),
        ("Sencha Grüntee", 3.50, [("20er", 1.0)]),
        ("Kaffeepads", 5.80, [("18 Stk", 1.0), ("36 Stk", 1.80)]),
    ],
    "oils_vinegar": [
        (
            "Olivenöl Extra Vergine",
            7.90,
            [("250ml", 1.0), ("500ml", 1.80), ("1L", 3.20)],
        ),
        ("Traubenkernöl", 5.80, [("250ml", 1.0)]),
        ("Sesamöl", 4.50, [("250ml", 1.0)]),
        ("Kokosöl", 5.90, [("300ml", 1.0), ("500ml", 1.55)]),
        ("Leinöl", 4.80, [("250ml", 1.0)]),
        ("Walnussöl", 6.50, [("250ml", 1.0)]),
        ("Avocadoöl", 7.20, [("250ml", 1.0)]),
        ("Apfelessig", 2.80, [("500ml", 1.0), ("1L", 1.80)]),
        ("Weissweinessig", 2.40, [("500ml", 1.0)]),
        ("Rotweinessig", 2.60, [("500ml", 1.0)]),
        ("Aceto Balsamico di Modena", 5.50, [("250ml", 1.0), ("500ml", 1.80)]),
        ("Sherry-Essig", 4.80, [("250ml", 1.0)]),
        ("Reisessig", 3.20, [("250ml", 1.0)]),
        ("Kürbiskernöl", 6.90, [("250ml", 1.0)]),
        ("Erdnussöl", 4.20, [("500ml", 1.0)]),
        ("Distelöl", 4.50, [("500ml", 1.0)]),
        ("Sonnenblumenöl kaltgepresst", 3.80, [("500ml", 1.0)]),
        ("Balsamico Crema", 4.90, [("250ml", 1.0)]),
        ("Condimento Bianco", 4.50, [("250ml", 1.0)]),
        ("Trüffelöl", 8.90, [("100ml", 1.0)]),
    ],
    "nuts_seeds": [
        ("Mandeln ganz", 4.50, [("200g", 1.0), ("500g", 2.20)]),
        ("Cashewnüsse", 5.50, [("200g", 1.0), ("500g", 2.20)]),
        ("Baumnüsse", 4.80, [("200g", 1.0)]),
        ("Haselnüsse", 4.20, [("200g", 1.0), ("500g", 2.20)]),
        ("Pistazien", 6.50, [("150g", 1.0), ("300g", 1.85)]),
        ("Pinienkerne", 7.90, [("100g", 1.0)]),
        ("Kürbiskerne", 3.80, [("200g", 1.0)]),
        ("Sonnenblumenkerne", 2.20, [("200g", 1.0), ("500g", 2.10)]),
        ("Leinsamen", 2.40, [("250g", 1.0)]),
        ("Chiasamen", 4.50, [("200g", 1.0)]),
        ("Sesam", 2.80, [("200g", 1.0)]),
        ("Hanfsamen", 5.90, [("200g", 1.0)]),
        ("Macadamia", 7.80, [("150g", 1.0)]),
        ("Pecannüsse", 6.20, [("150g", 1.0)]),
        ("Paranüsse", 5.80, [("200g", 1.0)]),
        ("Mandelsplitter", 3.90, [("200g", 1.0)]),
        ("Erdnüsse ungesalzen", 2.50, [("300g", 1.0)]),
        ("Mandelmehl", 5.50, [("250g", 1.0)]),
        ("Kokosraspeln", 2.20, [("200g", 1.0)]),
        ("Studentenfutter Deluxe", 5.80, [("250g", 1.0)]),
    ],
    "ready_meals": [
        ("Fertig-Risotto Pilz", 4.90, [("350g", 1.0)]),
        ("Fertig-Risotto Safran", 5.20, [("350g", 1.0)]),
        ("Poulet Tikka Masala", 6.90, [("400g", 1.0)]),
        ("Pasta Bolognese", 4.50, [("400g", 1.0)]),
        ("Poulet Sweet & Sour", 6.50, [("400g", 1.0)]),
        ("Chili con Carne", 5.80, [("400g", 1.0)]),
        ("Thai Green Curry", 6.20, [("400g", 1.0)]),
        ("Lasagne Bolognese", 5.90, [("400g", 1.0)]),
        ("Rinds-Gulasch", 7.20, [("400g", 1.0)]),
        ("Älplermagronen fertig", 4.80, [("350g", 1.0)]),
        ("Ghackets mit Hörnli", 5.50, [("400g", 1.0)]),
        ("Gemüse-Curry", 5.20, [("400g", 1.0)]),
        ("Chicken Wrap Kit", 7.90, [("Kit", 1.0)]),
        ("Fajita Kit", 7.50, [("Kit", 1.0)]),
        ("Sushi Box", 9.80, [("8 Stk", 1.0), ("16 Stk", 1.80)]),
        ("Sandwich Poulet", 4.50, [("Stk", 1.0)]),
        ("Sandwich Lachs", 5.20, [("Stk", 1.0)]),
        ("Bowl Teriyaki", 7.50, [("400g", 1.0)]),
        ("Bowl Buddha", 6.90, [("400g", 1.0)]),
        ("Ravioli Ricotta Spinat", 5.50, [("400g", 1.0)]),
        ("Pad Thai fertig", 6.20, [("400g", 1.0)]),
        ("Falafel Teller", 6.50, [("350g", 1.0)]),
        ("Mezze Platte", 8.90, [("400g", 1.0)]),
        ("Bento Box", 9.50, [("Stk", 1.0)]),
        ("Quiche Lorraine", 5.90, [("Stk", 1.0)]),
    ],
}

# Brand categories per retailer that can prefix product names
_BRAND_BUDGET = "budget"
_BRAND_BIO = "bio"


def _deterministic_uuid(retailer: str, name: str) -> uuid.UUID:
    """Generate a deterministic UUID from retailer:name using MD5."""
    hex_digest = hashlib.md5(f"{retailer}:{name}".encode()).hexdigest()
    return uuid.UUID(hex_digest)


def _generate_ean(seed_val: int) -> str:
    """Generate a fake but realistic 13-digit Swiss EAN barcode (7610000xxxxxx)."""
    rng = random.Random(seed_val)
    # Swiss prefix: 76, followed by manufacturer 10000, then product digits
    base = f"761{rng.randint(0, 9999999):07d}"  # 10 digits
    # Calculate EAN-13 check digit
    digits = [int(d) for d in base]
    total = sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits))
    # Pad to 12 digits before check
    base12 = base + f"{rng.randint(0, 9):01d}{rng.randint(0, 9):01d}"
    digits12 = [int(d) for d in base12[:12]]
    total = sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits12))
    check = (10 - (total % 10)) % 10
    return base12[:12] + str(check)


def _product_image_url(name: str) -> str:
    """Generate a placeholder image URL for a product."""
    encoded = quote(name, safe="")
    return f"https://placehold.co/200x200/1a1a1a/white?text={encoded}"


def _brand_prefix(retailer: str, brand_type: str) -> str:
    """Return the brand prefix string for a retailer and brand type."""
    return RETAILER_BRANDS[retailer][brand_type]


def _nutritional_info(category: str, rng: random.Random) -> dict:
    """Generate realistic nutritional info with slight variation per product."""
    base = CATEGORY_NUTRITION.get(category, (100, 5.0, 3.0, 15.0))
    cal, prot, fat, carbs = base
    # Add +-20% variation
    factor = lambda: rng.uniform(0.80, 1.20)  # noqa: E731
    return {
        "calories_per_100g": round(cal * factor(), 1),
        "protein_g": round(prot * factor(), 1),
        "fat_g": round(fat * factor(), 1),
        "carbs_g": round(carbs * factor(), 1),
    }


def _allergen_tags(category: str, name: str, rng: random.Random) -> list[str]:
    """Generate allergen tags based on category and product name."""
    base = list(CATEGORY_ALLERGENS.get(category, []))
    # Add context-specific allergens
    name_lower = name.lower()
    if any(
        w in name_lower
        for w in ["nuss", "mandel", "cashew", "hasel", "macadamia", "pecan", "pistazie"]
    ):
        if "nuts" not in base:
            base.append("nuts")
    if any(w in name_lower for w in ["ei ", "eier"]):
        if "eggs" not in base:
            base.append("eggs")
    if any(w in name_lower for w in ["soja", "tofu", "edamame"]):
        if "soy" not in base:
            base.append("soy")
    if any(
        w in name_lower
        for w in ["milch", "rahm", "käse", "joghurt", "butter", "quark", "mascarpone"]
    ):
        if "lactose" not in base:
            base.append("lactose")
    if any(
        w in name_lower
        for w in [
            "brot",
            "mehl",
            "pasta",
            "spaghetti",
            "penne",
            "nudel",
            "zopf",
            "gipfel",
        ]
    ):
        if "gluten" not in base:
            base.append("gluten")
    return base


def generate_demo_products(seed: int = 42) -> list[dict]:
    """Generate 12,000+ demo products across 5 retailers and 25 categories.

    Strategy per base product:
    - 5 retailers with +/-15% price variation
    - 2-3 size variants per product
    - Standard-brand variant always generated
    - ~38% get a Budget brand variant
    - ~30% get a Bio/Premium brand variant
    - ~20% get an Extra brand variant
    - ~8% get a Fairtrade variant
    - ~6% get a Demeter variant
    - ~5% get an IP-Suisse variant
    - ~20% of all products have a discount (10-40%)

    Returns a list of product dicts ready for DB insertion and Qdrant upsert.
    """
    rng = random.Random(seed)
    products: list[dict] = []
    seen_ids: set[str] = set()
    ean_counter = 0

    def _add_product(
        retailer: str,
        name: str,
        price: float,
        category: str,
    ) -> None:
        nonlocal ean_counter
        # Deterministic id
        product_id = _deterministic_uuid(retailer, name)
        id_str = str(product_id)
        if id_str in seen_ids:
            return
        seen_ids.add(id_str)

        # ~20% chance of discount
        discount_pct: float | None = None
        if rng.random() < 0.20:
            discount_pct = float(rng.choice(DISCOUNT_VALUES))

        # EAN barcode
        ean_counter += 1
        ean = _generate_ean(seed + ean_counter)

        products.append(
            {
                "id": product_id,
                "retailer": retailer,
                "name": name,
                "price": Decimal(str(round(price, 2))),
                "category": category,
                "discount_pct": discount_pct,
                "region": "zurich",
                "image_url": _product_image_url(name),
                "source": "demo",
                "ean": ean,
                "nutritional_info": _nutritional_info(category, rng),
                "allergens": _allergen_tags(category, name, rng),
            }
        )

    for category, items in CATEGORY_PRODUCTS.items():
        for base_name, base_price, size_variants in items:
            for retailer in RETAILERS:
                # Retailer-specific price factor (+/-15%)
                retailer_factor = rng.uniform(0.85, 1.15)

                for size_suffix, size_multiplier in size_variants:
                    price = base_price * size_multiplier * retailer_factor

                    # 1) Generic / unbranded product
                    full_name = f"{base_name} {size_suffix}"
                    _add_product(retailer, full_name, price, category)

                    # 2) Retailer standard-brand variant (always)
                    std_brand = _brand_prefix(retailer, "standard")
                    std_name = f"{std_brand} {base_name} {size_suffix}"
                    std_price = price * rng.uniform(0.95, 1.05)
                    _add_product(retailer, std_name, std_price, category)

                    # 3) Budget variant (~38%)
                    if rng.random() < 0.38:
                        budget_brand = _brand_prefix(retailer, _BRAND_BUDGET)
                        budget_name = f"{budget_brand} {base_name} {size_suffix}"
                        budget_price = price * rng.uniform(0.60, 0.78)
                        _add_product(retailer, budget_name, budget_price, category)

                    # 4) Bio/Premium variant (~30%)
                    if rng.random() < 0.30:
                        bio_brand = _brand_prefix(retailer, _BRAND_BIO)
                        bio_name = f"{bio_brand} {base_name} {size_suffix}"
                        bio_price = price * rng.uniform(1.20, 1.50)
                        _add_product(retailer, bio_name, bio_price, category)

                    # 5) Extra brand variant (~20%)
                    if rng.random() < 0.20:
                        extra_brand = _brand_prefix(retailer, "extra")
                        extra_name = f"{extra_brand} {base_name} {size_suffix}"
                        extra_price = price * rng.uniform(0.90, 1.15)
                        _add_product(retailer, extra_name, extra_price, category)

                    # 6) Fairtrade variant (~8%)
                    if rng.random() < 0.08:
                        ft_brand = _brand_prefix(retailer, "fairtrade")
                        ft_name = f"{ft_brand} {base_name} {size_suffix}"
                        ft_price = price * rng.uniform(1.15, 1.40)
                        _add_product(retailer, ft_name, ft_price, category)

                    # 7) Demeter variant (~6%)
                    if rng.random() < 0.06:
                        dm_brand = _brand_prefix(retailer, "demeter")
                        dm_name = f"{dm_brand} {base_name} {size_suffix}"
                        dm_price = price * rng.uniform(1.30, 1.60)
                        _add_product(retailer, dm_name, dm_price, category)

                    # 8) IP-Suisse variant (~5%)
                    if rng.random() < 0.05:
                        ip_brand = _brand_prefix(retailer, "ip_suisse")
                        ip_name = f"{ip_brand} {base_name} {size_suffix}"
                        ip_price = price * rng.uniform(1.10, 1.35)
                        _add_product(retailer, ip_name, ip_price, category)

    return products


# Pre-compute count so other modules can reference it without generating the full list
PRODUCT_COUNT = len(generate_demo_products())
