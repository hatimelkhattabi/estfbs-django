from datetime import timedelta

GRADES = ("PA", "PH", "PES")
DEPARTEMENTS = (
    "Math - Informatiques",
    "Génie Civil & Mines",
    "Biotechnologie Agroalimentaire",
)
DUREES = (
    "Demi-journée (Matin : 08h00 - 13h00)",
    "Demi-journée (Après-midi : 13h30 - 18h30)",
    "Une journée complète (08h00 - 18h00)",
    "2 jours consécutifs",
    "3 jours ou plus (mission spéciale)",
)


def professor_name(value):
    value = (value or "").strip()
    return value if value.lower().startswith(("pr.", "pr ", "prof")) else "Pr. " + value


def return_date(depart, duration):
    duration = (duration or "").casefold()
    return depart + timedelta(
        days=2 if "3 jour" in duration else (1 if "2 jour" in duration else 0)
    )


def suggested_vehicle(effectif):
    if effectif <= 6:
        return "Véhicule de liaison / service (5 places)"
    if effectif <= 25:
        return "Minibus Universitaire (25 places)"
    if effectif <= 50:
        return "Grand Bus Universitaire (50 places)"
    return "Autocar de location conventionné"
