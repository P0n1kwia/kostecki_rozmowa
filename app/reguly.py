"""Reguły biznesowe grafiku - czyste funkcje, bez FastAPI (łatwo je testować)."""
from datetime import date

NAZWY_ZMIAN = {"rano": "porannej", "wieczor": "wieczornej"}
NAZWY_TYPOW = {"urlop": "urlop", "niedostepny": "niedostępny"}


def powod_odmowy(
    pracownik_id: int,
    dzien: date,
    zmiana: str,
    przydzialy: list[dict],
    nieobecnosci: list[dict],
) -> str | None:
    """Zwraca tekst powodu odmowy albo None, gdy przydział jest dozwolony."""
    for n in nieobecnosci:
        # łańcuch porównań: od <= dzień <= do (obie krawędzie włącznie)
        if n["pracownik_id"] == pracownik_id and (
            date.fromisoformat(n["od"]) <= dzien <= date.fromisoformat(n["do"])
        ):
            return f"Pracownik jest nieobecny ({NAZWY_TYPOW.get(n['typ'], n['typ'])})"

    for p in przydzialy:
        if p["pracownik_id"] == pracownik_id and p["data"] == dzien.isoformat():
            if p["zmiana"] == zmiana:
                return "Pracownik jest już przypisany do tej zmiany"
            # ta sama doba, druga zmiana -> reguła "rano i wieczór się wykluczają"
            return f"Pracownik jest już przypisany do zmiany {NAZWY_ZMIAN[p['zmiana']]} tego dnia"
    return None
