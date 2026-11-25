"use strict";

const DNI = ["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"];
const MIESIACE = ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec",
  "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień"];
const ETYKIETY_ZMIAN = { rano: "poranna", wieczor: "wieczorna" };

const teraz = new Date();
const stan = {
  rok: teraz.getFullYear(),
  miesiac: teraz.getMonth(), // 0-11, jak w JS
  zmiana: "rano",
  pracownicy: [],
  przydzialy: [], // tylko wyświetlany miesiąc
};

const $ = (id) => document.getElementById(id);
const dwie = (n) => String(n).padStart(2, "0");
// Data ISO budowana RĘCZNIE z lokalnych składników. toISOString() liczy w UTC,
// więc w Polsce (UTC+1/+2) północ lokalna potrafi "cofnąć się" o dzień.
const iso = (rok, mies0, dzien) => `${rok}-${dwie(mies0 + 1)}-${dwie(dzien)}`;

// Mała funkcja do budowania elementów DOM. Tekst trafia przez append(), czyli jako
// tekst, a nie HTML - dzięki temu imię z "<script>" nic nie wykona (brak XSS).
function el(tag, atrybuty = {}, dzieci = []) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(atrybuty)) {
    if (v === false || v == null) continue; // disabled: false NIE może ustawić atrybutu
    if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  e.append(...[].concat(dzieci));
  return e;
}

async function api(url, opcje) {
  const odp = await fetch(url, opcje);
  if (!odp.ok) {
    let tekst = `Błąd ${odp.status}`;
    try {
      const b = await odp.json();
      if (typeof b.detail === "string") tekst = b.detail; // nasze komunikaty 404/409
    } catch { /* odpowiedź bez JSON-a */ }
    throw new Error(tekst);
  }
  return odp.status === 204 ? null : odp.json();
}

function pokazBlad(tekst) {
  $("komunikat").textContent = tekst;
  $("wybor-blad").textContent = tekst;
}

const pracownik = (id) => stan.pracownicy.find((p) => p.id === id);

// "Anna Kowalska" -> "Anna K." (pełne imię i nazwisko jest w podpowiedzi title)
function skrot(imieNazwisko) {
  const [imie, ...reszta] = imieNazwisko.split(" ");
  const nazwisko = reszta.at(-1);
  return nazwisko ? `${imie} ${nazwisko[0]}.` : imie;
}

// ---------- Rysowanie ----------
function render() {
  document.body.dataset.tryb = stan.zmiana; // CSS reaguje na ten atrybut
  $("tytul").textContent = `${MIESIACE[stan.miesiac]} ${stan.rok}`;
  for (const b of document.querySelectorAll(".tryby button")) {
    b.classList.toggle("aktywny", b.dataset.zmiana === stan.zmiana);
  }

  const siatka = $("siatka");
  siatka.replaceChildren();
  for (const d of DNI) siatka.append(el("div", { class: "naglowek" }, d));

  // getDay(): 0 = niedziela, a my zaczynamy tydzień od poniedziałku -> (x + 6) % 7
  const przesuniecie = (new Date(stan.rok, stan.miesiac, 1).getDay() + 6) % 7;
  // dzień "0" następnego miesiąca = ostatni dzień bieżącego
  const dniWMiesiacu = new Date(stan.rok, stan.miesiac + 1, 0).getDate();
  const tygodnie = Math.ceil((przesuniecie + dniWMiesiacu) / 7); // tyle wierszy, ile tygodni dotyka miesiąc

  for (let i = 0; i < tygodnie * 7; i++) {
    // Date sam "przelewa" dni spoza zakresu: dzień 0 = ostatni dzień poprzedniego miesiąca, 32 = początek następnego
    siatka.append(komorka(new Date(stan.rok, stan.miesiac, 1 - przesuniecie + i)));
  }
}

function komorka(d) {
  const swoj = d.getMonth() === stan.miesiac;
  const dzien = iso(d.getFullYear(), d.getMonth(), d.getDate());
  const dzisiaj = iso(teraz.getFullYear(), teraz.getMonth(), teraz.getDate());
  const weekend = d.getDay() === 0 || d.getDay() === 6;

  const kom = el("div", {
    class: ["dzien", swoj ? "" : "obcy", weekend ? "weekend" : "", dzien === dzisiaj ? "dzis" : ""].join(" ").trim(),
  }, el("span", { class: "numer" }, String(d.getDate())));
  if (!swoj) return kom; // dni z sąsiednich miesięcy tylko dopełniają siatkę

  const kafle = el("div", { class: "kafle" });
  // Widok pokazuje tylko wybraną zmianę: przy "Wieczór" znikają poranni i odwrotnie.
  const dzisiejsze = stan.przydzialy
    .filter((p) => p.data === dzien && p.zmiana === stan.zmiana)
    .sort((a, b) => a.pracownik_id - b.pracownik_id);
  for (const p of dzisiejsze) {
    const prac = pracownik(p.pracownik_id);
    // Klasa "rano"/"wieczor" pochodzi z samego przydziału (wartość z enuma po stronie serwera),
    // więc kolor kafelka zależy od JEGO zmiany, a nie od aktualnie wybranego przełącznika.
    kafle.append(el("div", {
      class: `kafel ${p.zmiana}`,
      title: `${prac ? prac.imie_nazwisko : "?"} - zmiana ${ETYKIETY_ZMIAN[p.zmiana]}`,
    }, [
      el("span", {}, prac ? skrot(prac.imie_nazwisko) : "?"),
      el("button", { class: "usun", "aria-label": "Zdejmij ze zmiany", onclick: () => odepnij(p) }, "×"),
    ]));
  }
  // Przycisk dodaje na zmianę wybraną w przełączniku - podpis mówi, na którą.
  kom.append(kafle, el("button", {
    class: "dodaj",
    "aria-label": `Dodaj pracownika na zmianę ${ETYKIETY_ZMIAN[stan.zmiana]}`,
    onclick: () => otworzWybor(dzien),
  }, `+ ${stan.zmiana === "rano" ? "rano" : "wieczór"}`));
  return kom;
}

