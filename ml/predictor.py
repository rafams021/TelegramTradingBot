# ml/predictor.py
"""
ML Predictor

Usa modelo entrenado para predecir probabilidad de win en live trading.
"""
import joblib
import os
import logging
import pandas as pd
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class MLPredictor:
    """
    Predictor ML que carga modelo entrenado y predice probabilidad de win.

    Usage:
        predictor = MLPredictor('ml/models/reversal_model.pkl', threshold=0.65)
        should_enter, prob = predictor.predict(features)
        if should_enter:
            execute_trade()
    """

    def __init__(self, model_path: str, threshold: float = 0.60):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Modelo no encontrado: {model_path}")

        self.model = joblib.load(model_path)
        self.threshold = threshold
        self.model_path = model_path

        logger.info("=" * 70)
        logger.info("ML PREDICTOR INITIALIZED")
        logger.info("=" * 70)
        logger.info(f"Model: {model_path}")
        logger.info(f"Threshold: {threshold:.0%}")
        logger.info(f"Feature count: {len(self.model.feature_importances_)}")
        logger.info("=" * 70)

    def predict(self, features: Dict[str, float]) -> Tuple[bool, float]:
        """
        Predice si debe entrar en el trade basandose en features.

        Args:
            features: Dict con features extraidas (de feature_extractor)

        Returns:
            (should_enter, win_probability)
        """
        features_df = pd.DataFrame([features])

        try:
            probabilities = self.model.predict_proba(features_df)
            prob_win = float(probabilities[0][1])
        except Exception as e:
            logger.error(f"Error en prediccion: {e}")
            logger.error(f"Features recibidas: {list(features.keys())}")
            logger.error(f"Features esperadas: {self.model.feature_name_}")
            return False, 0.0

        should_enter = prob_win >= self.threshold

        if should_enter:
            logger.info(f"ML APPROVED - Win prob: {prob_win:.1%} >= {self.threshold:.0%}")
        else:
            logger.info(f"ML REJECTED - Win prob: {prob_win:.1%} < {self.threshold:.0%}")

        return should_enter, prob_win

    def get_feature_importance(self, top_n: int = 10) -> pd.DataFrame:
        if not hasattr(self.model, "feature_importances_"):
            logger.warning("Modelo no tiene feature_importances_")
            return pd.DataFrame()

        importance_df = pd.DataFrame({
            "feature": self.model.feature_name_,
            "importance": self.model.feature_importances_,
        }).sort_values("importance", ascending=False)

        return importance_df.head(top_n)

    def update_threshold(self, new_threshold: float):
        old_threshold = self.threshold
        self.threshold = new_threshold
        logger.info(f"Threshold updated: {old_threshold:.0%} -> {new_threshold:.0%}")


if __name__ == "__main__":
    print("ML Predictor")
    print("\nUsage:")
    print("  from ml.predictor import MLPredictor")
    print("  predictor = MLPredictor('ml/models/reversal_model.pkl', threshold=0.65)")
    print("  should_enter, prob = predictor.predict(features)")