"""Reguły biznesowe grafiku - czyste funkcje, bez FastAPI (łatwo je testować)."""
from datetime import date, timedelta

NAZWY_ZMIAN = {"rano": "porannej", "wieczor": "wieczornej"}
NAZWY_TYPOW = {"urlop": "urlop", "niedostepny": "niedostępny"}
NAZWY_DNI = ["poniedziałki", "wtorki", "środy", "czwartki", "piątki", "soboty", "niedziele"]

# ZAŁOŻENIE: każda zmiana trwa 8 h. To jedyne miejsce do zmiany, gdy zmiany będą miały
# inną długość (np. wieczorna 12 h).
GODZINY_ZMIANY = {"rano": 8, "wieczor": 8}
# Normy dla pełnego etatu (1.0); dla innego etatu skalujemy proporcjonalnie (0.75 -> 30 h / 120 h).
GODZINY_TYDZIEN = 40
GODZINY_MIESIAC = 160


def _godziny(przydzialy: list[dict], pracownik_id: int, od: date, do: date) -> float:
    """Suma godzin pracownika na zmianach z zakresu dat [od, do] (obie krawędzie włącznie)."""
    return sum(
        GODZINY_ZMIANY[p["zmiana"]]
        for p in przydzialy
        if p["pracownik_id"] == pracownik_id and od <= date.fromisoformat(p["data"]) <= do
    )


def _g(liczba: float) -> str:
    return f"{liczba:g}"  # 30.0 -> "30", 7.5 -> "7.5"


def ocen(
    pracownik: dict,
    dzien: date,
    zmiana: str,
    przydzialy: list[dict],
    nieobecnosci: list[dict],
    preferencje: list[dict],
) -> dict:
    """Ocenia, czy pracownika można przypisać na daną zmianę danego dnia.

    czerwone = ograniczenia twarde (nie wolno przypisać),
    zolte    = preferencje pracownika (wolno, ale ostrzegamy).
    """
    pid = pracownik["id"]
    czerwone: list[str] = []
    zolte: list[str] = []

    # --- licznik godzin: tydzień pon-nd (ISO) i miesiąc kalendarzowy tego dnia ---
    poniedzialek = dzien - timedelta(days=dzien.weekday())
    pierwszy = dzien.replace(day=1)
    ostatni = (pierwszy + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    godz_tydzien = _godziny(przydzialy, pid, poniedzialek, poniedzialek + timedelta(days=6))
    godz_miesiac = _godziny(przydzialy, pid, pierwszy, ostatni)
    limit_tydzien = GODZINY_TYDZIEN * pracownik["etat"]
    limit_miesiac = GODZINY_MIESIAC * pracownik["etat"]

    # --- ograniczenia twarde (czerwone) ---
    for n in nieobecnosci:
        # łańcuch porównań: od <= dzień <= do (obie krawędzie włącznie)
        if n["pracownik_id"] == pid and (
            date.fromisoformat(n["od"]) <= dzien <= date.fromisoformat(n["do"])
        ):
            czerwone.append(f"nieobecny ({NAZWY_TYPOW.get(n['typ'], n['typ'])})")

    juz_tego_dnia = False
    for p in przydzialy:
        if p["pracownik_id"] == pid and p["data"] == dzien.isoformat():
            juz_tego_dnia = True
            if p["zmiana"] == zmiana:
                czerwone.append("już przypisany do tej zmiany")
            else:  # ta sama doba, druga zmiana -> reguła "rano i wieczór się wykluczają"
                czerwone.append(f"już na zmianie {NAZWY_ZMIAN[p['zmiana']]} tego dnia")

    if not juz_tego_dnia:  # przy dublu godziny i odpoczynek to już tylko szum
        wczoraj = (dzien - timedelta(days=1)).isoformat()
        jutro = (dzien + timedelta(days=1)).isoformat()
        for p in przydzialy:
            if p["pracownik_id"] != pid:
                continue
            # "nocka" = zmiana wieczorna: po niej nie wolno zaczynać rano następnego dnia
            if zmiana == "rano" and p["data"] == wczoraj and p["zmiana"] == "wieczor":
                czerwone.append("wczoraj wieczorem - brak odpoczynku przed zmianą poranną")
            if zmiana == "wieczor" and p["data"] == jutro and p["zmiana"] == "rano":
                czerwone.append("jutro rano - brak odpoczynku po zmianie wieczornej")

        h = GODZINY_ZMIANY[zmiana]
        if godz_tydzien + h > limit_tydzien:
            czerwone.append(f"limit tygodnia: byłoby {_g(godz_tydzien + h)}/{_g(limit_tydzien)} h")
        if godz_miesiac + h > limit_miesiac:
            czerwone.append(f"limit miesiąca: byłoby {_g(godz_miesiac + h)}/{_g(limit_miesiac)} h")

    # --- preferencje (żółte) ---
    dzien_tygodnia = dzien.isoweekday()  # 1 = poniedziałek ... 7 = niedziela
    for pref in preferencje:
        if pref["pracownik_id"] != pid:
            continue
        typ, wartosc = pref["typ"], pref.get("wartosc")
        if typ == "unikaj_weekendow" and dzien_tygodnia >= 6:
            zolte.append("woli nie w weekendy")
        elif typ == "tylko_dzienne" and zmiana == "wieczor":
            zolte.append("woli tylko dzienne zmiany")
        elif typ == "preferuje_nocne" and zmiana == "rano":
            zolte.append("woli zmiany nocne (wieczorne)")
        elif typ == "wolne_dnia" and wartosc == dzien.isoformat():
            zolte.append("chce wolne tego dnia")
        elif typ == "preferowane_dni_tygodnia" and dzien_tygodnia not in wartosc:
            zolte.append("woli " + " i ".join(NAZWY_DNI[d - 1] for d in wartosc))

    return {
        "kolor": "czerwony" if czerwone else "zolty" if zolte else "zielony",
        "czerwone": czerwone,
        "zolte": zolte,
        "godziny_tydzien": godz_tydzien,
        "limit_tydzien": limit_tydzien,
        "godziny_miesiac": godz_miesiac,
        "limit_miesiac": limit_miesiac,
    }


def powod_odmowy(
    pracownik: dict,
    dzien: date,
    zmiana: str,
    przydzialy: list[dict],
    nieobecnosci: list[dict],
) -> str | None:
    """Tekst odmowy (gdy są ograniczenia twarde) albo None, gdy przydział jest dozwolony.

    Preferencje (żółte) nie blokują - serwer odrzuca tylko to, co UI pokazuje na czerwono.
    """
    czerwone = ocen(pracownik, dzien, zmiana, przydzialy, nieobecnosci, [])["czerwone"]
    return ("Nie można przypisać: " + "; ".join(czerwone)) if czerwone else None