// ---------- Okno wyboru pracownika ----------
let numerZapytania = 0; // spóźniona odpowiedź dla poprzedniego otwarcia okna nie może nadpisać listy

async function otworzWybor(dzien) {
  const [r, m, dd] = dzien.split("-");
  $("wybor-tytul").textContent = `${Number(dd)}.${m}.${r} - zmiana ${ETYKIETY_ZMIAN[stan.zmiana]}`;
  pokazBlad("");
  const lista = $("wybor-lista");
  lista.replaceChildren(el("li", { class: "ladowanie" }, "Ładowanie..."));
  $("wybor").showModal(); // natywny <dialog>: ciemne tło, Esc i focus trap za darmo

  // Kolory i liczniki godzin liczy serwer (jedno źródło reguł; to samo sprawdza przy zapisie).
  const moj = ++numerZapytania;
  let oceny;
  try {
    oceny = await api(`/api/dostepnosc?data=${dzien}&zmiana=${stan.zmiana}`);
  } catch (e) {
    if (moj === numerZapytania) { lista.replaceChildren(); pokazBlad(e.message); }
    return;
  }
  if (moj !== numerZapytania) return;

  lista.replaceChildren();
  for (const o of oceny) {
    const p = pracownik(o.pracownik_id);
    if (!p) continue;
    lista.append(el("li", {}, el("button", {
      class: `osoba ${o.kolor}`,
      disabled: o.kolor === "czerwony", // ograniczenie twarde - serwer i tak odpowiedziałby 409
      onclick: () => przypisz(dzien, p.id),
    }, [
      el("span", { class: "osoba-gora" }, [
        el("span", {}, p.imie_nazwisko),
        el("small", {}, `tydz. ${o.godziny_tydzien}/${o.limit_tydzien} h · mies. ${o.godziny_miesiac}/${o.limit_miesiac} h`),
      ]),
      el("small", { class: "powody" }, o.powody.length ? o.powody.join(" · ") : `${p.stanowisko}, etat ${p.etat}`),
    ])));
  }
}

// ---------- Komunikacja z API ----------
async function wczytajPrzydzialy() {
  const [rok, mies] = [stan.rok, stan.miesiac];
  const dane = await api(`/api/przydzialy?rok=${rok}&miesiac=${mies + 1}`);
  // Przy szybkim klikaniu strzałek wolniejsza, starsza odpowiedź nie może nadpisać nowszej
  if (rok === stan.rok && mies === stan.miesiac) stan.przydzialy = dane;
}

async function przypisz(dzien, pid) {
  try {
    await api("/api/przydzialy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: dzien, zmiana: stan.zmiana, pracownik_id: pid }),
    });
    await wczytajPrzydzialy();
    $("wybor").close();
    pokazBlad("");
    render();
  } catch (e) {
    pokazBlad(e.message); // np. 409 od serwera, gdy ktoś inny zdążył przypisać tę osobę
  }
}

async function odepnij(przydzial) {
  try {
    await api(`/api/przydzialy/${przydzial.id}`, { method: "DELETE" });
    await wczytajPrzydzialy();
    pokazBlad("");
    render();
  } catch (e) {
    pokazBlad(e.message);
  }
}

async function zmienMiesiac(delta) {
  const d = new Date(stan.rok, stan.miesiac + delta, 1); // Date sam zawija rok (styczeń - 1 = grudzień)
  stan.rok = d.getFullYear();
  stan.miesiac = d.getMonth();
  try { await wczytajPrzydzialy(); } catch (e) { pokazBlad(e.message); }
  render();
}

// ---------- Start ----------
$("poprzedni").addEventListener("click", () => zmienMiesiac(-1));
$("nastepny").addEventListener("click", () => zmienMiesiac(1));
$("wybor-zamknij").addEventListener("click", () => $("wybor").close());
for (const b of document.querySelectorAll(".tryby button")) {
  b.addEventListener("click", () => { stan.zmiana = b.dataset.zmiana; render(); });
}

(async () => {
  try {
    stan.pracownicy = await api("/api/pracownicy");
    await wczytajPrzydzialy();
  } catch (e) {
    pokazBlad(e.message);
  }
  render();
})();
