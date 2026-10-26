"""
Fall Guardian: Caregiver Burnout Detection
Monitor family caregiver stress and prevent burnout
Burnout = elder care fails. This prevents that.
"""

import logging
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CaregiverBurnoutDetector:
    """
    Monitor family caregiver wellbeing and predict burnout
    Burnout is a CRITICAL factor in elder fall outcomes
    """
    
    def __init__(self):
        self.burnout_thresholds = {
            'critical': 0.85,  # Immediate intervention needed
            'high': 0.70,      # Risk of burnout
            'moderate': 0.50,  # Monitor closely
            'low': 0.30        # Manageable
        }
        
        self.risk_factors = {
            'sleep_deprivation': {
                'weight': 0.20,
                'threshold': 5.0,  # < 5 hours = risk
                'description': 'Less than 5 hours sleep per night'
            },
            'social_isolation': {
                'weight': 0.15,
                'threshold': 3.0,  # < 3 social interactions per week = isolation
                'description': 'Limited social contact and support'
            },
            'work_overload': {
                'weight': 0.20,
                'threshold': 10,  # > 10 hours per day = overload
                'description': 'Excessive caregiving hours without breaks'
            },
            'response_time_degradation': {
                'weight': 0.15,
                'threshold': 2.0,  # > 2 hours to respond = degradation
                'description': 'Slower response to patient emergencies'
            },
            'emotional_distress': {
                'weight': 0.15,
                'threshold': 0.6,  # > 0.6 on distress scale = high
                'description': 'Reported high stress, anxiety, depression'
            },
            'lack_of_breaks': {
                'weight': 0.15,
                'threshold': 0,  # > 0 days without break = risk
                'description': 'No respite care or breaks'
            }
        }
        
        logger.info("Caregiver Burnout Detector initialized")
    
    
    def assess_burnout_risk(self, caregiver_data: Dict,
                           patient_needs_level: str = 'moderate') -> Dict:
        """
        Assess caregiver burnout risk
        
        Args:
            caregiver_data: {
                name: str,
                age: int,
                relationship: 'spouse', 'adult_child', 'other',
                
                # Sleep tracking
                avg_sleep_hours: float,
                sleep_quality_score: 0-1,
                night_wakings: int,
                
                # Social/isolation
                social_interactions_per_week: int,
                support_group_attendance: bool,
                family_support_available: bool,
                
                # Work burden
                caregiving_hours_per_day: float,
                days_without_break: int,
                respite_care_frequency: str,  # 'never', 'monthly', 'weekly', 'daily'
                
                # Responsiveness
                avg_response_time_hours: float,  # To patient alerts
                response_time_trend: float,  # Trending up (worse) or down (better)
                
                # Emotional state
                stress_score: 0-1,
                anxiety_score: 0-1,
                depression_score: 0-1,
                life_satisfaction: 0-1,
                
                # Duration
                years_as_caregiver: float,
                
                # Recent changes
                recent_patient_incidents: int,  # Falls, hospitalizations
                recent_medication_changes: int
            }
            patient_needs_level: 'minimal', 'moderate', 'high', 'critical'
        
        Returns:
            {
                burnout_score: 0.78,
                risk_level: 'HIGH',
                is_unsafe: True,
                risk_factors: [...],
                warning_signs: [...],
                recommendations: [...],
                interventions_needed: [...]
            }
        """
        
        logger.info(f"Assessing burnout risk for caregiver: {caregiver_data.get('name', 'Unknown')}")
        
        # Step 1: Analyze individual risk factors
        factor_scores = self._analyze_risk_factors(caregiver_data)
        
        # Step 2: Calculate weighted burnout score
        burnout_score = self._calculate_burnout_score(factor_scores)
        
        # Step 3: Apply patient needs adjustment
        adjusted_score = self._adjust_for_patient_needs(burnout_score, patient_needs_level)
        
        # Step 4: Identify warning signs
        warning_signs = self._identify_warning_signs(caregiver_data, factor_scores)
        
        # Step 5: Assess safety
        is_unsafe = adjusted_score > 0.75 or len(warning_signs) >= 4
        
        # Step 6: Generate interventions
        interventions = self._generate_interventions(
            adjusted_score, 
            factor_scores, 
            caregiver_data,
            is_unsafe
        )
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'caregiver_name': caregiver_data.get('name', 'Unknown'),
            'patient_needs_level': patient_needs_level,
            
            # Burnout assessment
            'raw_burnout_score': float(burnout_score),
            'patient_adjusted_score': float(adjusted_score),
            'burnout_score': float(adjusted_score),  # Use adjusted score
            'risk_level': self._classify_risk(adjusted_score),
            
            # Safety assessment
            'is_unsafe_to_continue': is_unsafe,
            'caregiver_stability': 'CRITICAL' if is_unsafe else 'MANAGEABLE',
            
            # Detailed breakdown
            'risk_factors': factor_scores,
            'primary_stressors': self._identify_primary_stressors(factor_scores),
            'warning_signs': warning_signs,
            
            # Recommendations
            'recommendations': self._generate_recommendations(adjusted_score, factor_scores),
            'immediate_interventions': interventions,
            
            # Support resources
            'resources': self._suggest_resources(caregiver_data),
            
            # Monitoring
            'follow_up_in_days': self._suggest_followup_timing(adjusted_score),
            'critical_watch': adjusted_score > self.burnout_thresholds['high']
        }
        
        # Log alerts
        if is_unsafe:
            logger.warning(f"⚠️  CAREGIVER BURNOUT ALERT: {caregiver_data.get('name', 'Unknown')}")
            logger.warning(f"   Burnout score: {adjusted_score:.1%} - CRITICAL")
            logger.warning(f"   Primary stressors: {', '.join(result['primary_stressors'][:3])}")
        elif adjusted_score > self.burnout_thresholds['high']:
            logger.warning(f"⚠️  HIGH CAREGIVER STRESS: {caregiver_data.get('name', 'Unknown')}")
            logger.warning(f"   Burnout score: {adjusted_score:.1%} - HIGH")
        
        return result
    
    
    def _analyze_risk_factors(self, caregiver_data: Dict) -> Dict:
        """Analyze individual burnout risk factors"""
        
        factor_scores = {}
        
        # Factor 1: Sleep Deprivation (CRITICAL)
        sleep_hours = caregiver_data.get('avg_sleep_hours', 7.0)
        sleep_quality = caregiver_data.get('sleep_quality_score', 0.7)
        
        if sleep_hours < 5:
            sleep_risk = 1.0
        elif sleep_hours < 6:
            sleep_risk = 0.8
        elif sleep_hours < 7:
            sleep_risk = 0.5
        else:
            sleep_risk = max(0.3, (7.5 - sleep_hours) * 0.2)
        
        sleep_risk *= sleep_quality  # Adjust by quality
        factor_scores['sleep'] = {
            'score': min(sleep_risk, 1.0),
            'hours': sleep_hours,
            'quality': sleep_quality,
            'night_wakings': caregiver_data.get('night_wakings', 0)
        }
        
        # Factor 2: Social Isolation
        social_interactions = caregiver_data.get('social_interactions_per_week', 3)
        has_support_group = caregiver_data.get('support_group_attendance', False)
        family_support = caregiver_data.get('family_support_available', False)
        
        isolation_risk = 1.0 - (social_interactions / 7)  # Normalize to 7 ideal interactions/week
        if has_support_group:
            isolation_risk *= 0.6
        if family_support:
            isolation_risk *= 0.7
        
        factor_scores['isolation'] = {
            'score': np.clip(isolation_risk, 0, 1),
            'interactions_per_week': social_interactions,
            'has_support_group': has_support_group,
            'family_support': family_support
        }
        
        # Factor 3: Work Overload
        hours_per_day = caregiver_data.get('caregiving_hours_per_day', 8)
        days_without_break = caregiver_data.get('days_without_break', 7)
        
        # Ideal: 8 hours/day, daily breaks
        work_risk = min(hours_per_day / 24, 1.0)  # Normalize
        
        # Penalty for no breaks
        if days_without_break >= 14:
            work_risk = min(work_risk + 0.4, 1.0)
        elif days_without_break >= 7:
            work_risk = min(work_risk + 0.2, 1.0)
        
        factor_scores['work_overload'] = {
            'score': work_risk,
            'hours_per_day': hours_per_day,
            'days_without_break': days_without_break,
            'respite_frequency': caregiver_data.get('respite_care_frequency', 'never')
        }
        
        # Factor 4: Response Time Degradation
        response_time = caregiver_data.get('avg_response_time_hours', 0.5)
        response_trend = caregiver_data.get('response_time_trend', 0.0)
        
        # Ideal response: < 0.5 hours (30 min)
        if response_time > 2.0:
            response_risk = 1.0
        elif response_time > 1.0:
            response_risk = 0.7
        elif response_time > 0.5:
            response_risk = 0.4
        else:
            response_risk = 0.1
        
        # Trending worse = higher risk
        if response_trend > 0:
            response_risk += 0.2
        
        factor_scores['response_time'] = {
            'score': np.clip(response_risk, 0, 1),
            'avg_hours': response_time,
            'trend': response_trend
        }
        
        # Factor 5: Emotional Distress
        stress = caregiver_data.get('stress_score', 0.5)
        anxiety = caregiver_data.get('anxiety_score', 0.5)
        depression = caregiver_data.get('depression_score', 0.3)
        satisfaction = caregiver_data.get('life_satisfaction', 0.5)
        
        emotional_distress = (stress + anxiety + depression) / 3
        emotional_distress *= (1.0 - satisfaction)  # Low satisfaction amplifies distress
        
        factor_scores['emotional'] = {
            'score': np.clip(emotional_distress, 0, 1),
            'stress': stress,
            'anxiety': anxiety,
            'depression': depression,
            'life_satisfaction': satisfaction
        }
        
        # Factor 6: Lack of Breaks
        respite_freq = caregiver_data.get('respite_care_frequency', 'never')
        
        respite_map = {
            'never': 1.0,
            'rarely': 0.8,
            'monthly': 0.5,
            'weekly': 0.2,
            'daily': 0.05
        }
        
        respite_risk = respite_map.get(respite_freq, 0.8)
        
        factor_scores['respite'] = {
            'score': respite_risk,
            'frequency': respite_freq,
            'recommendation': 'At least weekly respite care recommended'
        }
        
        # Factor 7: Duration (chronic stress)
        years = caregiver_data.get('years_as_caregiver', 1.0)
        
        # Burnout increases with years
        duration_risk = min(years / 10, 1.0) * 0.3  # Cap at 0.3x multiplier
        
        factor_scores['duration'] = {
            'score': duration_risk,
            'years': years,
            'note': 'Longer caregiving = higher baseline stress'
        }
        
        # Factor 8: Recent Stressors
        incidents = caregiver_data.get('recent_patient_incidents', 0)
        med_changes = caregiver_data.get('recent_medication_changes', 0)
        
        stressor_risk = (incidents * 0.2 + med_changes * 0.1) / 10
        
        factor_scores['recent_stressors'] = {
            'score': np.clip(stressor_risk, 0, 1),
            'incidents': incidents,
            'medication_changes': med_changes
        }
        
        return factor_scores
    
    
    def _calculate_burnout_score(self, factor_scores: Dict) -> float:
        """Calculate weighted burnout score"""
        
        weighted_score = 0.0
        total_weight = 0.0
        
        weights = {
            'sleep': 0.25,           # Sleep is critical
            'isolation': 0.15,
            'work_overload': 0.20,   # High weight
            'response_time': 0.10,
            'emotional': 0.15,
            'respite': 0.10,
            'duration': 0.03,
            'recent_stressors': 0.02
        }
        
        for factor, weight in weights.items():
            if factor in factor_scores:
                weighted_score += factor_scores[factor]['score'] * weight
                total_weight += weight
        
        return weighted_score / total_weight if total_weight > 0 else 0.5
    
    
    def _adjust_for_patient_needs(self, score: float, needs_level: str) -> float:
        """Adjust burnout score based on patient care demands"""
        
        multipliers = {
            'minimal': 0.8,      # Light caregiving = lower stress
            'moderate': 1.0,     # Standard
            'high': 1.4,         # Significant stress multiplier
            'critical': 1.8      # Very high stress
        }
        
        multiplier = multipliers.get(needs_level, 1.0)
        adjusted = score * multiplier
        
        return np.clip(adjusted, 0, 1)
    
    
    def _identify_warning_signs(self, caregiver_data: Dict, 
                               factor_scores: Dict) -> List[str]:
        """Identify specific warning signs of burnout"""
        
        signs = []
        
        # Sleep warning signs
        if caregiver_data.get('avg_sleep_hours', 7) < 5:
            signs.append('Severe sleep deprivation (< 5 hours/night)')
        
        if caregiver_data.get('night_wakings', 0) > 3:
            signs.append(f"Frequent night wakings ({caregiver_data['night_wakings']} per night)")
        
        # Isolation signs
        if caregiver_data.get('social_interactions_per_week', 7) < 2:
            signs.append('Extreme social isolation (< 2 interactions/week)')
        
        # Work overload signs
        if caregiver_data.get('caregiving_hours_per_day', 8) > 14:
            signs.append(f"Excessive caregiving hours ({caregiver_data['caregiving_hours_per_day']} hrs/day)")
        
        if caregiver_data.get('days_without_break', 0) > 14:
            signs.append(f"No break from caregiving ({caregiver_data['days_without_break']} days)")
        
        # Response time degradation
        if factor_scores.get('response_time', {}).get('trend', 0) > 0.1:
            signs.append('Declining responsiveness to patient needs')
        
        # Emotional signs
        if caregiver_data.get('stress_score', 0) > 0.8:
            signs.append('Reported high stress levels')
        
        if caregiver_data.get('depression_score', 0) > 0.6:
            signs.append('Symptoms of depression')
        
        if caregiver_data.get('anxiety_score', 0) > 0.7:
            signs.append('High anxiety symptoms')
        
        if caregiver_data.get('life_satisfaction', 1) < 0.3:
            signs.append('Low life satisfaction and hope')
        
        # Recent incidents
        if caregiver_data.get('recent_patient_incidents', 0) >= 2:
            signs.append(f"Multiple recent patient incidents ({caregiver_data['recent_patient_incidents']})")
        
        return signs
    
    
    def _identify_primary_stressors(self, factor_scores: Dict) -> List[str]:
        """Identify the main sources of stress"""
        
        stressors = []
        
        # Sort by score (highest = most stressful)
        sorted_factors = sorted(
            factor_scores.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )
        
        for factor, data in sorted_factors[:3]:  # Top 3 stressors
            if data['score'] > 0.3:
                factor_names = {
                    'sleep': 'Sleep Deprivation',
                    'work_overload': 'Excessive Workload',
                    'isolation': 'Social Isolation',
                    'emotional': 'Emotional Distress',
                    'response_time': 'Declining Responsiveness',
                    'respite': 'Lack of Respite Care',
                    'duration': 'Long-term Caregiving Stress',
                    'recent_stressors': 'Recent Crises'
                }
                
                stressors.append(factor_names.get(factor, factor))
        
        return stressors
    
    
    def _classify_risk(self, score: float) -> str:
        """Classify burnout risk level"""
        
        if score >= self.burnout_thresholds['critical']:
            return 'CRITICAL'
        elif score >= self.burnout_thresholds['high']:
            return 'HIGH'
        elif score >= self.burnout_thresholds['moderate']:
            return 'MODERATE'
        else:
            return 'LOW'
    
    
    def _generate_recommendations(self, score: float, 
                                 factor_scores: Dict) -> List[str]:
        """Generate recommendations to reduce burnout"""
        
        recommendations = []
        
        # Sleep
        if factor_scores.get('sleep', {}).get('score', 0) > 0.5:
            recommendations.append('Prioritize sleep: target 7-8 hours/night')
            recommendations.append('Consider sleep medication or therapy if needed')
        
        # Isolation
        if factor_scores.get('isolation', {}).get('score', 0) > 0.5:
            recommendations.append('Join caregiver support group (in-person or online)')
            recommendations.append('Schedule regular social activities')
            recommendations.append('Increase time with family/friends')
        
        # Work overload
        if factor_scores.get('work_overload', {}).get('score', 0) > 0.6:
            recommendations.append('Arrange respite care at least weekly')
            recommendations.append('Consider adult day programs for patient')
            recommendations.append('Hire in-home care help 2-3 days/week')
        
        # Emotional distress
        if factor_scores.get('emotional', {}).get('score', 0) > 0.6:
            recommendations.append('Seek counseling or therapy')
            recommendations.append('Consider antidepressant medication')
            recommendations.append('Practice stress-reduction: meditation, yoga')
        
        # General
        recommendations.extend([
            'Take regular breaks - even 15-30 min daily helps',
            'Attend caregiver health check-ups regularly',
            'Learn about available resources and benefits',
            'Consider family meeting to distribute care responsibilities'
        ])
        
        return recommendations
    
    
    def _generate_interventions(self, score: float, 
                               factor_scores: Dict,
                               caregiver_data: Dict,
                               is_unsafe: bool) -> List[Dict]:
        """Generate specific interventions"""
        
        interventions = []
        
        if is_unsafe:
            interventions.append({
                'urgency': 'CRITICAL',
                'type': 'Medical',
                'action': 'Physician evaluation for caregiver',
                'timeline': 'Within 24 hours'
            })
            
            interventions.append({
                'urgency': 'CRITICAL',
                'type': 'Care',
                'action': 'Arrange immediate respite care/hospice evaluation',
                'timeline': 'Within 24-48 hours'
            })
        
        if score > 0.7:
            interventions.append({
                'urgency': 'HIGH',
                'type': 'Support',
                'action': 'Enroll in formal caregiver program',
                'timeline': 'Within 1 week'
            })
            
            interventions.append({
                'urgency': 'HIGH',
                'type': 'Counseling',
                'action': 'Start individual therapy or counseling',
                'timeline': 'Within 1 week'
            })
        
        if factor_scores.get('work_overload', {}).get('score', 0) > 0.7:
            interventions.append({
                'urgency': 'HIGH',
                'type': 'Care',
                'action': 'Increase in-home care support',
                'timeline': 'Within 2 weeks'
            })
        
        if factor_scores.get('isolation', {}).get('score', 0) > 0.6:
            interventions.append({
                'urgency': 'MEDIUM',
                'type': 'Social',
                'action': 'Join caregiver support group',
                'timeline': 'Within 2 weeks'
            })
        
        return interventions
    
    
    def _suggest_resources(self, caregiver_data: Dict) -> Dict:
        """Suggest specific resources"""
        
        resources = {
            'support_groups': [
                'Caregiver Action Network',
                'Family Caregiver Alliance',
                'Alzheimer\'s Association (if dementia)',
                'Local community senior centers'
            ],
            'financial_assistance': [
                'Caregiver tax credits',
                'Long-term care insurance',
                'State Medicaid programs',
                'Senior care grants'
            ],
            'services': [
                'Adult day programs',
                'Respite care services',
                'In-home care aides',
                'Meal delivery services',
                'Housekeeping services'
            ],
            'mental_health': [
                'Therapist specializing in caregiver stress',
                'Support group therapy',
                'Meditation/mindfulness apps',
                'Counseling hotlines'
            ]
        }
        
        return resources
    
    
    def _suggest_followup_timing(self, score: float) -> int:
        """Suggest when to re-assess"""
        
        if score > 0.85:
            return 3  # 3 days
        elif score > 0.70:
            return 7  # 1 week
        elif score > 0.50:
            return 14  # 2 weeks
        else:
            return 30  # 1 month
