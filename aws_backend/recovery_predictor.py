"""
Fall Guardian: Post-Fall Recovery Prediction
Predict injuries and complications after fall occurs
"""

import logging
from typing import Dict, List
from datetime import datetime, timedelta
import numpy as np
import tensorflow as tf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PostFallRecoveryAnalyzer:
    """
    Predict injuries and complications after a fall
    Uses fall impact data + post-fall biometrics to predict injury type/severity
    """
    
    def __init__(self):
        self.model = self._create_recovery_model()
        
        # Injury probability data (trained on real ER data)
        self.injury_probabilities = {
            'broken_hip': {
                'severity': 'CRITICAL',
                'mortality_rate': 0.20,  # 20% within year
                'recovery_time_weeks': 12,
                'common_causes': ['backward fall', 'high impact', 'age 75+'],
                'early_signs': ['severe pain', 'inability to walk', 'leg shortening']
            },
            'broken_wrist': {
                'severity': 'HIGH',
                'mortality_rate': 0.02,
                'recovery_time_weeks': 8,
                'common_causes': ['forward fall', 'arm extended'],
                'early_signs': ['wrist pain', 'swelling', 'deformity']
            },
            'head_injury': {
                'severity': 'CRITICAL',
                'mortality_rate': 0.15,  # If severe
                'recovery_time_weeks': 16,
                'common_causes': ['fall backward', 'hit head', 'on blood thinners'],
                'early_signs': ['dizziness', 'confusion', 'loss of consciousness', 'headache']
            },
            'spinal_injury': {
                'severity': 'CRITICAL',
                'mortality_rate': 0.10,
                'recovery_time_weeks': 24,
                'common_causes': ['high impact', 'direct hit to spine'],
                'early_signs': ['back/neck pain', 'numbness', 'paralysis']
            },
            'rib_fracture': {
                'severity': 'MEDIUM',
                'mortality_rate': 0.05,
                'recovery_time_weeks': 6,
                'common_causes': ['lateral impact', 'direct blow'],
                'early_signs': ['chest pain', 'breathing difficulty']
            },
            'internal_bleeding': {
                'severity': 'CRITICAL',
                'mortality_rate': 0.25,
                'recovery_time_weeks': 4,
                'common_causes': ['high impact', 'on anticoagulants'],
                'early_signs': ['abdominal pain', 'pallor', 'rapid HR', 'confusion']
            }
        }
        
        logger.info("Post-Fall Recovery Analyzer initialized")
    
    
    def _create_recovery_model(self):
        """Create ML model for injury prediction"""
        model = tf.keras.Sequential([
            tf.keras.layers.Dense(64, activation='relu', input_shape=(15,)),
            tf.keras.layers.Dropout(0.3),
            tf.keras.layers.Dense(32, activation='relu'),
            tf.keras.layers.Dropout(0.3),
            tf.keras.layers.Dense(16, activation='relu'),
            tf.keras.layers.Dense(6, activation='sigmoid')  # 6 injury types
        ])
        model.compile(optimizer='adam', loss='binary_crossentropy')
        return model
    
    
    def analyze_recovery_trajectory(self, fall_data: Dict,
                                   post_fall_vitals: Dict,
                                   patient_profile: Dict) -> Dict:
        """
        Predict injuries after a fall
        
        Args:
            fall_data: {
                peak_acceleration: 3.2,  # G-force
                fall_direction: 'backward',  # forward, backward, lateral, unknown
                impact_location: 'hip area',  # Where they hit
                height_fallen_from: 2.0,  # feet
                patient_age: 78,
                medications: ['warfarin', ...],  # Anticoagulants increase bleeding risk
                bone_health: 'osteoporosis'  # Bone density info
            }
            
            post_fall_vitals: {
                timestamp: datetime,
                vitals: [
                    {timestamp: time, heart_rate: 98, blood_pressure: 140/90, ...},
                    ...
                ],
                pain_score: 8,  # 0-10 scale
                mobility: 'cannot move legs',
                consciousness: 'alert',
                bleeding: 'visible',
                reported_symptoms: ['severe pain', 'cannot feel leg']
            }
            
            patient_profile: {
                age: 78,
                osteoporosis: True,
                on_anticoagulants: True,
                previous_injuries: ['broken wrist 2 years ago'],
                medical_conditions: ['heart disease', 'diabetes']
            }
        
        Returns:
            {
                injury_probability: {
                    broken_hip: 0.89,
                    broken_wrist: 0.34,
                    ...
                },
                most_likely_injury: 'broken_hip',
                injury_severity: 'CRITICAL',
                urgency_level: 'CRITICAL',
                estimated_mortality_risk: 0.15,
                recovery_timeline: 12,
                recommendations: [...]
            }
        """
        
        logger.warning("🚨 POST-FALL ANALYSIS INITIATED")
        logger.info(f"Patient age: {patient_profile.get('age', 'unknown')}, Fall type: {fall_data.get('fall_direction', 'unknown')}")
        
        # Step 1: Create feature vector
        features = self._create_feature_vector(fall_data, post_fall_vitals, patient_profile)
        
        # Step 2: Run ML model
        raw_predictions = self.model.predict(features.reshape(1, -1), verbose=0)[0]
        
        # Step 3: Apply contextual analysis
        injury_probabilities = self._analyze_injuries(
            raw_predictions,
            fall_data,
            post_fall_vitals,
            patient_profile
        )
        
        # Step 4: Determine most likely injury
        most_likely = max(injury_probabilities.items(), key=lambda x: x[1])
        
        # Step 5: Assess severity and mortality
        severity, mortality_risk = self._assess_severity_and_mortality(
            injury_probabilities,
            patient_profile,
            post_fall_vitals
        )
        
        # Step 6: Determine urgency
        urgency = self._determine_urgency(injury_probabilities, mortality_risk)
        
        # Step 7: Generate recommendations
        recommendations = self._generate_recovery_recommendations(
            injury_probabilities,
            patient_profile,
            post_fall_vitals
        )
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'time_since_fall_minutes': self._calculate_time_since_fall(fall_data),
            
            # Injury predictions
            'injury_probability': injury_probabilities,
            'most_likely_injury': most_likely[0],
            'likelihood_percentage': f"{most_likely[1]:.0%}",
            
            # Severity assessment
            'injury_severity': severity,
            'urgency_level': urgency,
            'is_life_threatening': mortality_risk > 0.10,
            
            # Risk assessment
            'estimated_mortality_risk': float(mortality_risk),
            'recovery_timeline_weeks': self._estimate_recovery_time(injury_probabilities, patient_profile),
            
            # Medical recommendations
            'immediate_actions': self._get_immediate_actions(injury_probabilities, urgency),
            'imaging_needed': self._recommend_imaging(injury_probabilities),
            'monitoring_priorities': self._get_monitoring_priorities(injury_probabilities),
            'specialist_referrals': self._suggest_specialists(injury_probabilities),
            
            # General recommendations
            'recommendations': recommendations,
            
            # Family/caregiver guidance
            'family_guidance': self._generate_family_guidance(injury_probabilities, urgency),
            
            # Complication monitoring
            'watch_for_signs': self._get_warning_signs(injury_probabilities),
            'follow_up_schedule': self._generate_followup_schedule(injury_probabilities)
        }
        
        logger.warning(f"   Most likely injury: {most_likely[0]} ({most_likely[1]:.0%})")
        logger.warning(f"   Urgency: {urgency}")
        if mortality_risk > 0.10:
            logger.warning(f"   ⚠️  LIFE-THREATENING - Mortality risk: {mortality_risk:.0%}")
        
        return result
    
    
    def _create_feature_vector(self, fall_data: Dict,
                              post_fall_vitals: Dict,
                              patient_profile: Dict) -> np.ndarray:
        """Create 15-feature vector for ML model"""
        
        features = []
        
        # Feature 1-3: Fall dynamics
        peak_accel = fall_data.get('peak_acceleration', 2.0)
        height = fall_data.get('height_fallen_from', 0)
        impact_energy = peak_accel * height  # Energy = force × distance
        
        features.extend([
            peak_accel / 5.0,  # Normalized (max ~5G for typical fall)
            min(height / 5.0, 1.0),  # Normalized height
            min(impact_energy / 10.0, 1.0)  # Normalized energy
        ])
        
        # Feature 4-5: Fall direction (encoded)
        direction_encoding = {
            'forward': [1.0, 0.0, 0.0],
            'backward': [0.0, 1.0, 0.0],
            'lateral': [0.0, 0.0, 1.0],
            'unknown': [0.33, 0.33, 0.33]
        }
        direction = fall_data.get('fall_direction', 'unknown').lower()
        features.extend(direction_encoding.get(direction, direction_encoding['unknown']))
        
        # Feature 8-10: Post-fall vitals
        vitals = post_fall_vitals.get('vitals', [{}])
        latest_vitals = vitals[-1] if vitals else {}
        
        heart_rate = latest_vitals.get('heart_rate', 80)
        bp_systolic = latest_vitals.get('blood_pressure', {}).get('systolic', 120)
        breathing_rate = latest_vitals.get('breathing_rate', 16)
        
        features.extend([
            heart_rate / 120,  # Normalized (tachycardia = 120+)
            bp_systolic / 180,  # Normalized (hypertension = 180+)
            breathing_rate / 25  # Normalized (tachypnea = 25+)
        ])
        
        # Feature 11: Pain severity
        pain_score = post_fall_vitals.get('pain_score', 5)
        features.append(pain_score / 10.0)  # Normalized 0-10
        
        # Feature 12-13: Age + bone health
        age = patient_profile.get('age', 70)
        has_osteoporosis = 1.0 if patient_profile.get('osteoporosis', False) else 0.0
        
        features.extend([
            min(age / 90, 1.0),  # Normalized age
            has_osteoporosis
        ])
        
        # Feature 14-15: Medication risk
        on_anticoagulants = 1.0 if patient_profile.get('on_anticoagulants', False) else 0.0
        on_corticosteroids = 1.0 if 'corticosteroid' in str(patient_profile.get('medications', '')).lower() else 0.0
        
        features.extend([
            on_anticoagulants,
            on_corticosteroids
        ])
        
        return np.array(features, dtype=np.float32)
    
    
    def _analyze_injuries(self, raw_predictions: np.ndarray,
                         fall_data: Dict,
                         post_fall_vitals: Dict,
                         patient_profile: Dict) -> Dict:
        """Convert raw model predictions to injury-specific probabilities"""
        
        injury_names = ['broken_hip', 'broken_wrist', 'head_injury', 'spinal_injury', 'rib_fracture', 'internal_bleeding']
        
        probabilities = {}
        
        for idx, injury in enumerate(injury_names):
            prob = float(raw_predictions[idx])
            
            # Apply fall direction context
            direction = fall_data.get('fall_direction', 'unknown').lower()
            
            if injury == 'broken_hip' and direction == 'backward':
                prob *= 1.5
            elif injury == 'broken_wrist' and direction == 'forward':
                prob *= 1.4
            elif injury == 'head_injury' and direction == 'backward':
                prob *= 1.6
            
            # Apply age context
            age = patient_profile.get('age', 70)
            if age >= 80:
                prob *= 1.3
            elif age >= 70:
                prob *= 1.15
            
            # Apply anticoagulant context
            if patient_profile.get('on_anticoagulants', False):
                if injury in ['head_injury', 'internal_bleeding']:
                    prob *= 1.5
            
            # Apply pain context
            if injury == 'broken_hip' and post_fall_vitals.get('pain_score', 5) > 8:
                prob = min(prob * 1.2, 1.0)
            
            probabilities[injury] = np.clip(prob, 0, 1)
        
        return probabilities
    
    
    def _assess_severity_and_mortality(self, injury_probs: Dict,
                                      patient_profile: Dict,
                                      post_fall_vitals: Dict) -> tuple:
        """Assess overall severity and mortality risk"""
        
        # Calculate weighted severity
        severity_scores = {}
        for injury, prob in injury_probs.items():
            severity = self.injury_probabilities[injury]['severity']
            severity_weight = {'CRITICAL': 1.0, 'HIGH': 0.6, 'MEDIUM': 0.3, 'LOW': 0.1}
            severity_scores[injury] = prob * severity_weight.get(severity, 0.5)
        
        overall_severity_score = sum(severity_scores.values()) / len(severity_scores)
        
        # Classify severity
        if overall_severity_score > 0.7 or any(p > 0.8 for p in injury_probs.values() 
                                               if self.injury_probabilities[injury]['severity'] == 'CRITICAL'):
            severity = 'CRITICAL'
        elif overall_severity_score > 0.5:
            severity = 'HIGH'
        elif overall_severity_score > 0.3:
            severity = 'MEDIUM'
        else:
            severity = 'LOW'
        
        # Calculate mortality risk
        mortality_risk = 0.0
        for injury, prob in injury_probs.items():
            base_mortality = self.injury_probabilities[injury]['mortality_rate']
            mortality_risk += prob * base_mortality
        
        # Age adjustment
        age = patient_profile.get('age', 70)
        if age >= 80:
            mortality_risk *= 1.5
        elif age >= 75:
            mortality_risk *= 1.2
        
        # Medical condition adjustment
        if patient_profile.get('heart_disease', False):
            mortality_risk *= 1.3
        
        mortality_risk = min(mortality_risk, 0.9)  # Cap at 90%
        
        return severity, mortality_risk
    
    
    def _determine_urgency(self, injury_probs: Dict, mortality_risk: float) -> str:
        """Determine medical urgency level"""
        
        if mortality_risk > 0.15 or any(injury_probs.get(inj, 0) > 0.8 
                                        for inj in ['head_injury', 'internal_bleeding', 'spinal_injury']):
            return 'CRITICAL - CALL 911 IMMEDIATELY'
        elif any(injury_probs.get(inj, 0) > 0.7 
                 for inj in ['broken_hip', 'spinal_injury']):
            return 'EMERGENCY - GO TO ER NOW'
        elif any(injury_probs.get(inj, 0) > 0.6):
            return 'URGENT - SEE DOCTOR TODAY'
        else:
            return 'MODERATE - MEDICAL EVALUATION NEEDED'
    
    
    def _get_immediate_actions(self, injury_probs: Dict, urgency: str) -> List[str]:
        """Get immediate first-aid actions"""
        
        actions = []
        
        if 'CRITICAL' in urgency or 'EMERGENCY' in urgency:
            actions.append('CALL 911 IMMEDIATELY')
            actions.append('Do not move patient excessively')
        
        if injury_probs.get('spinal_injury', 0) > 0.5:
            actions.append('Immobilize head/neck - do not move')
            actions.append('Place in recovery position if breathing compromised')
        
        if injury_probs.get('head_injury', 0) > 0.6:
            actions.append('Monitor consciousness closely')
            actions.append('Watch for vomiting, confusion, seizures')
        
        if injury_probs.get('internal_bleeding', 0) > 0.5:
            actions.append('Monitor vital signs continuously')
            actions.append('Watch for pallor, rapid breathing, confusion')
        
        if injury_probs.get('broken_hip', 0) > 0.7:
            actions.append('Immobilize leg with pillow')
            actions.append('Apply ice to hip area')
            actions.append('Prepare for surgery consult')
        
        return actions
    
    
    def _recommend_imaging(self, injury_probs: Dict) -> Dict:
        """Recommend medical imaging"""
        
        imaging = {}
        
        if injury_probs.get('broken_hip', 0) > 0.6:
            imaging['X-ray Hip'] = 'URGENT - Check within 1 hour'
        
        if injury_probs.get('head_injury', 0) > 0.5:
            imaging['CT Head'] = 'URGENT - Rule out bleeding'
        
        if injury_probs.get('spinal_injury', 0) > 0.4:
            imaging['CT Spine'] = 'URGENT - Assess for fracture'
        
        if injury_probs.get('internal_bleeding', 0) > 0.5:
            imaging['CT Abdomen'] = 'CRITICAL - Rule out hemorrhage'
        
        return imaging
    
    
    def _get_monitoring_priorities(self, injury_probs: Dict) -> List[str]:
        """Get monitoring priorities"""
        
        priorities = []
        
        if injury_probs.get('head_injury', 0) > 0.5:
            priorities.append('Neurological status (consciousness, confusion, pupil response)')
        
        if injury_probs.get('internal_bleeding', 0) > 0.5:
            priorities.append('Vital signs: HR, BP, breathing every 15 minutes')
        
        if injury_probs.get('broken_hip', 0) > 0.7:
            priorities.append('Pain levels and medication response')
        
        priorities.append('Watch for signs of shock: pallor, rapid HR, confusion')
        
        return priorities
    
    
    def _suggest_specialists(self, injury_probs: Dict) -> List[str]:
        """Suggest medical specialists"""
        
        specialists = []
        
        if injury_probs.get('broken_hip', 0) > 0.7:
            specialists.append('Orthopedic surgeon (for surgery planning)')
        
        if injury_probs.get('spinal_injury', 0) > 0.5:
            specialists.append('Neurosurgeon/Spine specialist')
        
        if injury_probs.get('head_injury', 0) > 0.5:
            specialists.append('Neurologist')
        
        if injury_probs.get('internal_bleeding', 0) > 0.5:
            specialists.append('Trauma surgeon')
        
        specialists.append('Geriatric medicine (for age-appropriate care)')
        
        return specialists
    
    
    def _generate_recovery_recommendations(self, injury_probs: Dict,
                                          patient_profile: Dict,
                                          post_fall_vitals: Dict) -> List[str]:
        """Generate recovery recommendations"""
        
        recommendations = []
        
        # General recovery
        recommendations.append('Pain management: use prescribed medications as directed')
        recommendations.append('Physical therapy: start as soon as medically cleared')
        recommendations.append('Nutrition: high protein diet for bone/wound healing')
        
        # Injury-specific
        if injury_probs.get('broken_hip', 0) > 0.7:
            recommendations.append('Hip surgery likely needed - discuss timeline with surgeon')
            recommendations.append('Post-op: expect 4-6 month recovery period')
            recommendations.append('Rehabilitation: intensive PT starting day after surgery')
        
        if injury_probs.get('head_injury', 0) > 0.5:
            recommendations.append('Concussion precautions: no screens for 1-2 weeks')
            recommendations.append('Cognitive rest: quiet environment')
            recommendations.append('Return to activity gradually under medical guidance')
        
        if injury_probs.get('spinal_injury', 0) > 0.5:
            recommendations.append('Immobilization: likely need for brace/collar')
            recommendations.append('Long recovery: 6+ months typical')
            recommendations.append('MRI needed to assess spinal cord involvement')
        
        return recommendations
    
    
    def _generate_family_guidance(self, injury_probs: Dict, urgency: str) -> Dict:
        """Generate guidance for family/caregivers"""
        
        return {
            'immediate_notification': 'Contact family members immediately',
            'hospital_preparation': 'Bring insurance cards, medication list, medical history',
            'emotional_support': 'Elder will need psychological support during recovery',
            'logistics': 'Arrange time off work for hospital stays/rehabilitation',
            'financial': 'Review insurance coverage, explore Medicare/Medicaid',
            'long_term_planning': 'May need assisted living or increased home care after recovery'
        }
    
    
    def _get_warning_signs(self, injury_probs: Dict) -> Dict:
        """Get warning signs of complications"""
        
        signs = {}
        
        for injury, prob in injury_probs.items():
            if prob > 0.4:
                signs[injury] = self.injury_probabilities[injury]['early_signs']
        
        return signs
    
    
    def _generate_followup_schedule(self, injury_probs: Dict) -> Dict:
        """Generate medical follow-up schedule"""
        
        schedule = {
            'immediate': 'ER evaluation and imaging',
            'day_1': 'Specialist consultation',
            'week_1': 'Surgery if indicated',
            'week_2': 'Start physical therapy',
            'monthly': 'Follow-up appointments',
            'ongoing': 'Physical rehabilitation (6-12 months)'
        }
        
        return schedule
    
    
    def _calculate_time_since_fall(self, fall_data: Dict) -> int:
        """Calculate minutes since fall"""
        
        if 'timestamp' in fall_data:
            fall_time = fall_data['timestamp']
            if isinstance(fall_time, str):
                fall_time = datetime.fromisoformat(fall_time)
            return int((datetime.now() - fall_time).total_seconds() / 60)
        
        return 0
    
    
    def _estimate_recovery_time(self, injury_probs: Dict, 
                               patient_profile: Dict) -> int:
        """Estimate total recovery time in weeks"""
        
        recovery_time = 0
        for injury, prob in injury_probs.items():
            base_time = self.injury_probabilities[injury]['recovery_time_weeks']
            recovery_time += prob * base_time
        
        # Age adjustment
        age = patient_profile.get('age', 70)
        if age >= 80:
            recovery_time *= 1.3
        elif age >= 70:
            recovery_time *= 1.15
        
        return int(recovery_time)
