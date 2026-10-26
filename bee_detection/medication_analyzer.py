"""
Fall Guardian: Medication-Fall Risk Analysis
Analyze medications for fall risk and dangerous interactions
"""

import logging
from typing import Dict, List, Tuple
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MedicationFallRiskAnalyzer:
    """
    Analyze fall risk from medications
    Uses FDA drug interaction database
    """
    
    def __init__(self):
        # FDA medication fall risk database
        # Real data from https://www.fda.gov/drugs
        self.high_risk_drugs = {
            # CNS Depressants
            'Ambien': {
                'generic': 'Zolpidem',
                'category': 'Sedative-Hypnotic',
                'fall_multiplier': 3.2,
                'mechanism': 'CNS depression, dizziness, coordination loss',
                'risk_level': 'CRITICAL',
                'worst_time': 'First 4 hours after dose'
            },
            'Benzodiazepines': {
                'generic': 'Alprazolam, Lorazepam, Diazepam',
                'category': 'Anxiolytic',
                'fall_multiplier': 2.8,
                'mechanism': 'CNS depression, impaired balance',
                'risk_level': 'CRITICAL',
                'worst_time': 'First 2-3 hours after dose'
            },
            'Opioids': {
                'generic': 'Oxycodone, Hydrocodone, Morphine',
                'category': 'Analgesic',
                'fall_multiplier': 2.5,
                'mechanism': 'Dizziness, impaired coordination, drowsiness',
                'risk_level': 'HIGH',
                'worst_time': 'First 6 hours after dose'
            },
            
            # Blood Pressure Medications
            'Lisinopril': {
                'generic': 'ACE Inhibitor',
                'category': 'Antihypertensive',
                'fall_multiplier': 1.8,
                'mechanism': 'Orthostatic hypotension (sudden BP drop)',
                'risk_level': 'HIGH',
                'worst_time': 'First 2 hours after dose'
            },
            'Metoprolol': {
                'generic': 'Beta Blocker',
                'category': 'Antihypertensive',
                'fall_multiplier': 1.6,
                'mechanism': 'Dizziness, fatigue, reduced cardiac output',
                'risk_level': 'MEDIUM',
                'worst_time': 'First 1 hour after dose'
            },
            'Diltiazem': {
                'generic': 'Calcium Channel Blocker',
                'category': 'Antihypertensive',
                'fall_multiplier': 1.5,
                'mechanism': 'Dizziness, hypotension',
                'risk_level': 'MEDIUM',
                'worst_time': 'First 2-3 hours after dose'
            },
            
            # Anticholinergics (dementia risk)
            'Diphenhydramine': {
                'generic': 'Benadryl',
                'category': 'Antihistamine',
                'fall_multiplier': 2.2,
                'mechanism': 'Drowsiness, dizziness, anticholinergic effects',
                'risk_level': 'HIGH',
                'worst_time': 'First 3 hours after dose'
            },
            'Hydroxyzine': {
                'generic': 'Vistaril, Atarax',
                'category': 'Antihistamine',
                'fall_multiplier': 2.0,
                'mechanism': 'Sedation, dizziness',
                'risk_level': 'HIGH',
                'worst_time': 'First 2 hours after dose'
            },
            
            # Diabetes Medications
            'Insulin': {
                'generic': 'All types',
                'category': 'Glucose Reducer',
                'fall_multiplier': 1.5,
                'mechanism': 'Hypoglycemia → confusion, tremor, dizziness',
                'risk_level': 'HIGH',
                'worst_time': 'Peak effect (varies by type)'
            },
            'Metformin': {
                'generic': 'Glucophage',
                'category': 'Antidiabetic',
                'fall_multiplier': 1.2,
                'mechanism': 'Lactic acidosis (rare, but severe)',
                'risk_level': 'MEDIUM',
                'worst_time': 'Continuous'
            },
            
            # Antidepressants
            'Sertraline': {
                'generic': 'Zoloft',
                'category': 'SSRI',
                'fall_multiplier': 1.4,
                'mechanism': 'Dizziness, hyponatremia, serotonin syndrome',
                'risk_level': 'MEDIUM',
                'worst_time': 'First 2 weeks, dosage changes'
            },
            'Amitriptyline': {
                'generic': 'Elavil',
                'category': 'Tricyclic Antidepressant',
                'fall_multiplier': 2.0,
                'mechanism': 'Strong anticholinergic, orthostatic hypotension',
                'risk_level': 'HIGH',
                'worst_time': 'First 3 hours after dose'
            },
            
            # Anti-inflammatories
            'Ibuprofen': {
                'generic': 'Advil, Motrin',
                'category': 'NSAID',
                'fall_multiplier': 1.1,
                'mechanism': 'GI issues, dizziness',
                'risk_level': 'LOW',
                'worst_time': 'Continuous (especially if dehydrated)'
            }
        }
        
        # Known dangerous drug interactions
        self.dangerous_interactions = [
            {
                'drugs': ['Ambien', 'Benzodiazepines'],
                'interaction': 'Severe CNS depression',
                'risk_multiplier': 4.5,
                'severity': 'CRITICAL',
                'recommendation': 'Do not combine. Serious overdose risk.'
            },
            {
                'drugs': ['Opioids', 'Benzodiazepines'],
                'interaction': 'Respiratory depression risk',
                'risk_multiplier': 3.8,
                'severity': 'CRITICAL',
                'recommendation': 'Use extreme caution. FDA black box warning.'
            },
            {
                'drugs': ['Lisinopril', 'Metformin'],
                'interaction': 'Enhanced hypotension + lactic acidosis',
                'risk_multiplier': 2.0,
                'severity': 'HIGH',
                'recommendation': 'Monitor BP daily, check kidney function.'
            },
            {
                'drugs': ['Amitriptyline', 'Opioids'],
                'interaction': 'CNS depression, anticholinergic effects',
                'risk_multiplier': 3.2,
                'severity': 'HIGH',
                'recommendation': 'Minimize doses, monitor closely.'
            },
            {
                'drugs': ['Sertraline', 'Tramadol'],
                'interaction': 'Serotonin syndrome risk',
                'risk_multiplier': 2.5,
                'severity': 'HIGH',
                'recommendation': 'Monitor for tremor, agitation, confusion.'
            },
            {
                'drugs': ['NSAIDs', 'ACE Inhibitor'],
                'interaction': 'Kidney damage risk, hypotension',
                'risk_multiplier': 1.8,
                'severity': 'MEDIUM',
                'recommendation': 'Monitor kidney function, hydrate well.'
            }
        ]
        
        logger.info("Medication Fall Risk Analyzer initialized")
    
    
    def analyze_medications(self, medications: List[str], 
                          patient_profile: Dict) -> Dict:
        """
        Analyze fall risk from medications
        
        Args:
            medications: List of medication names ['Ambien', 'Lisinopril', ...]
            patient_profile: {age, kidney_function, weight, ...}
        
        Returns:
            {
                total_fall_risk_multiplier: 3.2,
                fall_risk_level: 'CRITICAL',
                high_risk_drugs: [...],
                dangerous_combinations: [...],
                medication_timing: {...},
                recommendations: [...]
            }
        """
        
        logger.info(f"Analyzing {len(medications)} medications for fall risk")
        logger.info(f"Medications: {', '.join(medications)}")
        
        # Step 1: Identify high-risk medications
        high_risk_meds = self._identify_high_risk_meds(medications)
        
        # Step 2: Check for dangerous interactions
        dangerous_combos = self._check_interactions(medications)
        
        # Step 3: Calculate cumulative risk
        total_multiplier = self._calculate_cumulative_risk(
            high_risk_meds, 
            dangerous_combos, 
            patient_profile
        )
        
        # Step 4: Determine medication timing
        timing_recommendations = self._optimize_medication_timing(
            medications, 
            high_risk_meds
        )
        
        # Step 5: Generate recommendations
        recommendations = self._generate_recommendations(
            high_risk_meds, 
            dangerous_combos, 
            patient_profile
        )
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'medications_analyzed': len(medications),
            'total_fall_risk_multiplier': total_multiplier,
            'fall_risk_level': self._classify_risk(total_multiplier),
            
            # Detailed breakdown
            'high_risk_medications': high_risk_meds,
            'dangerous_combinations': dangerous_combos,
            'baseline_risk': 1.0,
            'interaction_multiplier': len(dangerous_combos) * 0.5 + 1,
            
            # Safety recommendations
            'medication_timing': timing_recommendations,
            'recommendations': recommendations,
            
            # Intervention suggestions
            'interventions': self._suggest_interventions(high_risk_meds, dangerous_combos),
            
            # Doctor consultation
            'physician_alert': len(dangerous_combos) > 0 or total_multiplier > 2.0,
            'alert_reason': self._get_alert_reason(high_risk_meds, dangerous_combos, total_multiplier)
        }
        
        # Log alerts
        if result['physician_alert']:
            logger.warning(f"⚠️  MEDICATION ALERT: {result['alert_reason']}")
            logger.warning(f"   Fall risk multiplier: {total_multiplier:.1f}x normal")
        
        return result
    
    
    def _identify_high_risk_meds(self, medications: List[str]) -> List[Dict]:
        """Identify which medications increase fall risk"""
        
        high_risk = []
        
        for med in medications:
            # Exact match
            if med in self.high_risk_drugs:
                drug_info = self.high_risk_drugs[med].copy()
                drug_info['drug_name'] = med
                high_risk.append(drug_info)
            else:
                # Check for partial matches (e.g., "Lisinopril 10mg" matches "Lisinopril")
                for drug_name, drug_info in self.high_risk_drugs.items():
                    if drug_name.lower() in med.lower():
                        drug_info_copy = drug_info.copy()
                        drug_info_copy['drug_name'] = med
                        high_risk.append(drug_info_copy)
                        break
        
        # Sort by risk level
        risk_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        high_risk.sort(key=lambda x: risk_order.get(x['risk_level'], 99))
        
        return high_risk
    
    
    def _check_interactions(self, medications: List[str]) -> List[Dict]:
        """Check for dangerous drug interactions"""
        
        interactions = []
        med_lower = [m.lower() for m in medications]
        
        for interaction in self.dangerous_interactions:
            interaction_drugs = [d.lower() for d in interaction['drugs']]
            
            # Check if all drugs in interaction are present
            if all(any(med.find(drug) >= 0 for med in med_lower) 
                   for drug in interaction_drugs):
                interactions.append(interaction)
        
        return interactions
    
    
    def _calculate_cumulative_risk(self, high_risk_meds: List[Dict],
                                  dangerous_combos: List[Dict],
                                  patient_profile: Dict) -> float:
        """Calculate total fall risk multiplier"""
        
        multiplier = 1.0
        
        # Individual medication risk
        for med in high_risk_meds:
            multiplier *= med['fall_multiplier']
        
        # Interaction risk (non-multiplicative to avoid explosion)
        for combo in dangerous_combos:
            multiplier += (combo['risk_multiplier'] - 1.0)
        
        # Age adjustment (older = higher sensitivity)
        age = patient_profile.get('age', 70)
        if age >= 80:
            age_factor = 1.3
        elif age >= 70:
            age_factor = 1.15
        else:
            age_factor = 1.0
        
        multiplier *= age_factor
        
        # Kidney function adjustment (poor function = drug accumulation)
        kidney_function = patient_profile.get('kidney_function', 'normal')
        if kidney_function == 'poor':
            multiplier *= 1.5
        elif kidney_function == 'moderate':
            multiplier *= 1.2
        
        return round(multiplier, 1)
    
    
    def _optimize_medication_timing(self, medications: List[str],
                                   high_risk_meds: List[Dict]) -> Dict:
        """Generate optimal medication timing to minimize fall risk"""
        
        timing = {
            'breakfast': [],
            'lunch': [],
            'dinner': [],
            'bedtime': [],
            'notes': []
        }
        
        for med in high_risk_meds:
            drug_name = med['drug_name']
            worst_time = med['worst_time']
            
            # Sedatives → bedtime (but monitor night bathroom trips)
            if med['category'] in ['Sedative-Hypnotic', 'Anxiolytic']:
                timing['bedtime'].append(drug_name)
                if 'worst_time' in med:
                    timing['notes'].append(f"{drug_name}: {worst_time} - monitor for falls")
            
            # Blood pressure meds → morning (less likely to fall during day)
            elif med['category'] == 'Antihypertensive':
                timing['breakfast'].append(drug_name)
                timing['notes'].append(f"{drug_name}: Take sitting down, wait 2 min before standing")
            
            # Others → morning/lunch (avoid evening)
            else:
                timing['breakfast'].append(drug_name)
        
        # Non-high-risk medications
        for med in medications:
            if med not in [m['drug_name'] for m in high_risk_meds]:
                timing['breakfast'].append(med)
        
        return timing
    
    
    def _generate_recommendations(self, high_risk_meds: List[Dict],
                                 dangerous_combos: List[Dict],
                                 patient_profile: Dict) -> List[str]:
        """Generate physician recommendations"""
        
        recommendations = []
        
        # Critical alerts
        if any(med['risk_level'] == 'CRITICAL' for med in high_risk_meds):
            recommendations.append("CRITICAL: Review high-risk medications with physician immediately")
        
        if dangerous_combos:
            recommendations.append(f"ALERT: {len(dangerous_combos)} dangerous drug interaction(s) detected")
            for combo in dangerous_combos:
                recommendations.append(f"  - {combo['interaction']}: {combo['recommendation']}")
        
        # Individual medication suggestions
        for med in high_risk_meds:
            if med['risk_level'] in ['CRITICAL', 'HIGH']:
                recommendations.append(f"Consider alternative to {med['drug_name']} (less fall risk)")
        
        # Timing recommendations
        recommendations.append("Take all high-risk meds with meals or after food")
        recommendations.append("Never combine doses - stagger timing by 2+ hours")
        recommendations.append("Change positions slowly: sit 30 seconds before standing")
        
        # Monitoring recommendations
        recommendations.append("Monitor for: dizziness, confusion, unsteadiness")
        recommendations.append("Check blood pressure before taking antihypertensives")
        recommendations.append("Check blood glucose before taking insulin/metformin")
        
        return recommendations
    
    
    def _classify_risk(self, multiplier: float) -> str:
        """Classify fall risk level"""
        if multiplier > 3.0:
            return 'CRITICAL'
        elif multiplier > 2.0:
            return 'HIGH'
        elif multiplier > 1.5:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    
    def _get_alert_reason(self, high_risk_meds: List[Dict],
                         dangerous_combos: List[Dict],
                         multiplier: float) -> str:
        """Generate reason for physician alert"""
        
        reasons = []
        
        if len(high_risk_meds) >= 3:
            reasons.append(f"{len(high_risk_meds)} high-risk medications")
        elif any(med['risk_level'] == 'CRITICAL' for med in high_risk_meds):
            critical_meds = [m['drug_name'] for m in high_risk_meds if m['risk_level'] == 'CRITICAL']
            reasons.append(f"Critical risk medications: {', '.join(critical_meds)}")
        
        if dangerous_combos:
            reasons.append(f"{len(dangerous_combos)} dangerous interactions")
        
        if multiplier > 3.0:
            reasons.append(f"Fall risk {multiplier}x higher than baseline")
        
        return "; ".join(reasons) if reasons else "Medication review recommended"
    
    
    def _suggest_interventions(self, high_risk_meds: List[Dict],
                              dangerous_combos: List[Dict]) -> List[Dict]:
        """Suggest specific interventions"""
        
        interventions = []
        
        if high_risk_meds:
            interventions.append({
                'type': 'Medical',
                'action': 'Physician review of medication regimen',
                'urgency': 'High' if any(m['risk_level'] == 'CRITICAL' for m in high_risk_meds) else 'Medium'
            })
        
        if dangerous_combos:
            interventions.append({
                'type': 'Medical',
                'action': 'Evaluate replacing one interacting drug',
                'urgency': 'Critical'
            })
        
        interventions.extend([
            {'type': 'Environmental', 'action': 'Install grab bars and safety rails', 'urgency': 'High'},
            {'type': 'Behavioral', 'action': 'Gait training and balance exercises', 'urgency': 'Medium'},
            {'type': 'Monitoring', 'action': 'Daily vital signs monitoring', 'urgency': 'High'}
        ])
        
        return interventions
