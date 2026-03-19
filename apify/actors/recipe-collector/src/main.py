"""
Recipe Collector - Apify Actor
Collects recipes from open sources (RSS feeds, RecipeNLG, curated Swiss classics)
and formats them for korb.guru's meal planning system.
"""

import asyncio
import logging
import time
from typing import Any

import feedparser
import httpx
from apify import Actor

# Configure root logger so output appears in Apify console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RSS Feed Configuration
# ---------------------------------------------------------------------------
RSS_FEEDS: dict[str, str] = {
    "chefkoch_tagesrezept": "https://www.chefkoch.de/rss/tagesrezept.xml",
    "chefkoch_rezeptdestages": "https://www.chefkoch.de/rss/rezept-des-tages.xml",
    "allrecipes": "https://www.allrecipes.com/feeds/",
    "srf_apoint": "https://www.srf.ch/sendungen/a-point/rezepte/rss/feed",
}

# ---------------------------------------------------------------------------
# Curated Swiss Classics (fallback source)
# ---------------------------------------------------------------------------
SWISS_CLASSICS: list[dict[str, Any]] = [
    {"title": "Zürcher Geschnetzeltes", "description": "Geschnetzeltes Kalbfleisch in Rahmsauce mit Rösti.", "ingredients": [{"name": "Kalbfleisch", "quantity": "400", "unit": "g"}, {"name": "Champignons", "quantity": "200", "unit": "g"}, {"name": "Rahm", "quantity": "2", "unit": "dl"}, {"name": "Weisswein", "quantity": "1", "unit": "dl"}, {"name": "Zwiebel", "quantity": "1", "unit": "Stück"}, {"name": "Butter", "quantity": "30", "unit": "g"}], "instructions": "Kalbfleisch in Streifen schneiden. Zwiebel fein hacken und in Butter andünsten. Fleisch portionsweise scharf anbraten. Champignons dazugeben, mit Weisswein ablöschen. Rahm beifügen, köcheln lassen bis Sauce eindickt. Mit Salz und Pfeffer abschmecken.", "time_minutes": 35, "servings": 4, "type": "protein", "tags": ["swiss", "zurich", "classic"]},
    {"title": "Rösti", "description": "Knusprige Schweizer Kartoffelrösti.", "ingredients": [{"name": "Kartoffeln", "quantity": "800", "unit": "g"}, {"name": "Butter", "quantity": "40", "unit": "g"}, {"name": "Salz", "quantity": "1", "unit": "TL"}], "instructions": "Kartoffeln am Vortag kochen, schälen und raffeln. In Butter in einer Bratpfanne flach drücken. Bei mittlerer Hitze goldbraun braten, wenden und zweite Seite ebenso braten.", "time_minutes": 30, "servings": 4, "type": "carb", "tags": ["swiss", "bern", "classic", "vegetarian"]},
    {"title": "Birchermüesli", "description": "Original Birchermüesli nach Dr. Bircher-Benner.", "ingredients": [{"name": "Haferflocken", "quantity": "200", "unit": "g"}, {"name": "Milch", "quantity": "2", "unit": "dl"}, {"name": "Joghurt", "quantity": "200", "unit": "g"}, {"name": "Äpfel", "quantity": "2", "unit": "Stück"}, {"name": "Zitronensaft", "quantity": "1", "unit": "EL"}, {"name": "Honig", "quantity": "2", "unit": "EL"}, {"name": "Haselnüsse", "quantity": "30", "unit": "g"}], "instructions": "Haferflocken in Milch einweichen (mind. 2 Stunden oder über Nacht). Äpfel raffeln, mit Zitronensaft mischen. Joghurt, Äpfel und Honig unter die Haferflocken rühren. Mit gehackten Haselnüssen bestreuen.", "time_minutes": 15, "servings": 4, "type": "carb", "tags": ["swiss", "classic", "vegetarian", "breakfast"]},
    {"title": "Fondue Moitié-Moitié", "description": "Klassisches Schweizer Käsefondue mit Gruyère und Vacherin.", "ingredients": [{"name": "Gruyère", "quantity": "400", "unit": "g"}, {"name": "Vacherin Fribourgeois", "quantity": "400", "unit": "g"}, {"name": "Weisswein", "quantity": "3", "unit": "dl"}, {"name": "Knoblauch", "quantity": "1", "unit": "Zehe"}, {"name": "Maisstärke", "quantity": "1", "unit": "EL"}, {"name": "Kirsch", "quantity": "2", "unit": "EL"}, {"name": "Brot", "quantity": "800", "unit": "g"}], "instructions": "Caquelon mit Knoblauch ausreiben. Käse reiben. Wein erhitzen, Käse portionsweise einrühren. Maisstärke in Kirsch auflösen, unterrühren. Unter ständigem Rühren schmelzen lassen. Mit Brotwürfeln servieren.", "time_minutes": 30, "servings": 4, "type": "protein", "tags": ["swiss", "fribourg", "classic", "vegetarian"]},
    {"title": "Raclette", "description": "Traditionelles Walliser Raclette mit Beilagen.", "ingredients": [{"name": "Raclette-Käse", "quantity": "800", "unit": "g"}, {"name": "Kartoffeln", "quantity": "1", "unit": "kg"}, {"name": "Cornichons", "quantity": "1", "unit": "Glas"}, {"name": "Silberzwiebeln", "quantity": "1", "unit": "Glas"}, {"name": "Pfeffer", "quantity": "1", "unit": "Prise"}], "instructions": "Kartoffeln mit Schale kochen. Raclette-Käse in Scheiben schneiden. Käse im Raclette-Ofen oder unter dem Grill schmelzen. Mit Gschwellti, Cornichons und Silberzwiebeln servieren.", "time_minutes": 40, "servings": 4, "type": "protein", "tags": ["swiss", "valais", "classic", "vegetarian"]},
    {"title": "Älplermagronen", "description": "Schweizer Hirtenmakkaroni mit Kartoffeln, Käse und Apfelmus.", "ingredients": [{"name": "Makkaroni", "quantity": "300", "unit": "g"}, {"name": "Kartoffeln", "quantity": "400", "unit": "g"}, {"name": "Gruyère", "quantity": "200", "unit": "g"}, {"name": "Rahm", "quantity": "2", "unit": "dl"}, {"name": "Zwiebeln", "quantity": "2", "unit": "Stück"}, {"name": "Butter", "quantity": "30", "unit": "g"}, {"name": "Apfelmus", "quantity": "200", "unit": "g"}], "instructions": "Kartoffeln schälen und würfeln. In Salzwasser garen, Makkaroni dazugeben. Abgiessen. Zwiebeln in Butter goldbraun rösten. Nudeln, Kartoffeln und geriebenen Käse schichtweise in eine Form geben. Rahm darüber giessen. Im Ofen bei 200°C überbacken. Mit Apfelmus servieren.", "time_minutes": 45, "servings": 4, "type": "carb", "tags": ["swiss", "classic", "vegetarian"]},
    {"title": "Capuns", "description": "Bündner Mangoldwickel mit Spätzleteig und Salsiz.", "ingredients": [{"name": "Mangoldblätter", "quantity": "20", "unit": "Stück"}, {"name": "Mehl", "quantity": "250", "unit": "g"}, {"name": "Milch", "quantity": "1.5", "unit": "dl"}, {"name": "Eier", "quantity": "2", "unit": "Stück"}, {"name": "Salsiz", "quantity": "100", "unit": "g"}, {"name": "Bündnerfleisch", "quantity": "50", "unit": "g"}, {"name": "Bouillon", "quantity": "5", "unit": "dl"}, {"name": "Rahm", "quantity": "1", "unit": "dl"}, {"name": "Bergkäse", "quantity": "100", "unit": "g"}], "instructions": "Spätzleteig aus Mehl, Eiern und Milch herstellen. Salsiz und Bündnerfleisch fein würfeln, unter den Teig mischen. Mangoldblätter blanchieren. Je 1 EL Füllung auf jedes Blatt geben, einrollen. In Bouillon pochieren. Mit Rahm und geriebenem Käse überbacken.", "time_minutes": 60, "servings": 4, "type": "protein", "tags": ["swiss", "graubünden", "classic"]},
    {"title": "Basler Mehlsuppe", "description": "Traditionelle Basler Mehlsuppe, serviert an der Fasnacht.", "ingredients": [{"name": "Mehl", "quantity": "80", "unit": "g"}, {"name": "Butter", "quantity": "60", "unit": "g"}, {"name": "Zwiebeln", "quantity": "2", "unit": "Stück"}, {"name": "Rindsbrühe", "quantity": "1", "unit": "l"}, {"name": "Gruyère", "quantity": "100", "unit": "g"}], "instructions": "Butter schmelzen, Mehl einrühren und unter ständigem Rühren dunkel rösten (ca. 15 Min). Fein gehackte Zwiebeln beifügen. Mit Brühe ablöschen, glatt rühren. 30 Min köcheln lassen. Mit geriebenem Käse servieren.", "time_minutes": 50, "servings": 4, "type": "carb", "tags": ["swiss", "basel", "classic", "fasnacht"]},
    {"title": "Berner Platte", "description": "Deftige Berner Fleischplatte mit verschiedenen Fleisch- und Wurstwaren.", "ingredients": [{"name": "Rippli", "quantity": "400", "unit": "g"}, {"name": "Zungenwurst", "quantity": "2", "unit": "Stück"}, {"name": "Speck", "quantity": "200", "unit": "g"}, {"name": "Sauerkraut", "quantity": "500", "unit": "g"}, {"name": "Kartoffeln", "quantity": "800", "unit": "g"}, {"name": "Dörrbohnen", "quantity": "200", "unit": "g"}], "instructions": "Dörrbohnen über Nacht einweichen. Rippli und Speck in Wasser sanft garen. Sauerkraut separat kochen. Zungenwurst im letzten Moment erwärmen. Kartoffeln kochen. Alles auf einer grossen Platte anrichten.", "time_minutes": 120, "servings": 6, "type": "protein", "tags": ["swiss", "bern", "classic", "winter"]},
    {"title": "Zopf (Butterzopf)", "description": "Schweizer Sonntagszopf aus Hefeteig.", "ingredients": [{"name": "Mehl", "quantity": "500", "unit": "g"}, {"name": "Butter", "quantity": "80", "unit": "g"}, {"name": "Milch", "quantity": "2.5", "unit": "dl"}, {"name": "Hefe", "quantity": "1", "unit": "Würfel"}, {"name": "Zucker", "quantity": "1", "unit": "EL"}, {"name": "Salz", "quantity": "1", "unit": "TL"}, {"name": "Ei", "quantity": "1", "unit": "Stück"}], "instructions": "Hefe in lauwarmer Milch auflösen. Mehl, Butter, Zucker und Salz vermengen. Hefemilch dazugeben, zu einem geschmeidigen Teig kneten. 1.5 Stunden aufgehen lassen. Zwei Stränge formen und flechten. Mit verquirltem Ei bestreichen. Bei 200°C ca. 35 Min backen.", "time_minutes": 150, "servings": 8, "type": "carb", "tags": ["swiss", "classic", "baking", "breakfast"]},
    {"title": "Bündner Gerstensuppe", "description": "Herzhafte Graubündner Gerstensuppe mit Trockenfleisch.", "ingredients": [{"name": "Rollgerste", "quantity": "150", "unit": "g"}, {"name": "Bündnerfleisch", "quantity": "100", "unit": "g"}, {"name": "Speck", "quantity": "100", "unit": "g"}, {"name": "Karotten", "quantity": "2", "unit": "Stück"}, {"name": "Lauch", "quantity": "1", "unit": "Stück"}, {"name": "Sellerie", "quantity": "100", "unit": "g"}, {"name": "Kartoffeln", "quantity": "200", "unit": "g"}, {"name": "Bouillon", "quantity": "1.5", "unit": "l"}, {"name": "Rahm", "quantity": "1", "unit": "dl"}], "instructions": "Gerste über Nacht einweichen. Speck würfeln und auslassen. Gemüse rüsten und anbraten. Gerste und Bouillon beifügen. Ca. 1.5 Stunden köcheln. Bündnerfleisch in Streifen schneiden, zum Schluss beifügen. Mit Rahm verfeinern.", "time_minutes": 120, "servings": 4, "type": "protein", "tags": ["swiss", "graubünden", "classic", "winter", "soup"]},
    {"title": "Saucisson mit Lauch", "description": "Waadtländer Saucisson auf Lauchgemüse.", "ingredients": [{"name": "Saucisson vaudois", "quantity": "1", "unit": "Stück"}, {"name": "Lauch", "quantity": "4", "unit": "Stangen"}, {"name": "Kartoffeln", "quantity": "600", "unit": "g"}, {"name": "Butter", "quantity": "30", "unit": "g"}, {"name": "Senf", "quantity": "2", "unit": "EL"}], "instructions": "Saucisson in kaltes Wasser legen, langsam erhitzen und ca. 40 Min bei schwacher Hitze ziehen lassen. Lauch in Ringe schneiden, in Butter dünsten. Kartoffeln kochen. Saucisson aufschneiden, mit Lauch, Kartoffeln und Senf servieren.", "time_minutes": 50, "servings": 4, "type": "protein", "tags": ["swiss", "waadt", "classic"]},
    {"title": "Papet Vaudois", "description": "Waadtländer Lauch-Kartoffel-Eintopf mit Saucisson.", "ingredients": [{"name": "Lauch", "quantity": "800", "unit": "g"}, {"name": "Kartoffeln", "quantity": "600", "unit": "g"}, {"name": "Saucisson", "quantity": "1", "unit": "Stück"}, {"name": "Rahm", "quantity": "1", "unit": "dl"}, {"name": "Butter", "quantity": "30", "unit": "g"}], "instructions": "Lauch in Stücke schneiden, Kartoffeln schälen und würfeln. Beides in Butter andünsten, mit wenig Wasser weich kochen. Leicht zerstampfen. Saucisson separat garen. Rahm unter das Gemüse rühren. Zusammen servieren.", "time_minutes": 60, "servings": 4, "type": "protein", "tags": ["swiss", "waadt", "classic"]},
    {"title": "Maluns", "description": "Bündner Kartoffelgericht mit Butter und Apfelmus.", "ingredients": [{"name": "Kartoffeln", "quantity": "1", "unit": "kg"}, {"name": "Mehl", "quantity": "150", "unit": "g"}, {"name": "Butter", "quantity": "100", "unit": "g"}, {"name": "Alpkäse", "quantity": "100", "unit": "g"}, {"name": "Apfelmus", "quantity": "200", "unit": "g"}], "instructions": "Kartoffeln am Vortag kochen und schälen. Raffeln und mit Mehl mischen. In reichlich Butter in einer Bratpfanne unter ständigem Wenden rösten, bis goldbraune Brösel entstehen (ca. 30 Min). Mit geriebenem Alpkäse und Apfelmus servieren.", "time_minutes": 45, "servings": 4, "type": "carb", "tags": ["swiss", "graubünden", "classic", "vegetarian"]},
    {"title": "Polenta mit Kaninchen", "description": "Tessiner Polenta mit geschmortem Kaninchen.", "ingredients": [{"name": "Kaninchen", "quantity": "1", "unit": "Stück"}, {"name": "Polenta", "quantity": "300", "unit": "g"}, {"name": "Rotwein", "quantity": "3", "unit": "dl"}, {"name": "Tomaten", "quantity": "400", "unit": "g"}, {"name": "Rosmarin", "quantity": "2", "unit": "Zweige"}, {"name": "Knoblauch", "quantity": "3", "unit": "Zehen"}, {"name": "Olivenöl", "quantity": "3", "unit": "EL"}], "instructions": "Kaninchen in Stücke teilen, in Olivenöl anbraten. Knoblauch und Rosmarin dazugeben. Mit Rotwein ablöschen, Tomaten beifügen. Zugedeckt ca. 1.5 Stunden schmoren. Polenta nach Packungsanleitung kochen. Zusammen servieren.", "time_minutes": 120, "servings": 4, "type": "protein", "tags": ["swiss", "ticino", "classic"]},
    {"title": "Risotto alla Ticinese", "description": "Tessiner Risotto mit Luganighe-Wurst.", "ingredients": [{"name": "Risotto-Reis", "quantity": "300", "unit": "g"}, {"name": "Luganighe", "quantity": "300", "unit": "g"}, {"name": "Zwiebel", "quantity": "1", "unit": "Stück"}, {"name": "Weisswein", "quantity": "1", "unit": "dl"}, {"name": "Bouillon", "quantity": "8", "unit": "dl"}, {"name": "Parmesan", "quantity": "80", "unit": "g"}, {"name": "Butter", "quantity": "30", "unit": "g"}], "instructions": "Zwiebel fein hacken und in Butter andünsten. Reis beifügen und glasig rühren. Mit Wein ablöschen. Bouillon kellenweise beifügen, unter Rühren einkochen lassen. Luganighe separat braten. Parmesan unter den Risotto rühren. Mit Wurst servieren.", "time_minutes": 40, "servings": 4, "type": "carb", "tags": ["swiss", "ticino", "classic"]},
    {"title": "Schweizer Kartoffelgratin", "description": "Cremiger Kartoffelgratin mit Gruyère.", "ingredients": [{"name": "Kartoffeln", "quantity": "1", "unit": "kg"}, {"name": "Rahm", "quantity": "3", "unit": "dl"}, {"name": "Milch", "quantity": "2", "unit": "dl"}, {"name": "Gruyère", "quantity": "150", "unit": "g"}, {"name": "Knoblauch", "quantity": "1", "unit": "Zehe"}, {"name": "Muskatnuss", "quantity": "1", "unit": "Prise"}], "instructions": "Kartoffeln schälen und in dünne Scheiben schneiden. Form mit Knoblauch ausreiben und buttern. Kartoffelscheiben schichtweise einlegen, salzen und mit Käse bestreuen. Rahm und Milch mit Muskatnuss mischen und darüber giessen. Bei 180°C ca. 60 Min backen.", "time_minutes": 75, "servings": 4, "type": "carb", "tags": ["swiss", "classic", "vegetarian"]},
    {"title": "Ghackets mit Hörnli", "description": "Schweizer Hackfleischsauce mit Hörnli-Nudeln und Apfelmus.", "ingredients": [{"name": "Rindshackfleisch", "quantity": "500", "unit": "g"}, {"name": "Hörnli", "quantity": "400", "unit": "g"}, {"name": "Zwiebeln", "quantity": "2", "unit": "Stück"}, {"name": "Tomatenpüree", "quantity": "2", "unit": "EL"}, {"name": "Bouillon", "quantity": "2", "unit": "dl"}, {"name": "Apfelmus", "quantity": "200", "unit": "g"}], "instructions": "Zwiebeln fein hacken und anbraten. Hackfleisch beifügen und krümelig braten. Tomatenpüree einrühren, mit Bouillon ablöschen. 15 Min köcheln. Hörnli nach Packungsanleitung kochen. Zusammen mit Apfelmus servieren.", "time_minutes": 30, "servings": 4, "type": "protein", "tags": ["swiss", "classic", "comfort"]},
    {"title": "Pastetli", "description": "Schweizer Blätterteigpastetchen mit Ragout fin.", "ingredients": [{"name": "Blätterteig-Pastetli", "quantity": "4", "unit": "Stück"}, {"name": "Kalbfleisch", "quantity": "300", "unit": "g"}, {"name": "Champignons", "quantity": "200", "unit": "g"}, {"name": "Rahm", "quantity": "2", "unit": "dl"}, {"name": "Weisswein", "quantity": "1", "unit": "dl"}, {"name": "Butter", "quantity": "30", "unit": "g"}, {"name": "Mehl", "quantity": "1", "unit": "EL"}], "instructions": "Kalbfleisch in kleine Würfel schneiden und anbraten. Champignons in Scheiben schneiden und mitbraten. Mehl darüber stäuben, mit Wein und Rahm ablöschen. Köcheln lassen bis die Sauce eindickt. Pastetli im Ofen erwärmen. Ragout einfüllen und servieren.", "time_minutes": 35, "servings": 4, "type": "protein", "tags": ["swiss", "classic"]},
    {"title": "Vermicelles", "description": "Schweizer Marroni-Dessert.", "ingredients": [{"name": "Marroni (gekocht)", "quantity": "500", "unit": "g"}, {"name": "Zucker", "quantity": "100", "unit": "g"}, {"name": "Rahm", "quantity": "3", "unit": "dl"}, {"name": "Vanillezucker", "quantity": "1", "unit": "Päckchen"}, {"name": "Kirsch", "quantity": "1", "unit": "EL"}, {"name": "Meringue", "quantity": "4", "unit": "Stück"}], "instructions": "Marroni mit Zucker und wenig Wasser weich kochen. Pürieren und durch das Passevite drücken. Kirsch unterrühren. Rahm mit Vanillezucker steif schlagen. Marronimasse durch Spätzlipresse auf Teller drücken. Mit Schlagrahm und Meringue anrichten.", "time_minutes": 45, "servings": 4, "type": "dessert", "tags": ["swiss", "classic", "autumn"]},
    {"title": "Engadiner Nusstorte", "description": "Bündner Nusstorte mit Baumnüssen und Caramel.", "ingredients": [{"name": "Mehl", "quantity": "350", "unit": "g"}, {"name": "Butter", "quantity": "200", "unit": "g"}, {"name": "Zucker", "quantity": "200", "unit": "g"}, {"name": "Baumnüsse", "quantity": "300", "unit": "g"}, {"name": "Rahm", "quantity": "2", "unit": "dl"}, {"name": "Honig", "quantity": "2", "unit": "EL"}, {"name": "Ei", "quantity": "1", "unit": "Stück"}], "instructions": "Mürbeteig aus Mehl, 130g Butter, 50g Zucker und Ei herstellen. Kühlen. Restlichen Zucker caramelisieren, Rahm, Honig und restliche Butter beifügen. Nüsse unterrühren. Teig ausrollen, Form auslegen. Füllung einfüllen, mit Teigdeckel verschliessen. Bei 180°C ca. 40 Min backen.", "time_minutes": 90, "servings": 12, "type": "dessert", "tags": ["swiss", "graubünden", "classic", "baking"]},
    {"title": "Basler Läckerli", "description": "Traditionelles Basler Honig-Gewürzgebäck.", "ingredients": [{"name": "Honig", "quantity": "250", "unit": "g"}, {"name": "Zucker", "quantity": "200", "unit": "g"}, {"name": "Mandeln", "quantity": "200", "unit": "g"}, {"name": "Orangeat", "quantity": "50", "unit": "g"}, {"name": "Zitronat", "quantity": "50", "unit": "g"}, {"name": "Mehl", "quantity": "300", "unit": "g"}, {"name": "Zimt", "quantity": "1", "unit": "TL"}, {"name": "Nelkenpulver", "quantity": "0.5", "unit": "TL"}, {"name": "Kirsch", "quantity": "2", "unit": "EL"}], "instructions": "Honig und Zucker erhitzen. Gehackte Mandeln, Orangeat, Zitronat, Gewürze und Kirsch beifügen. Mehl unterrühren. Teig auf einem Blech ca. 1 cm dick ausstreichen. Bei 180°C ca. 20 Min backen. Noch warm mit Zuckerglasur bestreichen und in Rechtecke schneiden.", "time_minutes": 45, "servings": 30, "type": "dessert", "tags": ["swiss", "basel", "classic", "baking", "christmas"]},
    {"title": "Tirggel", "description": "Zürcher Honiggebäck mit Prägung.", "ingredients": [{"name": "Honig", "quantity": "500", "unit": "g"}, {"name": "Mehl", "quantity": "500", "unit": "g"}, {"name": "Zucker", "quantity": "50", "unit": "g"}], "instructions": "Honig erwärmen. Mehl und Zucker einrühren, bis ein glatter Teig entsteht. Teig dünn ausrollen, in Tirggel-Formen pressen. Auf einem Blech bei 300°C kurz backen, bis die Oberfläche goldbraun ist (ca. 3-5 Min).", "time_minutes": 60, "servings": 20, "type": "dessert", "tags": ["swiss", "zurich", "classic", "christmas", "baking"]},
    {"title": "Zuger Kirschtorte", "description": "Berühmte Zuger Torte mit Kirsch und Buttercreme.", "ingredients": [{"name": "Eier", "quantity": "6", "unit": "Stück"}, {"name": "Zucker", "quantity": "200", "unit": "g"}, {"name": "Mehl", "quantity": "100", "unit": "g"}, {"name": "Butter", "quantity": "200", "unit": "g"}, {"name": "Kirsch", "quantity": "5", "unit": "cl"}, {"name": "Haselnüsse", "quantity": "100", "unit": "g"}, {"name": "Puderzucker", "quantity": "100", "unit": "g"}], "instructions": "Biskuit aus Eiern, Zucker und Mehl backen. Japonais-Boden aus Haselnüssen und Eiweiss backen. Buttercreme aus Butter und Zucker herstellen. Böden mit Kirsch tränken, mit Buttercreme füllen und bestreichen. Mit Puderzucker bestäuben.", "time_minutes": 120, "servings": 12, "type": "dessert", "tags": ["swiss", "zug", "classic", "baking"]},
    {"title": "Aargauer Rüeblitorte", "description": "Schweizer Rüeblitorte (Karottenkuchen) mit Zuckerguss.", "ingredients": [{"name": "Karotten", "quantity": "300", "unit": "g"}, {"name": "Mandeln", "quantity": "300", "unit": "g"}, {"name": "Zucker", "quantity": "250", "unit": "g"}, {"name": "Eier", "quantity": "5", "unit": "Stück"}, {"name": "Zitrone", "quantity": "1", "unit": "Stück"}, {"name": "Backpulver", "quantity": "1", "unit": "TL"}, {"name": "Kirsch", "quantity": "2", "unit": "EL"}, {"name": "Puderzucker", "quantity": "200", "unit": "g"}], "instructions": "Karotten und Mandeln fein reiben. Eier trennen, Eigelb mit Zucker schaumig schlagen. Karotten, Mandeln, Zitronensaft, Kirsch und Backpulver unterheben. Eiweiss steif schlagen und unterheben. Bei 180°C ca. 50 Min backen. Mit Puderzucker-Zitronensaft-Glasur überziehen. Mit Marzipan-Rüebli dekorieren.", "time_minutes": 80, "servings": 12, "type": "dessert", "tags": ["swiss", "aargau", "classic", "baking", "gluten-free"]},
    {"title": "Cholermues", "description": "Innerschweizer Mehlspeise aus der Pfanne.", "ingredients": [{"name": "Mehl", "quantity": "200", "unit": "g"}, {"name": "Milch", "quantity": "3", "unit": "dl"}, {"name": "Eier", "quantity": "3", "unit": "Stück"}, {"name": "Butter", "quantity": "50", "unit": "g"}, {"name": "Zucker", "quantity": "2", "unit": "EL"}, {"name": "Zimt", "quantity": "1", "unit": "TL"}], "instructions": "Aus Mehl, Milch und Eiern einen dickflüssigen Teig rühren. Butter in einer grossen Pfanne erhitzen. Teig eingiessen und stocken lassen. Mit zwei Gabeln in Stücke reissen. Weiterbraten bis goldbraun. Mit Zucker und Zimt bestreuen.", "time_minutes": 20, "servings": 4, "type": "dessert", "tags": ["swiss", "innerschweiz", "classic", "vegetarian"]},
    {"title": "Chäshörnli", "description": "Schweizer Käse-Hörnli — die einfache Variante der Älplermagronen.", "ingredients": [{"name": "Hörnli", "quantity": "400", "unit": "g"}, {"name": "Gruyère", "quantity": "200", "unit": "g"}, {"name": "Appenzeller", "quantity": "100", "unit": "g"}, {"name": "Butter", "quantity": "30", "unit": "g"}, {"name": "Zwiebeln", "quantity": "2", "unit": "Stück"}], "instructions": "Hörnli al dente kochen. Zwiebeln in Butter goldbraun rösten. Käse reiben. Hörnli und Käse abwechselnd in eine Schüssel schichten. Röstzwiebeln darüber geben. Sofort servieren.", "time_minutes": 25, "servings": 4, "type": "carb", "tags": ["swiss", "classic", "vegetarian", "comfort"]},
    {"title": "Fondue Chinoise", "description": "Fleischfondue in heisser Bouillon mit Saucen.", "ingredients": [{"name": "Rindsfilet", "quantity": "200", "unit": "g"}, {"name": "Pouletbrust", "quantity": "200", "unit": "g"}, {"name": "Schweinsfilet", "quantity": "200", "unit": "g"}, {"name": "Rindsbrühe", "quantity": "1.5", "unit": "l"}, {"name": "Cocktailsauce", "quantity": "1", "unit": "Portion"}, {"name": "Tartarsauce", "quantity": "1", "unit": "Portion"}, {"name": "Curryrahm", "quantity": "1", "unit": "Portion"}, {"name": "Reis", "quantity": "300", "unit": "g"}], "instructions": "Fleisch in hauchdünne Scheiben schneiden. Brühe zum Kochen bringen und ins Fondue-Caquelon giessen. Fleisch mit Fonduegabeln in der Brühe garen. Mit verschiedenen Saucen und Reis servieren.", "time_minutes": 30, "servings": 4, "type": "protein", "tags": ["swiss", "classic", "winter", "christmas"]},
    {"title": "Zürcher Eintopf", "description": "Herzhafter Zürcher Eintopf mit Gemüse und Cervelat.", "ingredients": [{"name": "Cervelat", "quantity": "4", "unit": "Stück"}, {"name": "Kartoffeln", "quantity": "600", "unit": "g"}, {"name": "Karotten", "quantity": "3", "unit": "Stück"}, {"name": "Lauch", "quantity": "1", "unit": "Stange"}, {"name": "Bouillon", "quantity": "1", "unit": "l"}, {"name": "Senf", "quantity": "2", "unit": "EL"}], "instructions": "Kartoffeln und Karotten schälen und würfeln. Lauch in Ringe schneiden. In Bouillon weich kochen. Cervelat einschneiden und die letzten 10 Min mitgaren. Mit Senf servieren.", "time_minutes": 35, "servings": 4, "type": "protein", "tags": ["swiss", "zurich", "classic", "comfort"]},
    {"title": "Tessiner Risotto ai Funghi", "description": "Pilzrisotto auf Tessiner Art.", "ingredients": [{"name": "Risotto-Reis", "quantity": "300", "unit": "g"}, {"name": "Steinpilze", "quantity": "200", "unit": "g"}, {"name": "Zwiebel", "quantity": "1", "unit": "Stück"}, {"name": "Weisswein", "quantity": "1", "unit": "dl"}, {"name": "Bouillon", "quantity": "8", "unit": "dl"}, {"name": "Parmesan", "quantity": "80", "unit": "g"}, {"name": "Butter", "quantity": "30", "unit": "g"}, {"name": "Olivenöl", "quantity": "2", "unit": "EL"}], "instructions": "Pilze putzen und in Scheiben schneiden. In Olivenöl anbraten, beiseite stellen. Zwiebel in Butter andünsten. Reis beifügen, glasig rühren. Mit Wein ablöschen. Bouillon kellenweise einrühren. Vor dem Servieren Pilze und Parmesan unterheben.", "time_minutes": 35, "servings": 4, "type": "carb", "tags": ["swiss", "ticino", "classic", "vegetarian", "autumn"]},
    {"title": "Zwiebelkuchen", "description": "Schweizer Zwiebelkuchen (Zwiebelwähe).", "ingredients": [{"name": "Kuchenteig", "quantity": "1", "unit": "Rolle"}, {"name": "Zwiebeln", "quantity": "800", "unit": "g"}, {"name": "Speck", "quantity": "100", "unit": "g"}, {"name": "Eier", "quantity": "3", "unit": "Stück"}, {"name": "Rahm", "quantity": "2", "unit": "dl"}, {"name": "Kümmel", "quantity": "1", "unit": "TL"}], "instructions": "Zwiebeln in Ringe schneiden und in wenig Butter dünsten bis weich. Speck in Würfel schneiden und knusprig braten. Eier mit Rahm verquirlen, Kümmel, Salz und Pfeffer beifügen. Teig in eine Form legen, Zwiebeln und Speck darauf verteilen. Guss darüber giessen. Bei 200°C ca. 35 Min backen.", "time_minutes": 55, "servings": 6, "type": "carb", "tags": ["swiss", "classic", "autumn"]},
    {"title": "Appenzeller Siedwurst mit Kartoffelstock", "description": "Appenzeller Siedwurst mit cremigem Kartoffelstock.", "ingredients": [{"name": "Siedwurst", "quantity": "4", "unit": "Stück"}, {"name": "Kartoffeln", "quantity": "1", "unit": "kg"}, {"name": "Butter", "quantity": "50", "unit": "g"}, {"name": "Milch", "quantity": "2", "unit": "dl"}, {"name": "Muskatnuss", "quantity": "1", "unit": "Prise"}], "instructions": "Kartoffeln schälen, kochen und stampfen. Heisse Milch und Butter unterrühren. Mit Muskatnuss und Salz abschmecken. Siedwürste in heissem Wasser ca. 20 Min ziehen lassen. Mit Kartoffelstock und Senf servieren.", "time_minutes": 40, "servings": 4, "type": "protein", "tags": ["swiss", "appenzell", "classic", "comfort"]},
    {"title": "Suuri Lääberli (Basler Sauerleberli)", "description": "Basler saure Leber mit Rösti.", "ingredients": [{"name": "Kalbsleber", "quantity": "500", "unit": "g"}, {"name": "Zwiebeln", "quantity": "2", "unit": "Stück"}, {"name": "Butter", "quantity": "40", "unit": "g"}, {"name": "Weissweinessig", "quantity": "2", "unit": "EL"}, {"name": "Mehl", "quantity": "2", "unit": "EL"}, {"name": "Bouillon", "quantity": "2", "unit": "dl"}, {"name": "Salbei", "quantity": "4", "unit": "Blätter"}], "instructions": "Leber in Scheiben schneiden, in Mehl wenden. In Butter scharf anbraten. Zwiebeln und Salbei beifügen. Mit Essig ablöschen, Bouillon angiessen. Kurz köcheln lassen — Leber soll innen noch rosa sein. Mit Rösti servieren.", "time_minutes": 25, "servings": 4, "type": "protein", "tags": ["swiss", "basel", "classic"]},
    {"title": "Fotzelschnitten", "description": "Schweizer Variante von French Toast.", "ingredients": [{"name": "Zopfbrot (altbacken)", "quantity": "8", "unit": "Scheiben"}, {"name": "Eier", "quantity": "3", "unit": "Stück"}, {"name": "Milch", "quantity": "2", "unit": "dl"}, {"name": "Zucker", "quantity": "2", "unit": "EL"}, {"name": "Zimt", "quantity": "1", "unit": "TL"}, {"name": "Butter", "quantity": "40", "unit": "g"}], "instructions": "Eier mit Milch, Zucker und Zimt verquirlen. Brotscheiben darin einweichen. In Butter von beiden Seiten goldbraun braten. Mit Puderzucker bestäuben oder mit Kompott servieren.", "time_minutes": 15, "servings": 4, "type": "dessert", "tags": ["swiss", "classic", "vegetarian", "breakfast"]},
    {"title": "Glarner Pastete", "description": "Süsse Pastete aus dem Kanton Glarus.", "ingredients": [{"name": "Blätterteig", "quantity": "500", "unit": "g"}, {"name": "Mandeln", "quantity": "200", "unit": "g"}, {"name": "Zucker", "quantity": "150", "unit": "g"}, {"name": "Eier", "quantity": "2", "unit": "Stück"}, {"name": "Zitrone", "quantity": "1", "unit": "Stück"}, {"name": "Zwetschgenmus", "quantity": "200", "unit": "g"}], "instructions": "Mandeln mahlen, mit Zucker, Eiern und Zitronenzeste zu einer Masse verrühren. Blätterteig halbieren. Eine Hälfte in die Form legen. Zwetschgenmus darauf verteilen. Mandelmasse darüber geben. Mit zweiter Teighälfte abdecken. Bei 180°C ca. 40 Min backen.", "time_minutes": 60, "servings": 8, "type": "dessert", "tags": ["swiss", "glarus", "classic", "baking"]},
    {"title": "Minestrone Ticinese", "description": "Tessiner Gemüsesuppe mit Pasta.", "ingredients": [{"name": "Bohnen (weiss)", "quantity": "200", "unit": "g"}, {"name": "Kartoffeln", "quantity": "200", "unit": "g"}, {"name": "Karotten", "quantity": "2", "unit": "Stück"}, {"name": "Zucchetti", "quantity": "1", "unit": "Stück"}, {"name": "Wirz", "quantity": "200", "unit": "g"}, {"name": "Ditalini", "quantity": "100", "unit": "g"}, {"name": "Speck", "quantity": "100", "unit": "g"}, {"name": "Tomaten", "quantity": "400", "unit": "g"}, {"name": "Parmesan", "quantity": "50", "unit": "g"}], "instructions": "Bohnen über Nacht einweichen. Speck würfeln und anbraten. Gemüse rüsten und würfeln. Alles mit Wasser bedecken und ca. 1 Stunde köcheln. Pasta die letzten 10 Min mitkochen. Mit Parmesan servieren.", "time_minutes": 80, "servings": 4, "type": "veggie", "tags": ["swiss", "ticino", "classic", "soup"]},
    {"title": "Meitschibei", "description": "Berner Mandel-Guetzli.", "ingredients": [{"name": "Mandeln", "quantity": "300", "unit": "g"}, {"name": "Zucker", "quantity": "200", "unit": "g"}, {"name": "Eiweiss", "quantity": "2", "unit": "Stück"}, {"name": "Zitronensaft", "quantity": "1", "unit": "EL"}, {"name": "Kirsch", "quantity": "1", "unit": "EL"}], "instructions": "Mandeln mit kochendem Wasser überbrühen und schälen. Fein mahlen. Mit Zucker, Eiweiss, Zitronensaft und Kirsch zu einem Teig kneten. Zu länglichen Schenkeli formen, leicht gebogen auf ein Blech legen. Bei 160°C ca. 15 Min backen bis hellgelb.", "time_minutes": 40, "servings": 25, "type": "dessert", "tags": ["swiss", "bern", "classic", "baking"]},
    {"title": "Zürcher Lebkuchen", "description": "Traditioneller Zürcher Lebkuchen.", "ingredients": [{"name": "Honig", "quantity": "300", "unit": "g"}, {"name": "Zucker", "quantity": "150", "unit": "g"}, {"name": "Mandeln", "quantity": "100", "unit": "g"}, {"name": "Mehl", "quantity": "400", "unit": "g"}, {"name": "Lebkuchengewürz", "quantity": "2", "unit": "TL"}, {"name": "Natron", "quantity": "1", "unit": "TL"}, {"name": "Eier", "quantity": "2", "unit": "Stück"}], "instructions": "Honig und Zucker erwärmen. Abkühlen lassen, Eier und gehackte Mandeln einrühren. Mehl mit Gewürzen und Natron mischen und unterrühren. Teig über Nacht ruhen lassen. Ca. 1 cm dick ausrollen, Formen ausstechen. Bei 170°C ca. 20 Min backen.", "time_minutes": 50, "servings": 30, "type": "dessert", "tags": ["swiss", "zurich", "classic", "baking", "christmas"]},
    {"title": "Fleischkäse (Leberkäse)", "description": "Schweizer Fleischkäse aus dem Ofen.", "ingredients": [{"name": "Schweinefleisch", "quantity": "500", "unit": "g"}, {"name": "Rindfleisch", "quantity": "300", "unit": "g"}, {"name": "Speck", "quantity": "200", "unit": "g"}, {"name": "Eis", "quantity": "100", "unit": "ml"}, {"name": "Nitritpökelsalz", "quantity": "15", "unit": "g"}, {"name": "Pfeffer", "quantity": "1", "unit": "TL"}, {"name": "Muskatnuss", "quantity": "1", "unit": "Prise"}], "instructions": "Fleisch und Speck durch den Fleischwolf drehen (feinste Scheibe). Im Kutter mit Eis und Gewürzen zu einem feinen Brät verarbeiten. In eine Kastenform füllen. Bei 180°C ca. 60 Min backen bis die Oberfläche goldbraun ist.", "time_minutes": 90, "servings": 8, "type": "protein", "tags": ["swiss", "classic"]},
    {"title": "Waadtländer Flûte", "description": "Dünne Waadtländer Käse-Stangen.", "ingredients": [{"name": "Blätterteig", "quantity": "500", "unit": "g"}, {"name": "Gruyère", "quantity": "200", "unit": "g"}, {"name": "Ei", "quantity": "1", "unit": "Stück"}, {"name": "Kümmel", "quantity": "1", "unit": "TL"}], "instructions": "Blätterteig ausrollen. Geriebenen Käse darauf verteilen. Zusammenklappen und nochmals ausrollen. In ca. 1 cm breite Streifen schneiden. Streifen drehen und auf ein Blech legen. Mit Ei bestreichen, mit Kümmel bestreuen. Bei 200°C ca. 15 Min goldbraun backen.", "time_minutes": 30, "servings": 20, "type": "carb", "tags": ["swiss", "waadt", "classic", "apéro"]},
    {"title": "Luzerner Chügelipastete", "description": "Luzerner Pastetli mit Vol-au-vent und feinem Ragout.", "ingredients": [{"name": "Blätterteig-Pastetli", "quantity": "4", "unit": "Stück"}, {"name": "Kalbfleisch", "quantity": "200", "unit": "g"}, {"name": "Kalbsmilken", "quantity": "100", "unit": "g"}, {"name": "Champignons", "quantity": "150", "unit": "g"}, {"name": "Rahm", "quantity": "2", "unit": "dl"}, {"name": "Weisswein", "quantity": "1", "unit": "dl"}, {"name": "Butter", "quantity": "30", "unit": "g"}, {"name": "Mehl", "quantity": "1", "unit": "EL"}, {"name": "Fleischkügeli", "quantity": "12", "unit": "Stück"}], "instructions": "Kalbfleisch und Milken in Würfel schneiden. In Butter anbraten. Champignons beifügen. Mehl darüberstäuben, mit Wein ablöschen. Rahm beifügen, köcheln lassen. Fleischkügeli separat braten und untermengen. Pastetli erwärmen, Ragout einfüllen.", "time_minutes": 45, "servings": 4, "type": "protein", "tags": ["swiss", "luzern", "classic"]},
    {"title": "Griessbrei mit Zwetschgenkompott", "description": "Cremiger Griessbrei mit warmem Zwetschgenkompott.", "ingredients": [{"name": "Griess", "quantity": "80", "unit": "g"}, {"name": "Milch", "quantity": "5", "unit": "dl"}, {"name": "Zucker", "quantity": "3", "unit": "EL"}, {"name": "Vanillezucker", "quantity": "1", "unit": "Päckchen"}, {"name": "Zwetschgen", "quantity": "500", "unit": "g"}, {"name": "Zimt", "quantity": "1", "unit": "Stange"}], "instructions": "Milch mit Zucker und Vanillezucker aufkochen. Griess einrieseln lassen, unter Rühren 5 Min köcheln. Zwetschgen entsteinen, mit Zucker und Zimt weich kochen. Griessbrei mit warmem Kompott servieren.", "time_minutes": 25, "servings": 4, "type": "dessert", "tags": ["swiss", "classic", "vegetarian", "comfort"]},
    {"title": "Bauernbratwurst mit Zwiebelsauce", "description": "Grillierte Bratwurst mit Zwiebelsauce und Rösti.", "ingredients": [{"name": "Bauernbratwurst", "quantity": "4", "unit": "Stück"}, {"name": "Zwiebeln", "quantity": "4", "unit": "Stück"}, {"name": "Butter", "quantity": "40", "unit": "g"}, {"name": "Bouillon", "quantity": "2", "unit": "dl"}, {"name": "Rahm", "quantity": "1", "unit": "dl"}, {"name": "Mehl", "quantity": "1", "unit": "EL"}], "instructions": "Bratwürste im Ofen oder auf dem Grill garen. Zwiebeln in Halbringe schneiden, in Butter goldbraun dünsten. Mehl darüberstäuben, mit Bouillon ablöschen. Rahm beifügen, einkochen lassen. Bratwurst mit Zwiebelsauce und Rösti servieren.", "time_minutes": 30, "servings": 4, "type": "protein", "tags": ["swiss", "classic", "comfort"]},
    {"title": "Haferflocken-Wähe", "description": "Einfache Schweizer Wähe mit Haferflocken.", "ingredients": [{"name": "Kuchenteig", "quantity": "1", "unit": "Rolle"}, {"name": "Haferflocken", "quantity": "100", "unit": "g"}, {"name": "Milch", "quantity": "3", "unit": "dl"}, {"name": "Eier", "quantity": "3", "unit": "Stück"}, {"name": "Zucker", "quantity": "80", "unit": "g"}, {"name": "Zimt", "quantity": "1", "unit": "TL"}], "instructions": "Haferflocken in Milch einweichen. Eier mit Zucker verrühren. Hafermischung dazugeben. Teig in eine Wähenform legen. Füllung darauf verteilen. Bei 200°C ca. 35 Min backen. Mit Zimt bestäuben.", "time_minutes": 50, "servings": 8, "type": "dessert", "tags": ["swiss", "classic", "vegetarian", "baking"]},
    {"title": "Churer Fleischtorte", "description": "Bündner Fleischtorte mit Blätterteig.", "ingredients": [{"name": "Blätterteig", "quantity": "500", "unit": "g"}, {"name": "Schweinefleisch", "quantity": "400", "unit": "g"}, {"name": "Speck", "quantity": "100", "unit": "g"}, {"name": "Zwiebel", "quantity": "1", "unit": "Stück"}, {"name": "Eier", "quantity": "2", "unit": "Stück"}, {"name": "Rahm", "quantity": "1", "unit": "dl"}, {"name": "Pfeffer", "quantity": "1", "unit": "Prise"}, {"name": "Muskatnuss", "quantity": "1", "unit": "Prise"}], "instructions": "Fleisch und Speck fein hacken. Zwiebel fein schneiden und andünsten. Fleisch, Speck, Zwiebel, Eier, Rahm und Gewürze mischen. Blätterteig halbieren, eine Hälfte in die Form legen. Füllung verteilen, mit zweiter Hälfte bedecken. Bei 200°C ca. 40 Min backen.", "time_minutes": 55, "servings": 6, "type": "protein", "tags": ["swiss", "graubünden", "classic"]},
    {"title": "Safran-Risotto (Walliser Art)", "description": "Walliser Risotto mit Safran aus Mund.", "ingredients": [{"name": "Risotto-Reis", "quantity": "300", "unit": "g"}, {"name": "Safran", "quantity": "0.5", "unit": "g"}, {"name": "Zwiebel", "quantity": "1", "unit": "Stück"}, {"name": "Weisswein", "quantity": "1", "unit": "dl"}, {"name": "Bouillon", "quantity": "8", "unit": "dl"}, {"name": "Parmesan", "quantity": "80", "unit": "g"}, {"name": "Butter", "quantity": "30", "unit": "g"}], "instructions": "Safran in wenig warmem Wasser einweichen. Zwiebel in Butter andünsten. Reis beifügen, glasig rühren. Mit Wein ablöschen. Bouillon und Safranwasser kellenweise einrühren. Parmesan und Butter zum Schluss unterrühren.", "time_minutes": 35, "servings": 4, "type": "carb", "tags": ["swiss", "valais", "classic", "vegetarian"]},
    {"title": "Solothurner Lebkuchen", "description": "Weicher Solothurner Lebkuchen mit Haselnüssen.", "ingredients": [{"name": "Haselnüsse", "quantity": "200", "unit": "g"}, {"name": "Zucker", "quantity": "200", "unit": "g"}, {"name": "Eier", "quantity": "3", "unit": "Stück"}, {"name": "Zitronat", "quantity": "50", "unit": "g"}, {"name": "Orangeat", "quantity": "50", "unit": "g"}, {"name": "Zimt", "quantity": "1", "unit": "TL"}, {"name": "Nelkenpulver", "quantity": "0.5", "unit": "TL"}, {"name": "Oblaten", "quantity": "1", "unit": "Packung"}], "instructions": "Eier mit Zucker schaumig schlagen. Gemahlene Haselnüsse, fein gehacktes Zitronat und Orangeat sowie Gewürze unterheben. Masse auf Oblaten streichen. Bei 150°C ca. 20 Min backen. Sollen weich bleiben.", "time_minutes": 40, "servings": 20, "type": "dessert", "tags": ["swiss", "solothurn", "classic", "baking"]},
    {"title": "Landjäger", "description": "Schweizer Trockenwurst-Klassiker (vereinfacht).", "ingredients": [{"name": "Rindfleisch", "quantity": "600", "unit": "g"}, {"name": "Schweinefleisch", "quantity": "400", "unit": "g"}, {"name": "Speck", "quantity": "100", "unit": "g"}, {"name": "Nitritpökelsalz", "quantity": "20", "unit": "g"}, {"name": "Pfeffer", "quantity": "1", "unit": "TL"}, {"name": "Kümmel", "quantity": "0.5", "unit": "TL"}, {"name": "Knoblauch", "quantity": "2", "unit": "Zehen"}], "instructions": "Fleisch und Speck durch den Wolf drehen. Mit Gewürzen und Salz mischen. In Schweinedärme füllen, paarweise abbinden. Flach pressen. Kalt räuchern über mehrere Tage. An der Luft trocknen lassen.", "time_minutes": 60, "servings": 10, "type": "protein", "tags": ["swiss", "classic", "snack"]},
    {"title": "Saure Mocke", "description": "Geschmorter Rindsbraten im Essigsud.", "ingredients": [{"name": "Rindsbraten", "quantity": "800", "unit": "g"}, {"name": "Essig", "quantity": "2", "unit": "dl"}, {"name": "Rotwein", "quantity": "2", "unit": "dl"}, {"name": "Zwiebeln", "quantity": "2", "unit": "Stück"}, {"name": "Karotten", "quantity": "2", "unit": "Stück"}, {"name": "Lorbeerblatt", "quantity": "2", "unit": "Stück"}, {"name": "Nelken", "quantity": "3", "unit": "Stück"}, {"name": "Zucker", "quantity": "1", "unit": "EL"}], "instructions": "Fleisch in der Marinade aus Essig, Wein und Gewürzen 2 Tage einlegen. Fleisch trocken tupfen, scharf anbraten. Gemüse beifügen. Marinade angiessen. Zugedeckt ca. 2.5 Stunden im Ofen bei 160°C schmoren. Sauce passieren und abschmecken.", "time_minutes": 180, "servings": 4, "type": "protein", "tags": ["swiss", "classic", "winter"]},
]

