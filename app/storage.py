"""Prosty magazyn danych w plikach JSON (zapis atomowy, blokada wątków)."""
import json
import os
import tempfile
from pathlib import Path
from threading import RLock

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Blokada jest publiczna: endpointy obejmują nią całą sekwencję
# "wczytaj -> zmień -> zapisz". RLock (wielobieżny) pozwala wątkowi, który już
# trzyma blokadę, wejść w load()/save(), które też ją biorą - bez zakleszczenia.
lock = RLock()


def load(name: str) -> list[dict]:
    path = DATA_DIR / f"{name}.json"
    with lock:
        if not path.exists():  # np. przydzialy.json przed pierwszym zapisem
            return []
        return json.loads(path.read_text(encoding="utf-8"))


def save(name: str, rows: list[dict]) -> None:
    path = DATA_DIR / f"{name}.json"
    with lock:
        # zapis do pliku tymczasowego + podmiana = plik nigdy nie jest "w połowie"
        fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


def next_id(rows: list[dict]) -> int:
    return max((r["id"] for r in rows), default=0) + 1
