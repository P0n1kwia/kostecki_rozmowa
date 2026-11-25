from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Stanowisko(str, Enum):
    starszy = "starszy"
    pracownik = "pracownik"
    mlodszy = "młodszy"


class Zmiana(str, Enum):
    rano = "rano"
    wieczor = "wieczor"  # klucze bez polskich znaków, w JSON i URL-ach bezpieczniej


class PracownikBase(BaseModel):
    imie_nazwisko: str = Field(min_length=3, max_length=100)
    stanowisko: Stanowisko
    etat: float = Field(gt=0, le=1, description="Wymiar etatu: 0.5, 0.75, 1.0 ...")

    @field_validator("imie_nazwisko")
    @classmethod
    def _strip(cls, v: str) -> str:
        return " ".join(v.split())


class PracownikCreate(PracownikBase):
    pass


class Pracownik(PracownikBase):
    id: int


class Nieobecnosc(BaseModel):
    id: int
    pracownik_id: int
    od: date  # Pydantic sam zamienia "2026-12-21" na obiekt date (i waliduje, np. odrzuci 2026-02-30)
    do: date
    typ: str


class PrzydzialCreate(BaseModel):
    data: date
    zmiana: Zmiana
    pracownik_id: int


class Przydzial(PrzydzialCreate):
    id: int