# How many curated recipes exist
CURATED_COUNT = len(SWISS_CLASSICS)

# ---------------------------------------------------------------------------
# Type Classification Helpers
# ---------------------------------------------------------------------------
PROTEIN_KEYWORDS = {"fleisch", "poulet", "rind", "kalb", "schwein", "fisch", "lachs", "huhn", "chicken", "beef", "pork", "lamb", "fish", "salmon", "shrimp"}
VEGGIE_KEYWORDS = {"gemüse", "salat", "vegan", "vegetarisch", "vegetarian", "veggie", "tofu", "linsen", "bohnen"}
DESSERT_KEYWORDS = {"kuchen", "torte", "dessert", "süss", "schokolade", "cake", "sweet", "chocolate", "cookie", "pudding"}
CARB_KEYWORDS = {"pasta", "reis", "brot", "kartoffel", "nudel", "rice", "bread", "potato", "noodle", "risotto"}


def classify_recipe_type(title: str, ingredients_text: str) -> str:
    """Classify a recipe into one of: protein, veggie, carb, dessert."""
    combined = (title + " " + ingredients_text).lower()
    if any(kw in combined for kw in DESSERT_KEYWORDS):
        return "dessert"
    if any(kw in combined for kw in PROTEIN_KEYWORDS):
        return "protein"
    if any(kw in combined for kw in VEGGIE_KEYWORDS):
        return "veggie"
    if any(kw in combined for kw in CARB_KEYWORDS):
        return "carb"
    return "veggie"


