"""Données d'observation.

TODO P2 : charger data/processed/monthly.parquet (region_id, indicator, date, value) et
data/processed/static.json en mémoire au démarrage. D'ici là : valeurs mock (aléatoires).
"""
import random


def mock_value(indicator: str, month: int) -> float:
    rainy = 1 if 4 <= month <= 10 else 0
    return {"precipitation": 20 + rainy * 140, "ndvi": 0.35 + rainy * 0.3,
            "lst_day": 38 - rainy * 6, "elevation": 300}[indicator] * random.uniform(0.8, 1.2)
