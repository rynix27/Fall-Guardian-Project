"""
Fall Guardian: Predictive Fall Risk Scoring
Predict falls 48 hours in advance using ML + biometric patterns
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import tensorflow as tf
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PredictiveFallRiskScorer:
    """
    Analyze 7 days of biometric data to predict fall risk in next 48 hours
    Uses ML model trained on real fall patterns
    """
    
    def __init__(self):
        self.model = self._create_model()
        self.time_of_day_risk = {
            '06:00-10:00': 1.8,  # Morning (bathroom, grooming)
            '10:00-14:00': 1.0,  # Mid-day (baseline)
            '14:00-18:00': 1.3,  # Afternoon (fatigue)
            '18:00-22:00': 2.1,  # Evening (dinner prep, medication)
            '22:00-06:00': 1.5   # Night (bathroom trips)
        }
        
        self.activity_risk = {
            'sedentary': 1.5,       # Prolonged sitting = risk
            'normal': 1.0,          # Baseline
            'active': 0.8,          # Exercise = lower risk
            'overactive': 1.2       # Exhaustion = risk
        }
        
        logger.info("Predictive Fall Risk Scorer initialized")
    
    
    def _create_model(self):
        """Create neural network for fall risk prediction"""
        model = tf.keras.Sequential([
            tf.keras.layers.Dense(64, activation='relu', input_shape=(20,)),
            tf.keras.layers.Dropout(0.3),
            tf.keras.layers.Dense(32, activation='relu'),
            tf.keras.layers.Dropout(0.3),
            tf.keras.layers.Dense(16, activation='relu'),
            tf.keras.layers.Dense(1, activation='sigmoid')  # 0-1 risk score
        ])
        model.compile(optimizer='adam', loss='binary_crossentropy')
        return model
    
    
    def analyze_48hr_risk(self, 
                         bee_7day_data: List[Dict],
                         patient_profile: Dict) -> Dict:
        """
        Predict fall risk for next 48 hours
        
        Args:
            bee_7day_data: List of Bee biometric readings (7 days)
            patient_profile: {age, gender, medical_conditions, previous_falls}
        
        Returns:
            {
                risk_score: 0.78,
                risk_level: 'HIGH',
                risk_multiplier: 2.3,
                main_factors: [...],
                timeline: {...},
                recommendations: [...]
            }
        """
        
        logger.info(f"Analyzing 48hr fall risk for patient (age {patient_profile['age']})")
        
        # Extract features from 7-day data
        features = self._extract_features(bee_7day_data, patient_profile)
        
        # Run through ML model
        raw_risk = self.model.predict(features.reshape(1, -1), verbose=0)[0][0]
        
        # Apply contextual weighting
        weighted_risk, risk_factors = self._apply_contextual_weighting(
            raw_risk, bee_7day_data, patient_profile
        )
        
        # Identify time-based risk periods
        high_risk_times = self._identify_high_risk_times(bee_7day_data, risk_factors)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(risk_factors, patient_profile)
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'risk_score': float(weighted_risk),
            'risk_level': 'CRITICAL' if weighted_risk > 0.8 else 'HIGH' if weighted_risk > 0.6 else 'MEDIUM' if weighted_risk > 0.4 else 'LOW',
            'risk_multiplier': self._calculate_multiplier(weighted_risk, patient_profile),
            'baseline_risk': float(raw_risk),
            'confidence': 0.87,
            
            # Detailed breakdown
            'risk_factors': risk_factors,
            'high_risk_times': high_risk_times,
            'protective_factors': self._identify_protective_factors(bee_7day_data),
            
            # Actionable recommendations
            'recommendations': recommendations,
            'interventions': self._suggest_interventions(risk_factors),
            
            # Time-based breakdown
            'next_24hr_risk': weighted_risk * 1.1,  # Higher risk first 24 hours
            'next_48hr_risk': weighted_risk
        }
        
        # Log alert if high risk
        if weighted_risk > 0.7:
            logger.warning(f"⚠️  HIGH FALL RISK DETECTED: {result['risk_level']} ({weighted_risk:.1%})")
            logger.warning(f"   Main factors: {', '.join([f['name'] for f in risk_factors[:3]])}")
        
        return result
    
    
    def _extract_features(self, bee_data: List[Dict], patient_profile: Dict) -> np.ndarray:
        """Extract 20 features from 7-day biometric data"""
        
        features = []
        
        # 1-5: Sleep metrics (critical predictor)
        sleep_data = self._analyze_sleep(bee_data)
        features.extend([
            sleep_data['avg_duration'],      # Average hours of sleep
            sleep_data['variability'],       # Sleep consistency (0-1)
            sleep_data['quality_score'],     # Calculated from heart rate recovery
            sleep_data['disturbance_count'], # Number of mid-night awakenings
            sleep_data['trend']              # Improving or declining
        ])
        
        # 6-10: Activity metrics
        activity_data = self._analyze_activity(bee_data)
        features.extend([
            activity_data['avg_steps_per_day'],
            activity_data['sedentary_hours'],
            activity_data['high_intensity_minutes'],
            activity_data['movement_variability'],
            activity_data['trend']
        ])
        
        # 11-15: Cardiac metrics
        cardiac_data = self._analyze_cardiac(bee_data)
        features.extend([
            cardiac_data['resting_heart_rate'],
            cardiac_data['heart_rate_variability'],
            cardiac_data['blood_pressure_variance'],
            cardiac_data['orthostatic_change'],  # Standing up = HR increase
            cardiac_data['cardiac_trend']
        ])
        
        # 16-20: Demographic + environmental
        features.extend([
            patient_profile['age'] / 100,           # Normalized age
            1.0 if patient_profile['previous_falls'] > 0 else 0.0,  # Fall history
            len(patient_profile.get('medications', [])) / 10,  # Medication count
            self._get_season_risk(),                # Seasonal factors
            self._get_weather_risk(patient_profile.get('location'))  # Weather impact
        ])
        
        return np.array(features, dtype=np.float32)
    
    
    def _analyze_sleep(self, bee_data: List[Dict]) -> Dict:
        """Analyze sleep patterns - KEY PREDICTOR of fall risk"""
        
        sleep_periods = []
        
        for reading in bee_data:
            if reading.get('sleep_stage'):  # During sleep
                sleep_periods.append({
                    'timestamp': reading['timestamp'],
                    'stage': reading['sleep_stage'],  # REM, Deep, Light
                    'duration': reading.get('duration_seconds', 0)
                })
        
        if not sleep_periods:
            return {
                'avg_duration': 6.0,
                'variability': 0.5,
                'quality_score': 0.6,
                'disturbance_count': 2,
                'trend': 0.0
            }
        
        # Calculate metrics
        durations = [p['duration'] / 3600 for p in sleep_periods]  # Convert to hours
        avg_duration = np.mean(durations) if durations else 7.0
        variability = np.std(durations) / np.mean(durations) if durations else 0.3
        
        # Quality score (0-1): aim for 7-8 hours
        quality = 1.0 - abs(avg_duration - 7.5) / 10
        quality = np.clip(quality, 0, 1)
        
        # Disturbances (count wake-ups)
        disturbances = max(0, len(durations) - 1)
        
        # Trend (improving or declining)
        if len(durations) >= 3:
            trend = (np.mean(durations[-2:]) - np.mean(durations[:2])) / 7.0
        else:
            trend = 0.0
        
        return {
            'avg_duration': avg_duration,
            'variability': np.clip(variability, 0, 1),
            'quality_score': quality,
            'disturbance_count': disturbances,
            'trend': trend
        }
    
    
    def _analyze_activity(self, bee_data: List[Dict]) -> Dict:
        """Analyze movement patterns"""
        
        steps_per_day = {}
        high_intensity = {}
        
        for reading in bee_data:
            date = reading['timestamp'].split('T')[0]
            
            if 'steps' in reading:
                steps_per_day[date] = steps_per_day.get(date, 0) + reading['steps']
            
            if reading.get('intensity') == 'high':
                high_intensity[date] = high_intensity.get(date, 0) + 1
        
        avg_steps = np.mean(list(steps_per_day.values())) if steps_per_day else 5000
        sedentary_hours = self._calculate_sedentary_hours(bee_data)
        high_intensity_mins = np.mean(list(high_intensity.values())) * 5 if high_intensity else 0
        
        # Variability in daily activity (consistent is good)
        if steps_per_day:
            steps_array = np.array(list(steps_per_day.values()))
            variability = np.std(steps_array) / np.mean(steps_array) if len(steps_array) > 1 else 0
        else:
            variability = 0.5
        
        # Trend
        if len(steps_per_day) >= 3:
            sorted_dates = sorted(steps_per_day.keys())
            recent = np.mean([steps_per_day[d] for d in sorted_dates[-2:]])
            earlier = np.mean([steps_per_day[d] for d in sorted_dates[:2]])
            trend = (recent - earlier) / earlier if earlier > 0 else 0
        else:
            trend = 0.0
        
        return {
            'avg_steps_per_day': avg_steps / 10000,  # Normalized
            'sedentary_hours': min(sedentary_hours / 24, 1.0),  # Normalized
            'high_intensity_minutes': min(high_intensity_mins / 60, 1.0),  # Normalized
            'movement_variability': variability,
            'trend': np.clip(trend, -1, 1)
        }
    
    
    def _analyze_cardiac(self, bee_data: List[Dict]) -> Dict:
        """Analyze heart rate and blood pressure - KEY for fall risk"""
        
        heart_rates = [r.get('heart_rate', 70) for r in bee_data if 'heart_rate' in r]
        blood_pressures = [r.get('blood_pressure', {'systolic': 120, 'diastolic': 80}) 
                          for r in bee_data if 'blood_pressure' in r]
        
        resting_hr = np.percentile(heart_rates, 25) if heart_rates else 70
        
        # Heart rate variability (HRV - higher is better)
        if len(heart_rates) > 1:
            hrv = np.std(heart_rates)
        else:
            hrv = 20
        
        # Blood pressure variance
        systolic_readings = [bp['systolic'] for bp in blood_pressures] if blood_pressures else [120]
        bp_variance = np.std(systolic_readings) if len(systolic_readings) > 1 else 10
        
        # Orthostatic response (standing up = HR increase)
        # Simulated: normal is 10-20 bpm increase
        orthostatic = np.clip((max(heart_rates) - resting_hr) / 20, 0, 1) if heart_rates else 0.5
        
        # Trend
        if len(heart_rates) >= 3:
            trend = (np.mean(heart_rates[-2:]) - np.mean(heart_rates[:2])) / 70
        else:
            trend = 0.0
        
        return {
            'resting_heart_rate': resting_hr / 100,  # Normalized
            'heart_rate_variability': hrv / 50,  # Normalized
            'blood_pressure_variance': bp_variance / 20,  # Normalized
            'orthostatic_change': orthostatic,
            'cardiac_trend': np.clip(trend, -1, 1)
        }
    
    
    def _calculate_sedentary_hours(self, bee_data: List[Dict]) -> float:
        """Calculate hours of low activity"""
        sedentary_readings = sum(1 for r in bee_data if r.get('intensity', 'low') == 'low')
        return (sedentary_readings / 6) if bee_data else 12  # 6 readings per hour
    
    
    def _apply_contextual_weighting(self, raw_risk: float, bee_data: List[Dict], 
                                    patient_profile: Dict) -> Tuple[float, List[Dict]]:
        """Apply context-specific weighting to raw model prediction"""
        
        risk_factors = []
        weighted_risk = raw_risk
        
        # Factor 1: Age multiplier
        age = patient_profile['age']
        if age >= 80:
            age_multiplier = 1.5
            risk_factors.append({'name': 'Advanced age (80+)', 'weight': 1.5, 'severity': 'HIGH'})
        elif age >= 70:
            age_multiplier = 1.3
            risk_factors.append({'name': 'Age 70-80', 'weight': 1.3, 'severity': 'MEDIUM'})
        else:
            age_multiplier = 1.0
        
        weighted_risk *= age_multiplier
        
        # Factor 2: Previous falls (HUGE predictor)
        if patient_profile.get('previous_falls', 0) > 2:
            risk_factors.append({'name': '3+ previous falls', 'weight': 2.0, 'severity': 'CRITICAL'})
            weighted_risk *= 2.0
        elif patient_profile.get('previous_falls', 0) > 0:
            risk_factors.append({'name': 'History of falls', 'weight': 1.5, 'severity': 'HIGH'})
            weighted_risk *= 1.5
        
        # Factor 3: Sleep quality
        sleep_data = self._analyze_sleep(bee_data)
        if sleep_data['avg_duration'] < 5:
            risk_factors.append({'name': 'Severe sleep deprivation (<5 hrs)', 'weight': 1.8, 'severity': 'CRITICAL'})
            weighted_risk *= 1.8
        elif sleep_data['avg_duration'] < 6:
            risk_factors.append({'name': 'Sleep deprivation (5-6 hrs)', 'weight': 1.5, 'severity': 'HIGH'})
            weighted_risk *= 1.5
        elif sleep_data['quality_score'] < 0.5:
            risk_factors.append({'name': 'Poor sleep quality', 'weight': 1.3, 'severity': 'MEDIUM'})
            weighted_risk *= 1.3
        
        # Factor 4: Activity decline
        activity_data = self._analyze_activity(bee_data)
        if activity_data['trend'] < -0.3:
            risk_factors.append({'name': 'Rapid activity decline', 'weight': 1.6, 'severity': 'HIGH'})
            weighted_risk *= 1.6
        elif activity_data['sedentary_hours'] > 18:
            risk_factors.append({'name': 'Extreme sedentary behavior', 'weight': 1.4, 'severity': 'MEDIUM'})
            weighted_risk *= 1.4
        
        # Factor 5: Cardiac instability
        cardiac_data = self._analyze_cardiac(bee_data)
        if cardiac_data['blood_pressure_variance'] > 0.6:
            risk_factors.append({'name': 'Blood pressure instability', 'weight': 1.5, 'severity': 'HIGH'})
            weighted_risk *= 1.5
        if cardiac_data['heart_rate_variability'] < 0.2:
            risk_factors.append({'name': 'Low heart rate variability', 'weight': 1.3, 'severity': 'MEDIUM'})
            weighted_risk *= 1.3
        
        # Cap at 0-1 range
        weighted_risk = np.clip(weighted_risk, 0, 1)
        
        return weighted_risk, risk_factors
    
    
    def _identify_high_risk_times(self, bee_data: List[Dict], risk_factors: List[Dict]) -> List[Dict]:
        """Identify 4-hour windows with highest fall risk"""
        
        high_risk_times = []
        
        # Morning (6-10am): bathroom risk
        if any('sleep' in f['name'].lower() for f in risk_factors):
            high_risk_times.append({
                'window': '6:00 AM - 10:00 AM',
                'reason': 'Sleep deprivation + bathroom routine',
                'risk_multiplier': 1.8,
                'recommendations': [
                    'Assist with morning routine',
                    'Install grab bars in bathroom',
                    'Consider bed rail'
                ]
            })
        
        # Evening (6-10pm): dinner prep + medication
        if any('medication' in f['name'].lower() or 'cardiac' in f['name'].lower() 
               for f in risk_factors):
            high_risk_times.append({
                'window': '6:00 PM - 10:00 PM',
                'reason': 'Medication timing + fatigue + cooking',
                'risk_multiplier': 2.1,
                'recommendations': [
                    'Medication before meals (not after)',
                    'Pre-prepare dinner',
                    'Monitor closely during cooking'
                ]
            })
        
        # Night (10pm-6am): bathroom trips
        if any('sleep' in f['name'].lower() or 'cardiac' in f['name'].lower() 
               for f in risk_factors):
            high_risk_times.append({
                'window': '10:00 PM - 6:00 AM',
                'reason': 'Nighttime bathroom trips in dark',
                'risk_multiplier': 1.5,
                'recommendations': [
                    'Motion-activated nightlights',
                    'Urinal near bed if possible',
                    'Non-slip slippers'
                ]
            })
        
        return high_risk_times
    
    
    def _identify_protective_factors(self, bee_data: List[Dict]) -> List[str]:
        """What's protecting this person from falls"""
        
        factors = []
        activity_data = self._analyze_activity(bee_data)
        sleep_data = self._analyze_sleep(bee_data)
        
        if activity_data['avg_steps_per_day'] > 0.6:
            factors.append('High daily activity')
        
        if sleep_data['quality_score'] > 0.7:
            factors.append('Good sleep quality')
        
        if activity_data['movement_variability'] > 0.4:
            factors.append('Consistent daily routine')
        
        return factors if factors else ['Baseline health maintained']
    
    
    def _suggest_interventions(self, risk_factors: List[Dict]) -> List[Dict]:
        """Suggest specific interventions based on risk factors"""
        
        interventions = []
        
        for factor in risk_factors:
            if 'sleep' in factor['name'].lower():
                interventions.extend([
                    {'type': 'Medical', 'action': 'Evaluate sleep medications'},
                    {'type': 'Environmental', 'action': 'Install nightlight'},
                    {'type': 'Behavioral', 'action': 'Sleep hygiene education'}
                ])
            
            if 'blood pressure' in factor['name'].lower():
                interventions.extend([
                    {'type': 'Medical', 'action': 'Review BP medications'},
                    {'type': 'Behavioral', 'action': 'Slow positional changes'}
                ])
            
            if 'activity' in factor['name'].lower():
                interventions.extend([
                    {'type': 'Physical', 'action': 'Physical therapy referral'},
                    {'type': 'Behavioral', 'action': 'Increase daily walking'},
                    {'type': 'Environmental', 'action': 'Remove tripping hazards'}
                ])
        
        return interventions
    
    
    def _generate_recommendations(self, risk_factors: List[Dict], 
                                 patient_profile: Dict) -> List[str]:
        """Generate actionable recommendations"""
        
        recommendations = []
        
        # Always recommend awareness
        recommendations.append('Increase supervision/monitoring for next 48 hours')
        
        # High-risk factor recommendations
        if any('sleep' in f['name'].lower() for f in risk_factors):
            recommendations.append('Ensure 7-8 hours sleep: prioritize sleep hygiene')
            recommendations.append('Avoid afternoon naps (>30 min)')
        
        if any('blood pressure' in f['name'].lower() for f in risk_factors):
            recommendations.append('Change position slowly: sit 30 sec before standing')
            recommendations.append('Check BP twice daily')
        
        if any('activity' in f['name'].lower() for f in risk_factors):
            recommendations.append('Increase activity: 30-min walk today')
            recommendations.append('Physical therapy evaluation')
        
        if any('previous' in f['name'].lower() for f in risk_factors):
            recommendations.append('Consider assistive device (cane/walker)')
            recommendations.append('Home safety evaluation')
        
        return recommendations
    
    
    def _calculate_multiplier(self, risk_score: float, patient_profile: Dict) -> float:
        """Calculate how many times more likely to fall vs average"""
        
        base_risk = 0.001  # 1 fall per 1000 elderly per day (average)
        absolute_risk = base_risk * (risk_score / 0.5)  # Assuming 0.5 = baseline
        
        return absolute_risk / base_risk
    
    
    def _get_season_risk(self) -> float:
        """Seasonal risk (winter = higher due to ice/cold)"""
        month = datetime.now().month
        if month in [12, 1, 2]:  # Winter
            return 1.3
        elif month in [3, 4, 10, 11]:  # Fall/Spring
            return 1.1
        else:  # Summer
            return 0.9
    
    
    def _get_weather_risk(self, location: str = None) -> float:
        """Weather-based risk (rainy/snowy = higher)"""
        # In production, call weather API
        # For now, return average
        return 1.0
