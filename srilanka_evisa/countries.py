"""ISO 3166-1 alpha-3 codes with English / French names, used to match
nationality and country <select> options whatever the site's locale.
Extend as needed; unknown codes fall back to matching the code itself."""

COUNTRIES: dict[str, tuple[str, str]] = {
    "ARG": ("Argentina", "Argentine"),
    "AUS": ("Australia", "Australie"),
    "AUT": ("Austria", "Autriche"),
    "BEL": ("Belgium", "Belgique"),
    "BRA": ("Brazil", "Brésil"),
    "CAN": ("Canada", "Canada"),
    "CHE": ("Switzerland", "Suisse"),
    "CHN": ("China", "Chine"),
    "CZE": ("Czech Republic", "République tchèque"),
    "D": ("Germany", "Allemagne"),
    "DEU": ("Germany", "Allemagne"),
    "DNK": ("Denmark", "Danemark"),
    "ESP": ("Spain", "Espagne"),
    "FIN": ("Finland", "Finlande"),
    "FRA": ("France", "France"),
    "GBR": ("United Kingdom", "Royaume-Uni"),
    "GRC": ("Greece", "Grèce"),
    "HUN": ("Hungary", "Hongrie"),
    "IND": ("India", "Inde"),
    "IRL": ("Ireland", "Irlande"),
    "ISR": ("Israel", "Israël"),
    "ITA": ("Italy", "Italie"),
    "JPN": ("Japan", "Japon"),
    "KOR": ("Korea, Republic of", "Corée du Sud"),
    "LKA": ("Sri Lanka", "Sri Lanka"),
    "LUX": ("Luxembourg", "Luxembourg"),
    "MAR": ("Morocco", "Maroc"),
    "MEX": ("Mexico", "Mexique"),
    "NLD": ("Netherlands", "Pays-Bas"),
    "NOR": ("Norway", "Norvège"),
    "NZL": ("New Zealand", "Nouvelle-Zélande"),
    "POL": ("Poland", "Pologne"),
    "PRT": ("Portugal", "Portugal"),
    "ROU": ("Romania", "Roumanie"),
    "RUS": ("Russian Federation", "Russie"),
    "SGP": ("Singapore", "Singapour"),
    "SWE": ("Sweden", "Suède"),
    "THA": ("Thailand", "Thaïlande"),
    "TUR": ("Turkey", "Turquie"),
    "UKR": ("Ukraine", "Ukraine"),
    "USA": ("United States", "États-Unis"),
    "ZAF": ("South Africa", "Afrique du Sud"),
}


def country_candidates(code: str) -> list[str]:
    """Strings that may identify the country in a dropdown (code first)."""
    code = code.upper()
    names = COUNTRIES.get(code, ())
    return [code, *names]
