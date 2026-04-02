"""Konfidenz-Flags und Unsicherheitsmodell für disaggregierte Datenpunkte.

Jeder disaggregierte Wert trägt ein Konfidenz-Flag das angibt wie zuverlässig
die Schätzung ist. Dies ist eine KRITISCHE Regel des Projekts.
"""

from dataclasses import dataclass
from typing import Literal

KonfidenzStufe = Literal["gemessen", "geschaetzt_hoch", "geschaetzt_mittel", "geschaetzt_niedrig"]

# Unsicherheits-Richtwerte pro Stufe (relative Unsicherheit 0–1)
UNSICHERHEIT_STUFEN: dict[KonfidenzStufe, float] = {
    "gemessen": 0.0,
    "geschaetzt_hoch": 0.15,
    "geschaetzt_mittel": 0.35,
    "geschaetzt_niedrig": 0.60,
}


@dataclass
class DisaggValue:
    """Ein disaggregierter Datenpunkt mit Konfidenz-Metadaten.

    Attributes:
        wert: Der geschätzte Wert.
        konfidenz: Zuverlässigkeits-Stufe der Schätzung.
        quelldatensatz: ID des Quelldatensatzes aus dem Katalog.
        quellwert_bezirk: Originalwert auf Bezirksebene.
        methode: Disaggregationsmethode (z.B. 'laenge_gewichtet').
        unsicherheit_relativ: Geschätzte relative Unsicherheit (0.0–1.0).
    """

    wert: float
    konfidenz: KonfidenzStufe
    quelldatensatz: str
    quellwert_bezirk: float
    methode: str
    unsicherheit_relativ: float

    def __post_init__(self) -> None:
        if self.unsicherheit_relativ < 0 or self.unsicherheit_relativ > 1:
            raise ValueError(
                f"unsicherheit_relativ muss zwischen 0 und 1 liegen, ist {self.unsicherheit_relativ}"
            )


def konfidenz_fuer_methode(methode: str, raeumliche_ebene: str) -> KonfidenzStufe:
    """Bestimmt die Konfidenz-Stufe basierend auf Methode und Quellebene.

    Args:
        methode: Disaggregationsmethode.
        raeumliche_ebene: Räumliche Ebene der Quelldaten.

    Returns:
        Passende Konfidenz-Stufe.
    """
    if raeumliche_ebene == "strassenabschnitt":
        return "gemessen"
    if methode in ("rate_direkt", "rate_bezirk"):
        # Raten (%) werden direkt übernommen, kein Fehler durch Disaggregation
        return "geschaetzt_hoch"
    if methode == "laenge_gewichtet" and raeumliche_ebene == "stadtbezirk":
        return "geschaetzt_mittel"
    if methode == "laenge_gewichtet" and raeumliche_ebene == "gesamtstadt":
        return "geschaetzt_niedrig"
    return "geschaetzt_niedrig"
