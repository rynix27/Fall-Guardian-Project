"""
Fall Guardian: Environmental Hazard Detection
Analyze Ring camera feed for home safety hazards
"""

import logging
from typing import Dict, List, Tuple
from datetime import datetime
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnvironmentalHazardDetector:
    """
    Analyze Ring camera feed for fall hazards
    Uses computer vision to detect unsafe conditions
    """
    
    def __init__(self):
        self.hazard_types = {
            'wet_floor': {
                'severity': 'HIGH',
                'description': 'Wet or slippery surface detected',
                'immediate_action': 'Dry floor immediately',
                'priority': 1
            },
            'clutter': {
                'severity': 'MEDIUM',
                'description': 'Items blocking pathways',
                'immediate_action': 'Clear pathways',
                'priority': 2
            },
            'poor_lighting': {
                'severity': 'HIGH',
                'description': 'Low light conditions',
                'immediate_action': 'Add lighting or increase brightness',
                'priority': 1
            },
            'stairs_no_rail': {
                'severity': 'CRITICAL',
                'description': 'Stairs without handrail',
                'immediate_action': 'Install safety rail immediately',
                'priority': 0
            },
            'uneven_floor': {
                'severity': 'MEDIUM',
                'description': 'Uneven surfaces or rugs',
                'immediate_action': 'Secure rugs, repair surfaces',
                'priority': 2
            },
            'poor_visibility': {
                'severity': 'MEDIUM',
                'description': 'Obstacles not clearly visible',
                'immediate_action': 'Add contrast markings',
                'priority': 2
            },
            'unstable_furniture': {
                'severity': 'MEDIUM',
                'description': 'Furniture used for support is unstable',
                'immediate_action': 'Replace or secure furniture',
                'priority': 2
            },
            'electrical_hazard': {
                'severity': 'HIGH',
                'description': 'Cords, cables blocking pathway',
                'immediate_action': 'Secure and hide cords',
                'priority': 1
            }
        }
        
        logger.info("Environmental Hazard Detector initialized")
    
    
    def analyze_environment(self, camera_feed_metadata: Dict,
                          room_type: str = 'living_room') -> Dict:
        """
        Analyze room for fall hazards
        
        Args:
            camera_feed_metadata: {
                brightness: 0-1 (0=dark, 1=very bright),
                motion_detected_areas: [(x, y, confidence), ...],
                detected_objects: ['rug', 'chair', 'cord', ...],
                floor_surface: 'tile', 'carpet', 'hardwood',
                moisture_detected: bool,
                clutter_score: 0-1
            }
            room_type: 'bathroom', 'kitchen', 'bedroom', 'hallway', etc.
        
        Returns:
            {
                overall_hazard_score: 0.68,
                hazard_level: 'MEDIUM',
                hazards: [...],
                room_risk_profile: {...},
                recommendations: [...]
            }
        """
        
        logger.info(f"Analyzing {room_type} for environmental hazards")
        
        hazards = []
        
        # Step 1: Detect wet floor (bathroom/kitchen specific)
        if room_type in ['bathroom', 'kitchen']:
            wet_score = self._detect_wet_surface(camera_feed_metadata)
            if wet_score > 0.6:
                hazards.append({
                    'type': 'wet_floor',
                    'confidence': wet_score,
                    'location': room_type,
                    'severity': 'HIGH',
                    'action': 'Dry floor immediately',
                    'risk_increase': 3.2
                })
        
        # Step 2: Detect clutter
        clutter_hazards = self._detect_clutter(camera_feed_metadata, room_type)
        hazards.extend(clutter_hazards)
        
        # Step 3: Detect poor lighting
        lighting_hazard = self._detect_poor_lighting(camera_feed_metadata)
        if lighting_hazard:
            hazards.append(lighting_hazard)
        
        # Step 4: Detect stairs hazards
        if room_type == 'stairway':
            stairs_hazards = self._detect_stair_hazards(camera_feed_metadata)
            hazards.extend(stairs_hazards)
        
        # Step 5: Detect uneven surfaces
        uneven_hazard = self._detect_uneven_surface(camera_feed_metadata)
        if uneven_hazard:
            hazards.append(uneven_hazard)
        
        # Step 6: Detect electrical hazards
        electrical_hazard = self._detect_electrical_hazard(camera_feed_metadata)
        if electrical_hazard:
            hazards.append(electrical_hazard)
        
        # Step 7: Detect unstable furniture
        furniture_hazard = self._detect_unstable_furniture(camera_feed_metadata)
        if furniture_hazard:
            hazards.append(furniture_hazard)
        
        # Sort by priority
        hazards.sort(key=lambda x: self.hazard_types[x['type']]['priority'])
        
        # Calculate overall hazard score
        overall_score = self._calculate_overall_hazard_score(hazards)
        
        # Generate room-specific risk profile
        room_risk = self._get_room_risk_profile(room_type, hazards)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(hazards, room_type)
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'room_type': room_type,
            'overall_hazard_score': overall_score,
            'hazard_level': 'CRITICAL' if overall_score > 0.8 else 'HIGH' if overall_score > 0.6 else 'MEDIUM' if overall_score > 0.4 else 'LOW',
            
            # Detailed hazard list
            'hazards_detected': hazards,
            'number_of_hazards': len(hazards),
            'critical_hazards': len([h for h in hazards if h['severity'] == 'CRITICAL']),
            
            # Room analysis
            'room_risk_profile': room_risk,
            'fall_risk_increase': sum(h.get('risk_increase', 1.0) for h in hazards) if hazards else 1.0,
            
            # Recommendations
            'recommendations': recommendations,
            'immediate_actions': self._get_immediate_actions(hazards),
            
            # Timeline
            'inspection_date': datetime.now().isoformat(),
            'next_inspection': self._suggest_inspection_timing(overall_score)
        }
        
        if overall_score > 0.6:
            logger.warning(f"⚠️  HIGH ENVIRONMENTAL HAZARD SCORE: {overall_score:.1%}")
            logger.warning(f"   Room: {room_type}, Hazards detected: {len(hazards)}")
        
        return result
    
    
    def _detect_wet_surface(self, metadata: Dict) -> float:
        """Detect wet floors via reflection, moisture sensors"""
        
        # Simulate detection via:
        # 1. Moisture sensor reading (if available)
        # 2. Reflective surface detection (wet = shiny)
        # 3. Recent water activity (bathroom/kitchen)
        
        wet_score = 0.0
        
        # Moisture detection
        if metadata.get('moisture_detected', False):
            wet_score += 0.7
        
        # Reflective surface detection (wet = high reflectance)
        floor_reflectance = metadata.get('floor_reflectance', 0.3)  # 0-1 scale
        if floor_reflectance > 0.5:  # Unnaturally high = wet
            wet_score += 0.4
        
        # Recent water activity detected
        if metadata.get('water_activity_detected', False):
            wet_score += 0.3
        
        return min(wet_score, 1.0)
    
    
    def _detect_clutter(self, metadata: Dict, room_type: str) -> List[Dict]:
        """Detect items blocking pathways"""
        
        hazards = []
        
        clutter_score = metadata.get('clutter_score', 0.0)  # 0-1
        
        # High clutter = pathway blocked
        if clutter_score > 0.6:
            hazards.append({
                'type': 'clutter',
                'confidence': clutter_score,
                'severity': 'HIGH' if clutter_score > 0.8 else 'MEDIUM',
                'location': room_type,
                'description': f'Clutter score: {clutter_score:.0%} - pathways partially blocked',
                'action': 'Clear pathways, create designated walking routes',
                'risk_increase': 1.5 if clutter_score > 0.8 else 1.2
            })
        
        # Specific objects detected
        detected_objects = metadata.get('detected_objects', [])
        
        # These are especially dangerous if in pathways
        dangerous_objects = ['cord', 'cable', 'rug', 'toy', 'box', 'pet']
        
        for obj in dangerous_objects:
            if obj in [o.lower() for o in detected_objects]:
                if obj == 'rug':
                    hazards.append({
                        'type': 'clutter',
                        'object': obj,
                        'confidence': 0.9,
                        'severity': 'MEDIUM',
                        'action': 'Secure rug with non-slip mat',
                        'risk_increase': 1.3
                    })
                elif obj in ['cord', 'cable']:
                    hazards.append({
                        'type': 'electrical_hazard',
                        'object': obj,
                        'confidence': 0.95,
                        'severity': 'HIGH',
                        'action': 'Tape down or hide cord',
                        'risk_increase': 1.8
                    })
        
        return hazards
    
    
    def _detect_poor_lighting(self, metadata: Dict) -> Dict or None:
        """Detect inadequate lighting"""
        
        brightness = metadata.get('brightness', 0.5)  # 0-1 scale
        
        # Target brightness: 0.4-0.8 (moderate light)
        if brightness < 0.3:
            return {
                'type': 'poor_lighting',
                'confidence': 1.0 - brightness,
                'severity': 'HIGH' if brightness < 0.2 else 'MEDIUM',
                'location': 'general',
                'description': f'Very low light level: {brightness:.0%}',
                'action': 'Add lights or increase brightness (target: 40-80%)',
                'risk_increase': 2.1 if brightness < 0.2 else 1.5
            }
        
        return None
    
    
    def _detect_stair_hazards(self, metadata: Dict) -> List[Dict]:
        """Detect stair-specific hazards"""
        
        hazards = []
        
        # Check for handrails
        has_handrail = metadata.get('handrail_detected', False)
        if not has_handrail:
            hazards.append({
                'type': 'stairs_no_rail',
                'confidence': 0.95,
                'severity': 'CRITICAL',
                'action': 'Install safety handrail IMMEDIATELY',
                'cost': '$200-400',
                'risk_increase': 3.5
            })
        
        # Check for step visibility
        step_contrast = metadata.get('step_edge_contrast', 0.3)  # 0-1
        if step_contrast < 0.3:
            hazards.append({
                'type': 'poor_visibility',
                'confidence': 0.7,
                'severity': 'HIGH',
                'action': 'Add yellow tape to stair edges for contrast',
                'cost': '$20',
                'risk_increase': 1.8
            })
        
        # Check for clutter on stairs
        stair_clutter = metadata.get('stair_clutter', False)
        if stair_clutter:
            hazards.append({
                'type': 'clutter',
                'location': 'stairs',
                'severity': 'CRITICAL',
                'action': 'Clear stairs immediately',
                'risk_increase': 4.0
            })
        
        return hazards
    
    
    def _detect_uneven_surface(self, metadata: Dict) -> Dict or None:
        """Detect uneven floors, loose carpets, etc."""
        
        floor_unevenness = metadata.get('floor_unevenness', 0.0)  # 0-1
        
        if floor_unevenness > 0.3:
            return {
                'type': 'uneven_floor',
                'confidence': floor_unevenness,
                'severity': 'HIGH' if floor_unevenness > 0.6 else 'MEDIUM',
                'description': f'Uneven surface score: {floor_unevenness:.0%}',
                'action': 'Repair floors, secure loose carpets/rugs',
                'risk_increase': 1.6 if floor_unevenness > 0.6 else 1.2
            }
        
        return None
    
    
    def _detect_electrical_hazard(self, metadata: Dict) -> Dict or None:
        """Detect cords, cables in pathways"""
        
        detected_objects = metadata.get('detected_objects', [])
        
        # Look for electrical hazards
        if any(obj.lower() in ['cord', 'cable', 'extension', 'wire'] 
               for obj in detected_objects):
            
            # Is it in a walkway? Check position
            object_positions = metadata.get('object_positions', {})
            
            in_pathway = object_positions.get('cord_in_pathway', False)
            
            if in_pathway:
                return {
                    'type': 'electrical_hazard',
                    'confidence': 0.9,
                    'severity': 'HIGH',
                    'action': 'Tape cord to wall or hide under furniture',
                    'risk_increase': 1.8
                }
        
        return None
    
    
    def _detect_unstable_furniture(self, metadata: Dict) -> Dict or None:
        """Detect furniture that might be used for support but is unstable"""
        
        detected_objects = metadata.get('detected_objects', [])
        
        # Objects commonly used for balance
        support_objects = ['chair', 'table', 'shelf', 'dresser']
        
        for obj in support_objects:
            if obj in [o.lower() for o in detected_objects]:
                stability_score = metadata.get(f'{obj}_stability', 0.8)  # 0-1
                
                if stability_score < 0.5:
                    return {
                        'type': 'unstable_furniture',
                        'object': obj,
                        'confidence': 1.0 - stability_score,
                        'severity': 'HIGH',
                        'action': f'Replace or secure {obj}',
                        'risk_increase': 1.7
                    }
        
        return None
    
    
    def _calculate_overall_hazard_score(self, hazards: List[Dict]) -> float:
        """Calculate composite hazard score 0-1"""
        
        if not hazards:
            return 0.0
        
        # Weighted scoring
        score = 0.0
        
        for hazard in hazards:
            severity_weight = {
                'CRITICAL': 1.0,
                'HIGH': 0.7,
                'MEDIUM': 0.4,
                'LOW': 0.1
            }
            
            hazard_weight = severity_weight.get(hazard['severity'], 0.5)
            confidence = hazard.get('confidence', 1.0)
            
            score += hazard_weight * confidence
        
        # Average and normalize
        score = min(score / len(hazards), 1.0)
        
        return score
    
    
    def _get_room_risk_profile(self, room_type: str, hazards: List[Dict]) -> Dict:
        """Get risk profile specific to room type"""
        
        room_profiles = {
            'bathroom': {
                'primary_risks': ['wet_floor', 'poor_lighting', 'uneven_surface'],
                'recommended_features': ['grab bars', 'non-slip mat', 'adequate lighting'],
                'baseline_risk': 1.5  # Bathrooms are inherently risky
            },
            'kitchen': {
                'primary_risks': ['wet_floor', 'clutter', 'electrical_hazard'],
                'recommended_features': ['clear walkways', 'good lighting', 'non-slip floor'],
                'baseline_risk': 1.3
            },
            'bedroom': {
                'primary_risks': ['poor_lighting', 'clutter', 'unstable_furniture'],
                'recommended_features': ['nightlight', 'clear pathways', 'stable furniture'],
                'baseline_risk': 1.2
            },
            'stairway': {
                'primary_risks': ['stairs_no_rail', 'poor_lighting', 'clutter'],
                'recommended_features': ['handrails', 'contrast edges', 'clear stairs'],
                'baseline_risk': 2.0  # Stairs are very risky
            },
            'hallway': {
                'primary_risks': ['poor_lighting', 'clutter', 'electrical_hazard'],
                'recommended_features': ['lighting', 'clear pathways', 'nightlight'],
                'baseline_risk': 1.1
            },
            'living_room': {
                'primary_risks': ['clutter', 'unstable_furniture', 'poor_lighting'],
                'recommended_features': ['clear pathways', 'stable furniture', 'lighting'],
                'baseline_risk': 1.1
            }
        }
        
        profile = room_profiles.get(room_type, room_profiles['living_room'])
        
        # Adjust based on detected hazards
        hazard_types_found = set(h['type'] for h in hazards)
        hazards_in_primary = len(hazard_types_found & set(profile['primary_risks']))
        
        adjusted_risk = profile['baseline_risk'] * (1 + 0.2 * hazards_in_primary)
        
        return {
            'room_type': room_type,
            'baseline_risk_multiplier': profile['baseline_risk'],
            'adjusted_risk_multiplier': adjusted_risk,
            'primary_risks': profile['primary_risks'],
            'recommended_features': profile['recommended_features'],
            'hazards_detected_in_primary': hazards_in_primary,
            'compliance_with_recommendations': (len(profile['recommended_features']) - hazards_in_primary) / len(profile['recommended_features'])
        }
    
    
    def _generate_recommendations(self, hazards: List[Dict], room_type: str) -> List[str]:
        """Generate actionable recommendations"""
        
        recommendations = []
        
        # Critical hazards first
        critical_hazards = [h for h in hazards if h['severity'] == 'CRITICAL']
        if critical_hazards:
            for hazard in critical_hazards:
                recommendations.append(f"URGENT: {hazard['action']}")
        
        # High-severity hazards
        high_hazards = [h for h in hazards if h['severity'] == 'HIGH']
        for hazard in high_hazards:
            recommendations.append(f"Priority: {hazard['action']}")
        
        # Medium hazards
        medium_hazards = [h for h in hazards if h['severity'] == 'MEDIUM']
        for hazard in medium_hazards[:3]:  # Limit to top 3
            recommendations.append(f"Consider: {hazard['action']}")
        
        # Room-specific recommendations
        room_recommendations = {
            'bathroom': [
                'Install grab bar next to toilet',
                'Use non-slip bath mat',
                'Keep area well-lit, especially at night'
            ],
            'kitchen': [
                'Keep walkways clear',
                'Secure throw rugs',
                'Organize low-use items out of reach'
            ],
            'bedroom': [
                'Keep nightlight on for bathroom trips',
                'Minimize bedside clutter',
                'Ensure stable furniture for support'
            ]
        }
        
        if room_type in room_recommendations:
            for rec in room_recommendations[room_type]:
                if rec not in recommendations:
                    recommendations.append(rec)
        
        return recommendations
    
    
    def _get_immediate_actions(self, hazards: List[Dict]) -> List[str]:
        """Get immediate actions needed"""
        
        actions = []
        
        for hazard in hazards:
            if hazard['severity'] in ['CRITICAL', 'HIGH']:
                actions.append(hazard['action'])
        
        return list(set(actions))  # Remove duplicates
    
    
    def _suggest_inspection_timing(self, hazard_score: float) -> str:
        """Suggest when to do next inspection"""
        
        if hazard_score > 0.8:
            return "Immediate (today)"
        elif hazard_score > 0.6:
            return "Within 1 week"
        elif hazard_score > 0.4:
            return "Within 2 weeks"
        else:
            return "Within 1 month"
