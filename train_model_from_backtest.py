# train_model_from_backtest.py
"""
TRAIN MODEL - Script principal para entrenar modelo ML

Uso:
    python train_model_from_backtest.py --csv backtest_trades_sl6_tp5_ml.csv --strategy REVERSAL
"""
import argparse
import logging
import os
import sys

import joblib
import lightgbm as lgb
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Train ML model from backtest data")
    parser.add_argument("--csv", type=str, required=True,
                        help="Path to CSV with features and results")
    parser.add_argument("--strategy", type=str, default="REVERSAL",
                        choices=["REVERSAL", "TREND"],
                        help="Strategy name (for model naming)")
    parser.add_argument("--threshold", type=float, default=0.65,
                        help="Default threshold for predictions")
    parser.add_argument("--test-size", type=float, default=0.33,
                        help="Test set proportion")

    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("TRAINING ML MODEL FROM BACKTEST DATA")
    logger.info("=" * 70)
    logger.info(f"CSV: {args.csv}")
    logger.info(f"Strategy: {args.strategy}")
    logger.info(f"Threshold: {args.threshold:.0%}")
    logger.info("=" * 70)

    if not os.path.exists(args.csv):
        logger.error(f"CSV not found: {args.csv}")
        return

    df = pd.read_csv(args.csv)
    logger.info(f"\nCSV loaded: {len(df):,} trades")

    required_cols = ["result"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        logger.error(f"Missing columns: {missing}")
        return

    df["won"] = df["result"].isin(["TP1", "TP2", "TP3"]).astype(int)
    logger.info(f"Win rate in data: {df['won'].mean():.2%}")

    feature_cols = [col for col in df.columns
                    if col not in ["strategy", "side", "entry_time", "exit_time",
                                   "entry", "sl", "tp1", "tp2", "tp3",
                                   "exit_price", "result", "pnl", "won"]]

    if len(feature_cols) == 0:
        logger.error("No feature columns found in CSV!")
        logger.error("   El CSV debe contener features extraidas (rsi, atr, momentum_3, etc)")
        logger.error("   Necesitas modificar backtest.py para guardar features")
        return

    logger.info(f"\nFeatures found: {len(feature_cols)}")
    logger.info(f"   {', '.join(feature_cols[:10])}...")

    X = df[feature_cols].fillna(0)
    y = df["won"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, shuffle=False, random_state=42
    )

    logger.info(f"\nTrain samples: {len(X_train):,} (Win rate: {y_train.mean():.2%})")
    logger.info(f"Test samples:  {len(X_test):,} (Win rate: {y_test.mean():.2%})")

    n_losses = (y_train == 0).sum()
    n_wins = (y_train == 1).sum()
    weight_loss = 1.0
    weight_win = n_losses / n_wins if n_wins > 0 else 1.0

    logger.info(f"\nClass balancing:")
    logger.info(f"  Losses: {n_losses} trades (weight: {weight_loss:.2f})")
    logger.info(f"  Wins:   {n_wins} trades (weight: {weight_win:.2f})")

    logger.info(f"\nTraining LightGBM with improved parameters...")

    model = lgb.LGBMClassifier(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.03,
        min_child_samples=15,
        num_leaves=31,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbose=-1,
        force_col_wise=True,
        class_weight={0: weight_loss, 1: weight_win},
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        eval_metric="binary_logloss",
        callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)],
    )

    train_preds = model.predict(X_train)
    test_preds = model.predict(X_test)
    test_probs = model.predict_proba(X_test)[:, 1]

    train_acc = accuracy_score(y_train, train_preds)
    test_acc = accuracy_score(y_test, test_preds)

    logger.info("\n" + "=" * 70)
    logger.info("TRAINING RESULTS")
    logger.info("=" * 70)
    logger.info(f"Train accuracy: {train_acc:.2%}")
    logger.info(f"Test accuracy:  {test_acc:.2%}")

    if test_acc < train_acc - 0.10:
        logger.warning(f"Possible overfitting: train={train_acc:.2%} >> test={test_acc:.2%}")
    else:
        logger.info(f"Good generalization: test={test_acc:.2%} >= train={train_acc:.2%}")

    logger.info(f"\nTest Set Classification Report:")
    print(classification_report(y_test, test_preds, target_names=["Loss", "Win"]))

    logger.info(f"\nConfusion Matrix:")
    cm = confusion_matrix(y_test, test_preds)
    print(cm)

    unique_preds = len(set(test_preds))
    if unique_preds == 1:
        logger.warning("WARNING: Model is predicting only ONE class!")
        logger.warning("   Solutions:")
        logger.warning("   1. Try with more data (--months 12)")
        logger.warning("   2. Check if features are informative")
        logger.warning("   3. Try different threshold in prediction")

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
    logger.info(f"{'Threshold':<12} {'Trades':<8} {'Win Rate':<10} {'Precision':<12} {'Expected P&L'}")
    logger.info("-" * 70)

    for threshold in [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
        mask = test_probs >= threshold
        if mask.sum() == 0:
            continue
        filtered_y_true = y_test[mask]
        filtered_y_pred = (test_probs[mask] >= threshold).astype(int)
        wr = filtered_y_true.mean()
        precision = (filtered_y_true == filtered_y_pred).mean()
        n_trades = len(filtered_y_true)
        expected_pnl = n_trades * (wr * 7 - (1 - wr) * 3.3)
        logger.info(f"{threshold:<12.2f} {n_trades:<8d} {wr:<10.1%} {precision:<12.1%} ${expected_pnl:>7.0f}")

    os.makedirs("ml/models", exist_ok=True)
    model_name = f"{args.strategy.lower()}_model"
    model_path = f"ml/models/{model_name}.pkl"
    joblib.dump(model, model_path)
    logger.info(f"\nModel saved to: {model_path}")

    importance_path = f"ml/models/{model_name}_importance.csv"
    importance_df.to_csv(importance_path, index=False)
    logger.info(f"Feature importance saved to: {importance_path}")

    logger.info("\n" + "=" * 70)
    logger.info("TRAINING COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Model saved: ml/models/{model_name}.pkl")
    logger.info(f"Test accuracy: {test_acc:.2%}")
    logger.info(f"Default threshold: {args.threshold:.0%}")
    logger.info("\nNext steps:")
    logger.info("  1. Integrate MLPredictor in your strategy")
    logger.info("  2. Run backtest with ML enabled")
    logger.info("  3. Optimize threshold (look at threshold analysis above)")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()