# ---------------------------------------------------------------------------
# Source: RSS Feeds
# ---------------------------------------------------------------------------
async def collect_from_rss(
    max_recipes: int, language: str
) -> list[dict[str, Any]]:
    """Parse recipe RSS feeds and return structured recipe data."""
    recipes: list[dict[str, Any]] = []
    remaining = max_recipes

    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": "korb.guru-recipe-collector/0.1"},
        follow_redirects=True,
    ) as client:
        for feed_name, feed_url in RSS_FEEDS.items():
            if remaining <= 0:
                break

            logger.info("Fetching RSS feed: %s (%s)", feed_name, feed_url)
            try:
                resp = await client.get(feed_url)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("Failed to fetch %s: %s", feed_name, exc)
                continue

            feed = feedparser.parse(resp.text)
            for entry in feed.entries:
                if remaining <= 0:
                    break

                title = entry.get("title", "").strip()
                if not title:
                    continue

                description = entry.get("summary", entry.get("description", "")).strip()
                link = entry.get("link", "")

                # Build basic recipe structure from RSS entry
                recipe: dict[str, Any] = {
                    "title": title,
                    "description": description[:500] if description else "",
                    "ingredients": [],
                    "instructions": description[:1000] if description else "",
                    "time_minutes": None,
                    "servings": 4,
                    "type": classify_recipe_type(title, description),
                    "tags": [language],
                    "source": "rss",
                    "source_url": link,
                }

                # Add feed-specific tags
                if "chefkoch" in feed_name:
                    recipe["tags"].append("chefkoch")
                elif "allrecipes" in feed_name:
                    recipe["tags"].append("allrecipes")
                elif "srf" in feed_name:
                    recipe["tags"].extend(["srf", "swiss"])

                recipes.append(recipe)
                remaining -= 1

            # Rate limit: 1 request/second between feeds
            await asyncio.sleep(1.0)

    logger.info("RSS: collected %d recipes", len(recipes))
    return recipes


