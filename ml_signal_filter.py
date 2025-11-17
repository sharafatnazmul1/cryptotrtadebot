"""
Machine Learning Signal Filter and Market Regime Detection
Uses ML models to filter signals and classify market conditions
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
import pickle
from pathlib import Path

try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    import xgboost as xgb
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logging.warning("ML libraries not available. Install scikit-learn and xgboost.")

logger = logging.getLogger(__name__)


@dataclass
class MarketRegime:
    """Market regime classification"""
    regime: str  # 'trending_bullish', 'trending_bearish', 'ranging', 'high_volatility'
    confidence: float
    features: Dict


@dataclass
class SignalQuality:
    """ML-based signal quality assessment"""
    score: float  # 0-1, higher is better
    confidence: float
    prediction: str  # 'take', 'skip'
    features: Dict


class MLSignalFilter:
    """
    Machine Learning-based signal filtering and market regime detection
    """

    def __init__(self, config: Dict):
        """Initialize ML signal filter"""
        self.config = config
        self.model_path = Path(config.get('model_path', './models'))
        self.model_path.mkdir(exist_ok=True)

        # Models
        self.signal_quality_model = None
        self.regime_classifier = None
        self.scaler = StandardScaler()

        # Training data buffer
        self.training_data = []
        self.max_training_samples = config.get('max_training_samples', 1000)
        self.min_samples_for_training = config.get('min_samples_for_training', 50)

        # Load models if they exist
        self._load_models()

        logger.info("ML Signal Filter initialized")

    def _load_models(self):
        """Load pre-trained models from disk"""
        try:
            signal_model_file = self.model_path / 'signal_quality_model.pkl'
            regime_model_file = self.model_path / 'regime_classifier.pkl'
            scaler_file = self.model_path / 'scaler.pkl'

            if signal_model_file.exists():
                with open(signal_model_file, 'rb') as f:
                    self.signal_quality_model = pickle.load(f)
                logger.info("Loaded signal quality model")

            if regime_model_file.exists():
                with open(regime_model_file, 'rb') as f:
                    self.regime_classifier = pickle.load(f)
                logger.info("Loaded regime classifier")

            if scaler_file.exists():
                with open(scaler_file, 'rb') as f:
                    self.scaler = pickle.load(f)
                logger.info("Loaded feature scaler")

        except Exception as e:
            logger.error(f"Error loading models: {e}")

    def _save_models(self):
        """Save trained models to disk"""
        try:
            if self.signal_quality_model:
                with open(self.model_path / 'signal_quality_model.pkl', 'wb') as f:
                    pickle.dump(self.signal_quality_model, f)

            if self.regime_classifier:
                with open(self.model_path / 'regime_classifier.pkl', 'wb') as f:
                    pickle.dump(self.regime_classifier, f)

            with open(self.model_path / 'scaler.pkl', 'wb') as f:
                pickle.dump(self.scaler, f)

            logger.info("Models saved successfully")

        except Exception as e:
            logger.error(f"Error saving models: {e}")

    def extract_features(self, signal: Dict, market_data: pd.DataFrame) -> Dict:
        """
        Extract features from signal and market data for ML model
        """
        try:
            features = {}

            # Signal features
            features['signal_score'] = signal.get('signal_score', 0)
            features['rr_ratio'] = signal.get('rr_ratio', 0)
            features['distance_to_entry'] = signal.get('distance_to_entry', 0)

            # Market structure features
            features['htf_trend_bullish'] = 1 if signal.get('htf_trend') == 'bullish' else 0
            features['mtf_trend_bullish'] = 1 if signal.get('mtf_trend') == 'bullish' else 0
            features['choch_detected'] = 1 if signal.get('choch', False) else 0
            features['bos_detected'] = 1 if signal.get('bos', False) else 0

            # Zone features
            features['zone_is_ob'] = 1 if signal.get('zone_type') == 'OB' else 0
            features['zone_strength'] = signal.get('zone_data', {}).get('strength', 0)
            features['zone_age'] = signal.get('zone_data', {}).get('age', 0)

            # Technical indicators from market data
            if len(market_data) >= 20:
                recent = market_data.tail(20)

                # Volatility
                returns = recent['close'].pct_change()
                features['volatility'] = returns.std()

                # Momentum
                features['momentum'] = (recent['close'].iloc[-1] - recent['close'].iloc[0]) / recent['close'].iloc[0]

                # Volume trend
                if 'tick_volume' in recent.columns:
                    features['volume_trend'] = recent['tick_volume'].iloc[-5:].mean() / recent['tick_volume'].mean()
                else:
                    features['volume_trend'] = 1.0

                # Price position in range
                range_high = recent['high'].max()
                range_low = recent['low'].min()
                current_price = recent['close'].iloc[-1]
                features['price_position'] = (current_price - range_low) / (range_high - range_low) if range_high != range_low else 0.5

                # Trend strength (ADX-like)
                highs = recent['high']
                lows = recent['low']
                plus_dm = (highs.diff()).apply(lambda x: max(x, 0))
                minus_dm = (-lows.diff()).apply(lambda x: max(x, 0))
                features['trend_strength'] = abs(plus_dm.mean() - minus_dm.mean())

            else:
                # Default values if not enough data
                features['volatility'] = 0.01
                features['momentum'] = 0.0
                features['volume_trend'] = 1.0
                features['price_position'] = 0.5
                features['trend_strength'] = 0.0

            # Time-based features
            if 'timestamp' in signal:
                timestamp = signal['timestamp']
                features['hour'] = timestamp.hour
                features['day_of_week'] = timestamp.weekday()
                features['is_killzone'] = 1 if self._is_killzone(timestamp) else 0
            else:
                features['hour'] = 0
                features['day_of_week'] = 0
                features['is_killzone'] = 0

            return features

        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return {}

    def _is_killzone(self, timestamp) -> bool:
        """Check if timestamp is in a killzone"""
        hour = timestamp.hour
        return (2 <= hour < 5) or (8 <= hour < 11) or (13 <= hour < 16)

    def predict_signal_quality(self, signal: Dict, market_data: pd.DataFrame) -> SignalQuality:
        """
        Predict if a signal is likely to be profitable
        Returns quality score and recommendation
        """
        try:
            # Extract features
            features = self.extract_features(signal, market_data)

            # If model not trained yet, use rule-based scoring
            if not self.signal_quality_model:
                score = self._rule_based_quality_score(features)
                prediction = 'take' if score > 0.6 else 'skip'

                return SignalQuality(
                    score=score,
                    confidence=0.5,
                    prediction=prediction,
                    features=features
                )

            # Prepare features for model
            feature_values = np.array([list(features.values())])
            feature_values = self.scaler.transform(feature_values)

            # Get prediction
            prediction_proba = self.signal_quality_model.predict_proba(feature_values)[0]
            prediction = 'take' if prediction_proba[1] > 0.5 else 'skip'
            confidence = max(prediction_proba)
            score = prediction_proba[1]  # Probability of positive class

            return SignalQuality(
                score=score,
                confidence=confidence,
                prediction=prediction,
                features=features
            )

        except Exception as e:
            logger.error(f"Error predicting signal quality: {e}")
            # Return neutral prediction on error
            return SignalQuality(score=0.5, confidence=0.0, prediction='skip', features={})

    def _rule_based_quality_score(self, features: Dict) -> float:
        """Simple rule-based quality scoring when ML model not available"""
        score = 0.0

        # Signal score contribution (0-0.3)
        score += min(features.get('signal_score', 0) / 10, 0.3)

        # RR ratio contribution (0-0.2)
        rr = features.get('rr_ratio', 0)
        score += min(rr / 10, 0.2)

        # Trend alignment (0-0.2)
        if features.get('htf_trend_bullish') == features.get('mtf_trend_bullish'):
            score += 0.2

        # Zone quality (0-0.15)
        score += min(features.get('zone_strength', 0) / 5, 0.15)

        # Killzone bonus (0-0.15)
        if features.get('is_killzone'):
            score += 0.15

        return min(score, 1.0)

    def classify_market_regime(self, market_data: pd.DataFrame) -> MarketRegime:
        """
        Classify current market regime
        Returns: trending_bullish, trending_bearish, ranging, high_volatility
        """
        try:
            if len(market_data) < 50:
                return MarketRegime('unknown', 0.0, {})

            # Calculate regime features
            features = {}
            recent = market_data.tail(50)

            # Trend metrics
            sma_20 = recent['close'].rolling(20).mean()
            sma_50 = recent['close'].rolling(50).mean()
            features['sma_slope'] = (sma_20.iloc[-1] - sma_20.iloc[-10]) / sma_20.iloc[-10]

            # Volatility
            returns = recent['close'].pct_change()
            features['volatility'] = returns.std()
            features['volatility_percentile'] = (features['volatility'] - returns.rolling(50).std().min()) / \
                                                (returns.rolling(50).std().max() - returns.rolling(50).std().min() + 1e-9)

            # Range metrics
            high_50 = recent['high'].max()
            low_50 = recent['low'].min()
            current = recent['close'].iloc[-1]
            features['range_position'] = (current - low_50) / (high_50 - low_50) if high_50 != low_50 else 0.5

            # Momentum
            features['momentum_10'] = (recent['close'].iloc[-1] - recent['close'].iloc[-10]) / recent['close'].iloc[-10]

            # ADX-like trend strength
            highs = recent['high']
            lows = recent['low']
            plus_dm = (highs.diff()).apply(lambda x: max(x, 0)).rolling(14).mean()
            minus_dm = (-lows.diff()).apply(lambda x: max(x, 0)).rolling(14).mean()
            features['trend_strength'] = abs(plus_dm.iloc[-1] - minus_dm.iloc[-1])

            # If model available, use it
            if self.regime_classifier:
                feature_values = np.array([list(features.values())])
                feature_values = self.scaler.transform(feature_values)

                prediction = self.regime_classifier.predict(feature_values)[0]
                confidence = max(self.regime_classifier.predict_proba(feature_values)[0])

                return MarketRegime(
                    regime=prediction,
                    confidence=confidence,
                    features=features
                )

            # Rule-based classification
            regime, confidence = self._rule_based_regime(features)

            return MarketRegime(
                regime=regime,
                confidence=confidence,
                features=features
            )

        except Exception as e:
            logger.error(f"Error classifying market regime: {e}")
            return MarketRegime('unknown', 0.0, {})

    def _rule_based_regime(self, features: Dict) -> Tuple[str, float]:
        """Rule-based regime classification"""
        try:
            # High volatility check
            if features['volatility_percentile'] > 0.8:
                return 'high_volatility', 0.7

            # Ranging market check
            if abs(features['momentum_10']) < 0.005 and features['trend_strength'] < 0.001:
                return 'ranging', 0.6

            # Trending market
            if features['sma_slope'] > 0.01 and features['momentum_10'] > 0:
                return 'trending_bullish', 0.7
            elif features['sma_slope'] < -0.01 and features['momentum_10'] < 0:
                return 'trending_bearish', 0.7

            # Default to ranging
            return 'ranging', 0.5

        except Exception as e:
            logger.error(f"Error in rule-based regime: {e}")
            return 'unknown', 0.0

    def add_training_sample(self, signal: Dict, market_data: pd.DataFrame,
                           outcome: bool, profit_pct: float):
        """
        Add a training sample from a completed trade
        outcome: True if profitable, False if loss
        """
        try:
            features = self.extract_features(signal, market_data)
            features['outcome'] = 1 if outcome else 0
            features['profit_pct'] = profit_pct

            self.training_data.append(features)

            # Keep only recent samples
            if len(self.training_data) > self.max_training_samples:
                self.training_data = self.training_data[-self.max_training_samples:]

            # Retrain periodically
            if len(self.training_data) >= self.min_samples_for_training and \
               len(self.training_data) % 20 == 0:
                self.retrain_models()

        except Exception as e:
            logger.error(f"Error adding training sample: {e}")

    def retrain_models(self):
        """Retrain ML models with accumulated data"""
        try:
            if not ML_AVAILABLE:
                logger.warning("ML libraries not available, skipping training")
                return

            if len(self.training_data) < self.min_samples_for_training:
                logger.warning("Not enough training samples")
                return

            # Prepare training data
            df = pd.DataFrame(self.training_data)

            # Remove outcome columns for features
            X = df.drop(['outcome', 'profit_pct'], axis=1)
            y = df['outcome']

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)

            # Train signal quality model (XGBoost)
            self.signal_quality_model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )
            self.signal_quality_model.fit(X_train_scaled, y_train)

            # Evaluate
            train_score = self.signal_quality_model.score(X_train_scaled, y_train)
            test_score = self.signal_quality_model.score(X_test_scaled, y_test)

            logger.info(f"Retrained signal quality model - Train: {train_score:.3f}, Test: {test_score:.3f}")

            # Save models
            self._save_models()

        except Exception as e:
            logger.error(f"Error retraining models: {e}")

    def get_feature_importance(self) -> Optional[Dict]:
        """Get feature importance from trained model"""
        try:
            if not self.signal_quality_model or not hasattr(self.signal_quality_model, 'feature_importances_'):
                return None

            if not self.training_data:
                return None

            # Get feature names
            df = pd.DataFrame(self.training_data)
            feature_names = df.drop(['outcome', 'profit_pct'], axis=1).columns.tolist()

            # Get importance scores
            importance_scores = self.signal_quality_model.feature_importances_

            # Create dictionary
            importance_dict = dict(zip(feature_names, importance_scores))

            # Sort by importance
            importance_dict = dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))

            return importance_dict

        except Exception as e:
            logger.error(f"Error getting feature importance: {e}")
            return None
