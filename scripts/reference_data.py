"""Reference data used by the demo seed.

Prices per m2 are rounded orders of magnitude of apartment sale prices observed in the
French open data DVF ("Demandes de valeurs foncières", data.gouv.fr) for 2024. They only
calibrate the synthetic generator so that the analytics look realistic; they are not
official statistics.
"""

# (name, postal code, department, latitude, longitude, apartment price per m2 in EUR)
CITIES: list[tuple[str, str, str, float, float, int]] = [
    # Aix-en-Provence (headquarters) and its area
    ("Aix-en-Provence", "13100", "13", 43.5297, 5.4474, 5000),
    ("Gardanne", "13120", "13", 43.4549, 5.4691, 3300),
    ("Pertuis", "84120", "84", 43.6942, 5.5016, 3100),
    ("Salon-de-Provence", "13300", "13", 43.6403, 5.0973, 2900),
    # Marseille
    ("Marseille", "13008", "13", 43.2422, 5.3755, 4600),
    ("Marseille", "13001", "13", 43.2999, 5.3841, 2600),
    ("Aubagne", "13400", "13", 43.2927, 5.5708, 3400),
    ("La Ciotat", "13600", "13", 43.1748, 5.6046, 4600),
    # Nice
    ("Nice", "06000", "06", 43.7034, 7.2663, 5300),
    ("Antibes", "06600", "06", 43.5808, 7.1251, 5600),
    ("Cannes", "06400", "06", 43.5528, 7.0174, 6200),
    # Lyon
    ("Lyon", "69003", "69", 45.7597, 4.8422, 5000),
    ("Lyon", "69006", "69", 45.7699, 4.8521, 6500),
    ("Villeurbanne", "69100", "69", 45.7719, 4.8902, 4100),
    # Paris and inner suburbs
    ("Paris", "75011", "75", 48.8590, 2.3800, 10200),
    ("Paris", "75016", "75", 48.8637, 2.2769, 11500),
    ("Boulogne-Billancourt", "92100", "92", 48.8397, 2.2399, 8300),
    ("Montreuil", "93100", "93", 48.8611, 2.4437, 6200),
    # Bordeaux
    ("Bordeaux", "33000", "33", 44.8378, -0.5792, 4700),
    ("Mérignac", "33700", "33", 44.8386, -0.6436, 3900),
    ("Pessac", "33600", "33", 44.8067, -0.6311, 3700),
    # Toulouse
    ("Toulouse", "31000", "31", 43.6047, 1.4442, 3900),
    ("Blagnac", "31700", "31", 43.6370, 1.3907, 3300),
    ("Colomiers", "31770", "31", 43.6116, 1.3350, 2900),
    # Montpellier
    ("Montpellier", "34000", "34", 43.6108, 3.8767, 3900),
    ("Castelnau-le-Lez", "34170", "34", 43.6336, 3.9017, 4200),
    # Nantes
    ("Nantes", "44000", "44", 47.2184, -1.5536, 3900),
    ("Saint-Herblain", "44800", "44", 47.2122, -1.6497, 3200),
    ("Rezé", "44400", "44", 47.1833, -1.5500, 3400),
    # Lille
    ("Lille", "59000", "59", 50.6292, 3.0573, 3600),
    ("Roubaix", "59100", "59", 50.6942, 3.1746, 1800),
    ("Villeneuve-d'Ascq", "59650", "59", 50.6233, 3.1450, 2900),
    # Strasbourg
    ("Strasbourg", "67000", "67", 48.5734, 7.7521, 3700),
    ("Schiltigheim", "67300", "67", 48.6070, 7.7490, 3000),
    # Rennes
    ("Rennes", "35000", "35", 48.1173, -1.6778, 4100),
    ("Cesson-Sévigné", "35510", "35", 48.1214, -1.6031, 4000),
    # Grenoble
    ("Grenoble", "38000", "38", 45.1885, 5.7245, 2500),
    ("Meylan", "38240", "38", 45.2096, 5.7782, 3300),
    ("Échirolles", "38130", "38", 45.1436, 5.7183, 1900),
]

