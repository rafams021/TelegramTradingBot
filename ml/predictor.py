"""
ML Predictor - Fase 2

Usa modelo entrenado para predecir probabilidad de win en live trading.
"""

import joblib
import pandas as pd
from typing import Dict, Tuple
import logging
import os

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
        """
        Args:
            model_path: Path al modelo .pkl entrenado
            threshold: Probabilidad mínima para aprobar trade (0.0-1.0)
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"❌ Modelo no encontrado: {model_path}")
        
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
        Predice si debe entrar en el trade basándose en features.
        
        Args:
            features: Dict con features extraídas (de feature_extractor)
        
        Returns:
            (should_enter, win_probability)
            - should_enter: True si prob >= threshold
            - win_probability: Probabilidad de ganar (0.0-1.0)
        
        Example:
            >>> features = {'rsi': 45.2, 'atr': 14.5, ...}
            >>> should_enter, prob = predictor.predict(features)
            >>> print(f"Should enter: {should_enter}, Prob: {prob:.1%}")
            Should enter: True, Prob: 67.3%
        """
        # Convertir dict a DataFrame (modelo espera DataFrame)
        features_df = pd.DataFrame([features])
        
        # Asegurar que features estén en el orden correcto
        # (LightGBM requiere mismo orden que training)
        try:
            # Predecir probabilidades
            probabilities = self.model.predict_proba(features_df)
            prob_win = float(probabilities[0][1])  # Probabilidad de clase 1 (win)
        
        except Exception as e:
            logger.error(f"❌ Error en predicción: {e}")
            logger.error(f"   Features recibidas: {list(features.keys())}")
            logger.error(f"   Features esperadas: {self.model.feature_name_}")
            return False, 0.0
        
        # Decisión
        should_enter = prob_win >= self.threshold
        
        # Log
        if should_enter:
            logger.info(f"✅ ML APPROVED - Win prob: {prob_win:.1%} >= {self.threshold:.0%}")
        else:
            logger.info(f"❌ ML REJECTED - Win prob: {prob_win:.1%} < {self.threshold:.0%}")
        
        return should_enter, prob_win
    
    def get_feature_importance(self, top_n: int = 10) -> pd.DataFrame:
        """
        Retorna las N features más importantes del modelo.
        
        Args:
            top_n: Número de features a retornar
        
        Returns:
            DataFrame con feature names e importances
        """
        if not hasattr(self.model, 'feature_importances_'):
            logger.warning("Modelo no tiene feature_importances_")
            return pd.DataFrame()
        
        importance_df = pd.DataFrame({
            'feature': self.model.feature_name_,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        return importance_df.head(top_n)
    
    def update_threshold(self, new_threshold: float):
        """
        Actualiza el threshold de decisión.
        
        Args:
            new_threshold: Nuevo threshold (0.0-1.0)
        """
        old_threshold = self.threshold
        self.threshold = new_threshold
        logger.info(f"🔄 Threshold updated: {old_threshold:.0%} → {new_threshold:.0%}")


if __name__ == "__main__":
    print("ML Predictor - Fase 2")
    print("\nUsage:")
    print("  from ml.predictor import MLPredictor")
    print("  predictor = MLPredictor('ml/models/reversal_model.pkl', threshold=0.65)")
    print("  should_enter, prob = predictor.predict(features)")