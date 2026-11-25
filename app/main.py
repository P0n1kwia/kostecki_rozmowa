from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.staticfiles import StaticFiles

from . import reguly, storage
from .models import (
    Dostepnosc,
    Nieobecnosc,
    Pracownik,
    PracownikCreate,
    Przydzial,
    PrzydzialCreate,
    Zmiana,
)

app = FastAPI(title="Grafik zmian")
PRAC, NIEOB, PRZYD, PREF = "pracownicy", "nieobecnosci", "przydzialy", "preferencje"


# ---------- Pracownicy ----------
@app.get("/api/pracownicy", response_model=list[Pracownik])
def lista():
    return storage.load(PRAC)


@app.get("/api/pracownicy/{pid}", response_model=Pracownik)
def pobierz(pid: int):
    for r in storage.load(PRAC):
        if r["id"] == pid:
            return r
    raise HTTPException(404, "Nie znaleziono pracownika")


@app.post("/api/pracownicy", response_model=Pracownik, status_code=201)
def dodaj(dane: PracownikCreate):
    with storage.lock:  # cała sekwencja pod jedną blokadą -> brak dubli id
        rows = storage.load(PRAC)
        nowy = {"id": storage.next_id(rows), **dane.model_dump(mode="json")}
        rows.append(nowy)
        storage.save(PRAC, rows)
        return nowy


@app.put("/api/pracownicy/{pid}", response_model=Pracownik)
def zmien(pid: int, dane: PracownikCreate):
    with storage.lock:
        rows = storage.load(PRAC)
        for i, r in enumerate(rows):
            if r["id"] == pid:
                rows[i] = {"id": pid, **dane.model_dump(mode="json")}
                storage.save(PRAC, rows)
                return rows[i]
    raise HTTPException(404, "Nie znaleziono pracownika")


@app.delete("/api/pracownicy/{pid}", status_code=204)
def usun(pid: int):
    with storage.lock:
        rows = storage.load(PRAC)
        reszta = [r for r in rows if r["id"] != pid]
        if len(reszta) == len(rows):
            raise HTTPException(404, "Nie znaleziono pracownika")
        storage.save(PRAC, reszta)
        # kaskadowo: usuwamy też jego przydziały, żeby w grafiku nie zostały "duchy"
        storage.save(PRZYD, [p for p in storage.load(PRZYD) if p["pracownik_id"] != pid])
    return Response(status_code=204)


# ---------- Nieobecności (na razie tylko odczyt) ----------
@app.get("/api/nieobecnosci", response_model=list[Nieobecnosc])
def nieobecnosci():
    return storage.load(NIEOB)


# ---------- Przydziały do zmian ----------
@app.get("/api/przydzialy", response_model=list[Przydzial])
def przydzialy(
    rok: int = Query(ge=2000, le=2100),
    miesiac: int = Query(ge=1, le=12),  # walidacja parametrów URL, błędny -> 422
):
    prefiks = f"{rok}-{miesiac:02d}-"  # daty ISO zaczynają się od "RRRR-MM-"
    return [p for p in storage.load(PRZYD) if p["data"].startswith(prefiks)]


@app.post("/api/przydzialy", response_model=Przydzial, status_code=201)
def przypisz(dane: PrzydzialCreate):
    with storage.lock:  # sprawdzenie reguł i zapis muszą być jedną, nierozerwalną operacją
        prac = next((p for p in storage.load(PRAC) if p["id"] == dane.pracownik_id), None)
        if prac is None:
            raise HTTPException(404, "Nie znaleziono pracownika")
        rows = storage.load(PRZYD)
        powod = reguly.powod_odmowy(prac, dane.data, dane.zmiana.value, rows, storage.load(NIEOB))
        if powod:
            raise HTTPException(409, powod)  # 409 Conflict = żądanie koliduje ze stanem danych
        nowy = {"id": storage.next_id(rows), **dane.model_dump(mode="json")}
        rows.append(nowy)
        storage.save(PRZYD, rows)
        return nowy


@app.delete("/api/przydzialy/{przydzial_id}", status_code=204)
def odepnij(przydzial_id: int):
    with storage.lock:
        rows = storage.load(PRZYD)
        reszta = [p for p in rows if p["id"] != przydzial_id]
        if len(reszta) == len(rows):
            raise HTTPException(404, "Nie znaleziono przydziału")
        storage.save(PRZYD, reszta)
    return Response(status_code=204)


# ---------- Dostępność: kolory + liczniki godzin dla okna wyboru ----------
@app.get("/api/dostepnosc", response_model=list[Dostepnosc])
def dostepnosc(data: date, zmiana: Zmiana):
    with storage.lock:  # spójny odczyt wszystkich plików naraz
        pracownicy, przydzialy = storage.load(PRAC), storage.load(PRZYD)
        nieobecnosci, preferencje = storage.load(NIEOB), storage.load(PREF)
    wynik = []
    for p in pracownicy:
        o = reguly.ocen(p, data, zmiana.value, przydzialy, nieobecnosci, preferencje)
        wynik.append({
            "pracownik_id": p["id"],
            "kolor": o["kolor"],
            "powody": o["czerwone"] + o["zolte"],
            "godziny_tydzien": o["godziny_tydzien"],
            "limit_tydzien": o["limit_tydzien"],
            "godziny_miesiac": o["godziny_miesiac"],
            "limit_miesiac": o["limit_miesiac"],
        })
    return wynik


# Frontend montowany NA KOŃCU, bo mount("/") przechwytuje wszystkie ścieżki
app.mount(
    "/",
    StaticFiles(directory=Path(__file__).resolve().parent.parent / "static", html=True),
    name="static",
)