# ---------------------------------------------------------------------------
# Source: RecipeNLG (open dataset subset)
# ---------------------------------------------------------------------------
RECIPENLG_SAMPLE_URL = (
    "https://raw.githubusercontent.com/Glorf/recipenlg/main/dataset/dataset.csv"
)

# German/Swiss keywords for filtering RecipeNLG
GERMAN_KEYWORDS = {
    "schnitzel", "strudel", "knödel", "sauerkraut", "kartoffel", "bratwurst",
    "spätzle", "rösti", "fondue", "raclette", "müesli", "bircher", "zopf",
    "gulasch", "apfelstrudel", "zwiebelkuchen", "brezel", "pretzel",
    "black forest", "schwarzwälder", "sauerbraten", "lebkuchen",
}


async def collect_from_recipenlg(
    max_recipes: int, language: str
) -> list[dict[str, Any]]:
    """Download a small subset from RecipeNLG and filter for German/Swiss recipes.

    RecipeNLG is a large dataset (~2M recipes, CC-BY-NC-SA). We only fetch
    the first chunk and filter for relevance to keep the actor lightweight.
    """
    recipes: list[dict[str, Any]] = []

    async with httpx.AsyncClient(
        timeout=60.0,
        headers={"User-Agent": "korb.guru-recipe-collector/0.1"},
        follow_redirects=True,
    ) as client:
        logger.info("Fetching RecipeNLG sample data...")
        try:
            # Stream only first 2 MB to stay within reasonable limits
            async with client.stream("GET", RECIPENLG_SAMPLE_URL) as resp:
                resp.raise_for_status()
                raw_bytes = b""
                async for chunk in resp.aiter_bytes(chunk_size=8192):
                    raw_bytes += chunk
                    if len(raw_bytes) >= 2 * 1024 * 1024:
                        break
        except httpx.HTTPError as exc:
            logger.warning("Failed to fetch RecipeNLG: %s", exc)
            return recipes

    raw_text = raw_bytes.decode("utf-8", errors="replace")
    lines = raw_text.split("\n")

    # Skip header
    if lines and "title" in lines[0].lower():
        lines = lines[1:]

    for line in lines:
        if len(recipes) >= max_recipes:
            break

        parts = line.split('","')
        if len(parts) < 4:
            continue

        title = parts[0].strip('"').strip()
        ingredients_raw = parts[1].strip('"').strip()
        instructions_raw = parts[2].strip('"').strip()

        # Filter for German/Swiss relevance
        title_lower = title.lower()
        if language == "de" and not any(kw in title_lower for kw in GERMAN_KEYWORDS):
            continue

        # Parse ingredients (RecipeNLG uses JSON-like lists)
        ingredient_list: list[dict[str, str]] = []
        try:
            # RecipeNLG stores ingredients as Python-style list strings
            for ing in ingredients_raw.strip("[]").split('", "'):
                ing_clean = ing.strip('" ')
                if ing_clean:
                    ingredient_list.append({
                        "name": ing_clean,
                        "quantity": "",
                        "unit": "",
                    })
        except Exception:
            pass

        recipe: dict[str, Any] = {
            "title": title,
            "description": "",
            "ingredients": ingredient_list,
            "instructions": instructions_raw.replace('""', '"').strip("[]\"' "),
            "time_minutes": None,
            "servings": 4,
            "type": classify_recipe_type(title, ingredients_raw),
            "tags": [language, "recipenlg"],
            "source": "recipenlg",
            "source_url": "https://recipenlg.cs.put.poznan.pl/",
        }
        recipes.append(recipe)

    logger.info("RecipeNLG: collected %d recipes", len(recipes))
    return recipes


