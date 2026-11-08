"""Per-document options and compatibility with forms opened before the update."""

PRINT_OPTIONS = (
    "type_travail",
    "date_souhaitee",
    "exemplaires",
    "mode",
    "format_papier",
    "feuilles_reponse",
    "papier_brouillon",
)


def print_summary(documents):
    def value(document, key):
        return document[key] if isinstance(document, dict) else getattr(document, key)

    types = {value(document, "type_travail") for document in documents}
    return {
        "type_travail": next(iter(types)) if len(types) == 1 else "mixte",
        "feuilles_reponse": sum(value(d, "feuilles_reponse") for d in documents),
        "papier_brouillon": sum(value(d, "papier_brouillon") for d in documents),
    }


def legacy_print_data(data):
    """Copy old batch options once; never override a new document's own options."""
    if data is None:
        return None
    data = data.copy()
    try:
        count = min(max(int(data.get("documents-TOTAL_FORMS", "0")), 0), 12)
    except (TypeError, ValueError):
        return data
    if "type_travail" not in data or any(
        f"documents-{i}-type_travail" in data for i in range(count)
    ):
        return data
    active = []
    for index in range(count):
        prefix = f"documents-{index}-"
        data[prefix + "type_travail"] = data["type_travail"]
        deleted = str(data.get(prefix + "DELETE", "")).lower()
        if deleted and deleted != "false":
            continue
        active.append(index)
    if active:
        first = min(
            active,
            key=lambda i: (data.get(f"documents-{i}-date_souhaitee", "9999-12-31"), i),
        )
        for key in (
            "avec_feuilles_reponse",
            "feuilles_reponse",
            "avec_papier_brouillon",
            "papier_brouillon",
        ):
            if key in data:
                data[f"documents-{first}-" + key] = data[key]
    return data
