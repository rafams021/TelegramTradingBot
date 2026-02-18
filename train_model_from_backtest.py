"""
TRAIN MODEL - Script principal para entrenar modelo ML

Este script:
1. Ejecuta backtest modificado que extrae features
2. Carga el dataset con features
3. Entrena modelo LightGBM  
4. Guarda modelo en ml/models/

Uso:
    python train_model_from_backtest.py --months 6 --strategy REVERSAL
"""

import argparse
import pandas as pd
import sys
import os

# Agregar path del proyecto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ml.feature_extractor import extract_features
from ml.model_trainer import train_model
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Train ML model from backtest data')
    parser.add_argument('--csv', type=str, required=True,
                       help='Path to CSV with features and results')
    parser.add_argument('--strategy', type=str, default='REVERSAL',
                       choices=['REVERSAL', 'TREND'],
                       help='Strategy name (for model naming)')
    parser.add_argument('--threshold', type=float, default=0.65,
                       help='Default threshold for predictions')
    parser.add_argument('--test-size', type=float, default=0.33,
                       help='Test set proportion')
    
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("TRAINING ML MODEL FROM BACKTEST DATA")
    logger.info("=" * 70)
    logger.info(f"CSV: {args.csv}")
    logger.info(f"Strategy: {args.strategy}")
    logger.info(f"Threshold: {args.threshold:.0%}")
    logger.info("=" * 70)
    
    # Load CSV
    if not os.path.exists(args.csv):
        logger.error(f"❌ CSV not found: {args.csv}")
        return
    
    df = pd.read_csv(args.csv)
    logger.info(f"\n✅ CSV loaded: {len(df):,} trades")
    
    # Verificar columnas necesarias
    required_cols = ['result']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        logger.error(f"❌ Missing columns: {missing}")
        return
    
    # Crear target
    df['won'] = df['result'].isin(['TP1', 'TP2', 'TP3']).astype(int)
    logger.info(f"Win rate in data: {df['won'].mean():.2%}")
    
    # Separar features y target
    feature_cols = [col for col in df.columns 
                   if col not in ['strategy', 'side', 'entry_time', 'exit_time',
                                  'entry', 'sl', 'tp1', 'tp2', 'tp3', 
                                  'exit_price', 'result', 'pnl', 'won']]
    
    if len(feature_cols) == 0:
        logger.error("❌ No feature columns found in CSV!")
        logger.error("   El CSV debe contener features extraídas (rsi, atr, momentum_3, etc)")
        logger.error("   Necesitas modificar backtest.py para guardar features")
        return
    
    logger.info(f"\n✅ Features found: {len(feature_cols)}")
    logger.info(f"   {', '.join(feature_cols[:10])}...")
    
    X = df[feature_cols]
    y = df['won']
    
    # Train model
    model_name = f"{args.strategy.lower()}_model"
    model, test_acc, importance_df = train_model(
        X=X,
        y=y,
        model_name=model_name,
        test_size=args.test_size
    )
    
    logger.info("\n" + "=" * 70)
    logger.info("✅ TRAINING COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Model saved: ml/models/{model_name}.pkl")
    logger.info(f"Test accuracy: {test_acc:.2%}")
    logger.info(f"Default threshold: {args.threshold:.0%}")
    logger.info("\nNext steps:")
    logger.info("  1. Integrate MLPredictor in your strategy")
    logger.info("  2. Run backtest with ML enabled")
    logger.info("  3. Optimize threshold (try 0.60, 0.65, 0.70)")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()