# ---------------------------------------------------------------------------
# Source: Curated Swiss Classics
# ---------------------------------------------------------------------------
def collect_curated(
    max_recipes: int, categories: list[str] | None = None
) -> list[dict[str, Any]]:
    """Return curated Swiss classic recipes as fallback source."""
    recipes: list[dict[str, Any]] = []
    for item in SWISS_CLASSICS:
        if len(recipes) >= max_recipes:
            break

        recipe = {**item, "source": "curated", "source_url": ""}

        # Filter by category if specified
        if categories and recipe.get("type") not in categories:
            continue

        recipes.append(recipe)

    logger.info("Curated: collected %d recipes", len(recipes))
    return recipes


# ---------------------------------------------------------------------------
# Main Actor Logic
# ---------------------------------------------------------------------------
async def main():
    async with Actor:
        actor_input = await Actor.get_input() or {}

        sources = actor_input.get("sources")
        if sources is None:
            sources = ["recipenlg", "rss"]
        if isinstance(sources, str):
            sources = [sources]

        max_recipes = max(1, actor_input.get("maxRecipes", 100))
        categories = actor_input.get("categories", [])
        language = actor_input.get("language", "de")

        logger.info(
            "Starting recipe collection: sources=%s, max=%d, lang=%s, categories=%s",
            sources, max_recipes, language, categories,
        )
        await Actor.set_status_message(
            f"Collecting recipes from {len(sources)} source(s)"
        )

        start_time = time.monotonic()
        all_recipes: list[dict[str, Any]] = []
        remaining = max_recipes

        # Collect from each source sequentially
        for source in sources:
            if remaining <= 0:
                break

            if source == "rss":
                recipes = await collect_from_rss(remaining, language)
                all_recipes.extend(recipes)
                remaining -= len(recipes)

            elif source == "recipenlg":
                recipes = await collect_from_recipenlg(remaining, language)
                all_recipes.extend(recipes)
                remaining -= len(recipes)

            else:
                logger.warning("Unknown source: %s — skipping", source)

        # Always include curated Swiss classics as fallback
        if remaining > 0:
            curated = collect_curated(remaining, categories or None)
            all_recipes.extend(curated)

        # Apply category filter to all recipes if specified
        if categories:
            all_recipes = [
                r for r in all_recipes if r.get("type") in categories
            ]

        # Trim to max
        all_recipes = all_recipes[:max_recipes]

        # Push all recipes to dataset
        total_pushed = 0
        for recipe in all_recipes:
            await Actor.push_data(recipe)
            total_pushed += 1

        total_elapsed = time.monotonic() - start_time

        # Store run summary
        kv_store = await Actor.open_key_value_store()
        run_summary = {
            "sources_requested": sources,
            "language": language,
            "categories_filter": categories,
            "total_recipes_pushed": total_pushed,
            "total_duration_s": round(total_elapsed, 1),
        }
        await kv_store.set_value("run-summary", run_summary)

        finished_msg = (
            f"Done: {total_pushed} recipes from "
            f"{', '.join(sources)} in {total_elapsed:.0f}s"
        )
        logger.info(finished_msg)
        await Actor.set_status_message(finished_msg)


if __name__ == "__main__":
    asyncio.run(main())
