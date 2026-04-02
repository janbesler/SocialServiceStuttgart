"""Konsistenzprüfungen für disaggregierte Daten.

Hauptregel: Summe aller Straßenabschnitte eines Bezirks ≈ Bezirkswert.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

TOLERANZ_RELATIV = 0.001  # 0.1% Rundungstoleranz


def validate_sum_constraint(
    disagg_df: pd.DataFrame,
    bezirk_df: pd.DataFrame,
    wert_spalten: list[str],
    bezirk_spalte: str,
    dataset_id: str,
) -> bool:
    """Prüft ob Summen der Segmente mit Bezirkswerten übereinstimmen.

    Nur anwendbar für Count-Indikatoren (modus='count').

    Args:
        disagg_df: Disaggregierter DataFrame mit 'bezirk' und wert_spalten.
        bezirk_df: Original-Bezirks-DataFrame.
        wert_spalten: Zu prüfende Wertspalten.
        bezirk_spalte: Bezirksspalte im bezirk_df.
        dataset_id: Datensatz-ID für Log-Ausgaben.

    Returns:
        True wenn alle Prüfungen bestehen, False bei Abweichungen.
    """
    from .dasymetric import normalize_bezirk_name

    bezirk_df = bezirk_df.copy()
    bezirk_df[bezirk_spalte] = bezirk_df[bezirk_spalte].apply(normalize_bezirk_name)

    alle_ok = True
    for col in wert_spalten:
        if col not in disagg_df.columns or col not in bezirk_df.columns:
            continue

        # Segmentsummen pro Bezirk
        segment_summen = (
            disagg_df.groupby("bezirk")[col]
            .sum()
            .rename("segment_summe")
        )

        # Bezirkswerte
        bezirk_werte = (
            bezirk_df.groupby(bezirk_spalte)[col]
            .sum()
            .rename("bezirk_wert")
        )

        vergleich = pd.concat([segment_summen, bezirk_werte], axis=1, join="inner")
        if vergleich.empty:
            continue

        # Relative Abweichung
        vergleich["abweichung"] = (
            (vergleich["segment_summe"] - vergleich["bezirk_wert"]).abs()
            / vergleich["bezirk_wert"].replace(0, float("nan"))
        ).fillna(0)

        max_abw = vergleich["abweichung"].max()
        if max_abw > TOLERANZ_RELATIV:
            schlimmster = vergleich["abweichung"].idxmax()
            logger.warning(
                "%s | %s: Summen-Abweichung %.4f%% in Bezirk '%s' "
                "(Segment-Summe=%.2f, Bezirk=%.2f)",
                dataset_id, col, max_abw * 100, schlimmster,
                vergleich.loc[schlimmster, "segment_summe"],
                vergleich.loc[schlimmster, "bezirk_wert"],
            )
            alle_ok = False
        else:
            logger.debug("%s | %s: Summen-Validierung OK (max Abw. %.4f%%)", dataset_id, col, max_abw * 100)

    return alle_ok


def validate_no_negatives(
    disagg_df: pd.DataFrame,
    wert_spalten: list[str],
    dataset_id: str,
) -> bool:
    """Prüft ob keine negativen Werte in physikalisch nicht-negativen Spalten.

    Args:
        disagg_df: Disaggregierter DataFrame.
        wert_spalten: Zu prüfende Spalten.
        dataset_id: Datensatz-ID für Log-Ausgaben.

    Returns:
        True wenn keine negativen Werte gefunden.
    """
    alle_ok = True
    for col in wert_spalten:
        if col not in disagg_df.columns:
            continue
        neg = (disagg_df[col] < 0).sum()
        if neg > 0:
            logger.warning(
                "%s | %s: %d negative Werte gefunden (sollten nicht vorkommen)",
                dataset_id, col, neg,
            )
            alle_ok = False
    return alle_ok