# (code, name, city name, postal code, address, is headquarters)
AGENCIES: list[tuple[str, str, str, str, str, bool]] = [
    ("AIX", "Ymmo Aix-en-Provence (siège)", "Aix-en-Provence", "13100", "12 cours Mirabeau", True),
    ("MRS", "Ymmo Marseille Prado", "Marseille", "13008", "250 avenue du Prado", False),
    ("NCE", "Ymmo Nice", "Nice", "06000", "18 avenue Jean Médecin", False),
    ("LYS", "Ymmo Lyon Part-Dieu", "Lyon", "69003", "40 rue de la Villette", False),
    ("PAR", "Ymmo Paris Bastille", "Paris", "75011", "21 rue de la Roquette", False),
    ("BOD", "Ymmo Bordeaux", "Bordeaux", "33000", "5 cours de l'Intendance", False),
    ("TLS", "Ymmo Toulouse Capitole", "Toulouse", "31000", "8 rue d'Alsace-Lorraine", False),
    ("MPL", "Ymmo Montpellier", "Montpellier", "34000", "3 place de la Comédie", False),
    ("NTE", "Ymmo Nantes", "Nantes", "44000", "14 rue Crébillon", False),
    ("LIL", "Ymmo Lille", "Lille", "59000", "30 rue Faidherbe", False),
    ("SXB", "Ymmo Strasbourg", "Strasbourg", "67000", "9 rue des Grandes Arcades", False),
    ("RNS", "Ymmo Rennes", "Rennes", "35000", "6 quai Lamartine", False),
    ("GNB", "Ymmo Grenoble", "Grenoble", "38000", "11 place Grenette", False),
]

FIRST_NAMES = [
    "Camille",
    "Léa",
    "Manon",
    "Chloé",
    "Inès",
    "Sarah",
    "Julie",
    "Emma",
    "Lucie",
    "Clara",
    "Lucas",
    "Hugo",
    "Louis",
    "Nathan",
    "Gabriel",
    "Arthur",
    "Jules",
    "Thomas",
    "Léo",
    "Adam",
    "Yasmine",
    "Karim",
    "Mehdi",
    "Nora",
    "Sofiane",
    "Amina",
    "Antoine",
    "Pauline",
    "Maxime",
    "Élodie",
    "Romain",
    "Anaïs",
    "Quentin",
    "Marine",
    "Julien",
    "Laura",
    "Nicolas",
    "Océane",
]
LAST_NAMES = [
    "Martin",
    "Bernard",
    "Dubois",
    "Thomas",
    "Robert",
    "Richard",
    "Petit",
    "Durand",
    "Leroy",
    "Moreau",
    "Simon",
    "Laurent",
    "Lefebvre",
    "Michel",
    "Garcia",
    "David",
    "Bertrand",
    "Roux",
    "Vincent",
    "Fournier",
    "Morel",
    "Girard",
    "André",
    "Mercier",
    "Dupont",
    "Lambert",
    "Bonnet",
    "François",
    "Martinez",
    "Benali",
    "Nguyen",
    "Haddad",
    "Rossi",
    "Lopez",
    "Fontaine",
    "Chevalier",
]
STREETS = [
    "rue de la République",
    "avenue Victor Hugo",
    "boulevard Gambetta",
    "rue Pasteur",
    "rue Jean Jaurès",
    "avenue de la Libération",
    "rue du Général de Gaulle",
    "place de la Mairie",
    "rue des Lilas",
    "chemin des Oliviers",
    "allée des Platanes",
    "rue Voltaire",
    "rue Émile Zola",
    "avenue Foch",
    "rue de la Gare",
    "quai des Docks",
    "rue du Commerce",
    "impasse des Vignes",
]
