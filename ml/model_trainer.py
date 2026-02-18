# ml/model_trainer.py
"""
Model Trainer

Entrena modelo LightGBM con datos historicos de trading.
"""
import logging
import os

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)


def train_model(
    X: pd.DataFrame,
    y: pd.Series,
    model_name: str = "trading_model",
    test_size: float = 0.33,
    n_estimators: int = 200,
    max_depth: int = 6,
    learning_rate: float = 0.05,
):
    """
    Entrena modelo LightGBM para predecir wins.

    Args:
        X: Features (DataFrame)
        y: Target (Series) - 1=win, 0=loss
        model_name: Nombre del modelo a guardar
        test_size: Proporcion para test set
        n_estimators: Arboles en el modelo
        max_depth: Profundidad maxima de arboles
        learning_rate: Tasa de aprendizaje

    Returns:
        Trained model, test accuracy, feature importance DataFrame
    """
    logger.info("=" * 70)
    logger.info(f"TRAINING MODEL: {model_name}")
    logger.info("=" * 70)
    logger.info(f"Total samples: {len(X):,}")
    logger.info(f"Features: {len(X.columns)}")
    logger.info(f"Win rate: {y.mean():.2%}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, shuffle=False, random_state=42
    )

    logger.info(f"\nTrain samples: {len(X_train):,}")
    logger.info(f"Test samples:  {len(X_test):,}")
    logger.info(f"Train win rate: {y_train.mean():.2%}")
    logger.info(f"Test win rate:  {y_test.mean():.2%}")

    logger.info(f"\nTraining LightGBM...")
    logger.info(f"  n_estimators={n_estimators}")
    logger.info(f"  max_depth={max_depth}")
    logger.info(f"  learning_rate={learning_rate}")

    model = lgb.LGBMClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        min_child_samples=20,
        num_leaves=31,
        random_state=42,
        verbose=-1,
        force_col_wise=True,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        eval_metric="binary_logloss",
        callbacks=[lgb.early_stopping(stopping_rounds=20, verbose=False)],
    )

    train_preds = model.predict(X_train)
    test_preds = model.predict(X_test)
    train_acc = accuracy_score(y_train, train_preds)
    test_acc = accuracy_score(y_test, test_preds)
    test_probs = model.predict_proba(X_test)[:, 1]

    logger.info("\n" + "=" * 70)
    logger.info("TRAINING RESULTS")
    logger.info("=" * 70)
    logger.info(f"Train accuracy: {train_acc:.2%}")
    logger.info(f"Test accuracy:  {test_acc:.2%}")

    if test_acc < train_acc - 0.10:
        logger.warning(f"Possible overfitting: train={train_acc:.2%} >> test={test_acc:.2%}")

    logger.info(f"\nTest Set Classification Report:")
    print(classification_report(y_test, test_preds, target_names=["Loss", "Win"], digits=3))

    logger.info(f"\nConfusion Matrix:")
    cm = confusion_matrix(y_test, test_preds)
    print(f"              Predicted")
    print(f"              Loss  Win")
    print(f"Actual Loss   {cm[0][0]:4d}  {cm[0][1]:4d}")
    print(f"       Win    {cm[1][0]:4d}  {cm[1][1]:4d}")

    importance_df = pd.DataFrame({
        "feature": X.columns,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False)

    logger.info("\n" + "=" * 70)
    logger.info("TOP 15 MOST IMPORTANT FEATURES")
    logger.info("=" * 70)
    for idx, row in importance_df.head(15).iterrows():
        logger.info(f"  {row['feature']:<30} {row['importance']:>8.1f}")

    logger.info("\n" + "=" * 70)
    logger.info("THRESHOLD ANALYSIS (on test set)")
    logger.info("=" * 70)
    logger.info(f"{'Threshold':<12} {'Trades':<8} {'Win Rate':<10} {'Expected P&L'}")
    logger.info("-" * 70)

    for threshold in [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
        mask = test_probs >= threshold
        if mask.sum() == 0:
            continue
        filtered_y = y_test[mask]
        wr = filtered_y.mean()
        n_trades = len(filtered_y)
        expected_pnl = n_trades * (wr * 7 - (1 - wr) * 3.3)
        logger.info(f"{threshold:<12.2f} {n_trades:<8d} {wr:<10.1%} ${expected_pnl:>7.0f}")

    os.makedirs("ml/models", exist_ok=True)
    model_path = f"ml/models/{model_name}.pkl"
    joblib.dump(model, model_path)
    logger.info(f"\nModel saved to: {model_path}")

    importance_path = f"ml/models/{model_name}_importance.csv"
    importance_df.to_csv(importance_path, index=False)
    logger.info(f"Feature importance saved to: {importance_path}")

    return model, test_acc, importance_df


if __name__ == "__main__":
    print("Model Trainer")
    print("Uso: Importa train_model() y pasale X, y")