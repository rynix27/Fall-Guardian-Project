"""
Fall Guardian: Community Fall Heatmap
Aggregate anonymized fall data to identify danger zones and help cities prevent falls
"""

import logging
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CommunityFallHeatmap:
    """
    Analyze fall patterns at community/city level
    Identify high-risk areas and recommend preventive interventions
    """
    
    def __init__(self):
        # Simulated database of anonymized falls
        self.falls_database = []  # In production: DynamoDB
        
        self.location_types = {
            'street': {
                'primary_hazards': ['uneven sidewalk', 'poor lighting', 'weather'],
                'common_causes': ['tripping', 'slipping'],
                'interventions': ['repair sidewalk', 'add lighting', 'salt/sand in winter']
            },
            'home': {
                'primary_hazards': ['clutter', 'poor lighting', 'wet floor'],
                'common_causes': ['bathroom', 'stairs', 'bedroom'],
                'interventions': ['safety assessment', 'grab bars', 'lighting']
            },
            'transit': {
                'primary_hazards': ['moving vehicle', 'crowding', 'sudden stops'],
                'common_causes': ['bus stop', 'train', 'getting on/off'],
                'interventions': ['handrails', 'warning signals', 'staff assistance']
            },
            'park': {
                'primary_hazards': ['uneven paths', 'roots', 'wet grass'],
                'common_causes': ['tripping', 'slipping'],
                'interventions': ['path maintenance', 'benches for rest', 'lighting']
            },
            'store': {
                'primary_hazards': ['wet floors', 'clutter', 'crowding'],
                'common_causes': ['spill', 'blocked aisle'],
                'interventions': ['staff training', 'warning signs', 'cleanup protocol']
            }
        }
        
        logger.info("Community Fall Heatmap initialized")
    
    
    def analyze_community_falls(self, location: Dict,
                               radius_miles: float = 1.0,
                               time_period_days: int = 30) -> Dict:
        """
        Analyze fall patterns in a geographic area
        
        Args:
            location: {
                latitude: 40.7128,
                longitude: -74.0060,
                area_name: 'Manhattan, NY'
            }
            radius_miles: Search radius
            time_period_days: How far back to analyze
        
        Returns:
            {
                area_name: str,
                total_falls: int,
                fall_rate_per_1000_elderly: float,
                hotspots: [...],
                risk_patterns: [...],
                city_recommendations: [...]
            }
        """
        
        logger.info(f"Analyzing community falls for {location.get('area_name', 'Unknown')}")
        
        # Step 1: Query falls in area (simulated - in production: DynamoDB)
        falls_in_area = self._query_falls_by_location(
            location, radius_miles, time_period_days
        )
        
        logger.info(f"Found {len(falls_in_area)} falls in area")
        
        # Step 2: Identify hotspots (high-density areas)
        hotspots = self._identify_hotspots(falls_in_area)
        
        # Step 3: Analyze patterns
        patterns = self._analyze_fall_patterns(falls_in_area)
        
        # Step 4: Generate city-level recommendations
        city_recs = self._generate_city_recommendations(hotspots, patterns)
        
        # Step 5: Create heatmap grid
        heatmap = self._create_heatmap_grid(falls_in_area, location, radius_miles)
        
        # Step 6: Calculate statistics
        stats = self._calculate_statistics(falls_in_area)
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'analysis_period': f'{time_period_days} days',
            'area_name': location.get('area_name', 'Unknown'),
            'location': location,
            'radius_miles': radius_miles,
            
            # Statistics
            'total_falls_recorded': len(falls_in_area),
            'fall_density': stats['fall_density'],  # Falls per sq mile
            'average_fall_severity': stats['avg_severity'],  # 0-1 scale
            
            # Hotspots
            'hotspots': hotspots,
            'number_of_hotspots': len(hotspots),
            'critical_hotspots': len([h for h in hotspots if h['risk_level'] == 'CRITICAL']),
            
            # Patterns
            'risk_patterns': patterns,
            'seasonal_trends': self._analyze_seasonal_trends(falls_in_area),
            'time_of_day_patterns': self._analyze_time_patterns(falls_in_area),
            
            # Recommendations
            'city_level_recommendations': city_recs,
            'priority_interventions': self._get_priority_interventions(hotspots),
            
            # Public health impact
            'estimated_preventable_falls': self._estimate_preventable(falls_in_area, city_recs),
            'potential_cost_savings': self._calculate_potential_savings(falls_in_area, city_recs),
            
            # Heatmap visualization
            'heatmap_grid': heatmap,
            
            # Follow-up
            'recommended_action_items': self._generate_action_items(hotspots, patterns)
        }
        
        return result
    
    
    def _query_falls_by_location(self, location: Dict,
                                radius_miles: float,
                                days_back: int) -> List[Dict]:
        """Query falls from database within geographic area"""
        
        # Simulate database query
        # In production: query DynamoDB with geographic index
        
        # Example simulated data
        simulated_falls = [
            {
                'id': 'fall-001',
                'timestamp': datetime.now() - timedelta(days=5),
                'latitude': 40.7128,
                'longitude': -74.0060,
                'location_type': 'street',
                'location_name': 'Broadway & 42nd St',
                'cause': 'uneven sidewalk',
                'patient_age': 76,
                'severity': 0.7,
                'injury': 'broken_wrist',
                'weather': 'rainy'
            },
            {
                'id': 'fall-002',
                'timestamp': datetime.now() - timedelta(days=3),
                'latitude': 40.7120,
                'longitude': -74.0050,
                'location_type': 'park',
                'location_name': 'Times Square Park',
                'cause': 'wet path',
                'patient_age': 82,
                'severity': 0.8,
                'injury': 'broken_hip',
                'weather': 'rainy'
            },
            # ... more falls
        ]
        
        return simulated_falls
    
    
    def _identify_hotspots(self, falls: List[Dict]) -> List[Dict]:
        """Identify high-density fall areas (hotspots)"""
        
        if not falls:
            return []
        
        hotspots = []
        
        # Cluster falls by location
        location_clusters = defaultdict(list)
        
        for fall in falls:
            # Round to 0.01 degree precision (≈ 1 km)
            lat_bucket = round(fall['latitude'], 2)
            lon_bucket = round(fall['longitude'], 2)
            location_key = (lat_bucket, lon_bucket)
            
            location_clusters[location_key].append(fall)
        
        # Identify hotspots (clusters with 3+ falls)
        for location_key, location_falls in location_clusters.items():
            if len(location_falls) >= 3:
                lat, lon = location_key
                
                # Calculate risk metrics
                avg_severity = np.mean([f['severity'] for f in location_falls])
                avg_age = np.mean([f['patient_age'] for f in location_falls])
                
                # Identify common causes
                causes = [f.get('cause', 'unknown') for f in location_falls]
                most_common_cause = max(set(causes), key=causes.count)
                
                # Identify injuries
                injuries = [f.get('injury', 'unknown') for f in location_falls]
                
                # Determine risk level
                if len(location_falls) >= 5 and avg_severity > 0.7:
                    risk_level = 'CRITICAL'
                elif len(location_falls) >= 4 and avg_severity > 0.6:
                    risk_level = 'HIGH'
                elif len(location_falls) >= 3:
                    risk_level = 'MEDIUM'
                else:
                    risk_level = 'LOW'
                
                location_type = location_falls[0].get('location_type', 'unknown')
                location_name = location_falls[0].get('location_name', f'{lat},{lon}')
                
                hotspot = {
                    'location': location_name,
                    'coordinates': {'latitude': lat, 'longitude': lon},
                    'fall_count': len(location_falls),
                    'average_severity': avg_severity,
                    'average_patient_age': avg_age,
                    'risk_level': risk_level,
                    'location_type': location_type,
                    'common_cause': most_common_cause,
                    'injuries': list(set(injuries)),
                    'recommendation': self._generate_hotspot_recommendation(location_type, most_common_cause),
                    'estimated_cost_per_fall': 35000  # Average elder fall cost
                }
                
                hotspots.append(hotspot)
        
        # Sort by risk
        risk_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        hotspots.sort(key=lambda x: risk_order.get(x['risk_level'], 99))
        
        return hotspots
    
    
    def _analyze_fall_patterns(self, falls: List[Dict]) -> List[Dict]:
        """Identify fall patterns and risk factors"""
        
        patterns = []
        
        # Pattern 1: Weather effects
        weather_falls = defaultdict(list)
        for fall in falls:
            weather = fall.get('weather', 'unknown')
            weather_falls[weather].append(fall)
        
        for weather, weather_specific_falls in weather_falls.items():
            if len(weather_specific_falls) >= 2:
                patterns.append({
                    'type': 'Weather',
                    'factor': weather,
                    'fall_count': len(weather_specific_falls),
                    'percentage': len(weather_specific_falls) / len(falls),
                    'recommendation': f"Increase safety measures during {weather} weather"
                })
        
        # Pattern 2: Location type
        location_type_falls = defaultdict(list)
        for fall in falls:
            loc_type = fall.get('location_type', 'unknown')
            location_type_falls[loc_type].append(fall)
        
        for loc_type, type_specific_falls in location_type_falls.items():
            if len(type_specific_falls) >= 2:
                avg_severity = np.mean([f['severity'] for f in type_specific_falls])
                patterns.append({
                    'type': 'Location Type',
                    'factor': loc_type,
                    'fall_count': len(type_specific_falls),
                    'average_severity': avg_severity,
                    'recommendation': f"Focus prevention efforts on {loc_type} environments"
                })
        
        # Pattern 3: Age groups
        age_groups = {
            '65-75': [],
            '75-85': [],
            '85+': []
        }
        
        for fall in falls:
            age = fall.get('patient_age', 75)
            if age < 75:
                age_groups['65-75'].append(fall)
            elif age < 85:
                age_groups['75-85'].append(fall)
            else:
                age_groups['85+'].append(fall)
        
        for age_group, group_falls in age_groups.items():
            if len(group_falls) >= 2:
                patterns.append({
                    'type': 'Age Group',
                    'factor': age_group,
                    'fall_count': len(group_falls),
                    'average_severity': np.mean([f['severity'] for f in group_falls])
                })
        
        return patterns
    
    
    def _generate_city_recommendations(self, hotspots: List[Dict],
                                      patterns: List[Dict]) -> List[Dict]:
        """Generate city-level recommendations"""
        
        recommendations = []
        
        # Prioritize critical hotspots
        critical_hotspots = [h for h in hotspots if h['risk_level'] == 'CRITICAL']
        
        for hotspot in critical_hotspots:
            recommendations.append({
                'priority': 'CRITICAL',
                'location': hotspot['location'],
                'action': hotspot['recommendation'],
                'estimated_cost': self._estimate_intervention_cost(hotspot),
                'potential_lives_saved': self._estimate_lives_saved(hotspot),
                'timeline': 'Implement within 30 days'
            })
        
        # General recommendations
        recommendations.extend([
            {
                'priority': 'HIGH',
                'action': 'Increase elder safety awareness campaigns',
                'target': 'Public',
                'budget': '$50,000',
                'timeline': 'Ongoing'
            },
            {
                'priority': 'HIGH',
                'action': 'Improve sidewalk maintenance and lighting',
                'target': 'Public Works',
                'budget': '$500,000 - $2M',
                'timeline': '6-12 months'
            },
            {
                'priority': 'MEDIUM',
                'action': 'Install grab bars and safety railings at identified hotspots',
                'target': 'Public/Private locations',
                'budget': '$10,000 - $50,000 per location',
                'timeline': '2-4 months'
            },
            {
                'priority': 'MEDIUM',
                'action': 'Coordinate with healthcare system for fall prevention programs',
                'target': 'Health Department',
                'budget': '$100,000',
                'timeline': 'Ongoing'
            }
        ])
        
        return recommendations
    
    
    def _create_heatmap_grid(self, falls: List[Dict],
                            location: Dict,
                            radius_miles: float) -> List[List[float]]:
        """Create grid-based heatmap for visualization"""
        
        # Create 20x20 grid
        grid = [[0.0 for _ in range(20)] for _ in range(20)]
        
        # Normalize falls to grid
        if falls:
            min_lat = min(f['latitude'] for f in falls)
            max_lat = max(f['latitude'] for f in falls)
            min_lon = min(f['longitude'] for f in falls)
            max_lon = max(f['longitude'] for f in falls)
            
            for fall in falls:
                # Map coordinates to grid indices
                lat_idx = int(19 * (fall['latitude'] - min_lat) / (max_lat - min_lat + 0.001))
                lon_idx = int(19 * (fall['longitude'] - min_lon) / (max_lon - min_lon + 0.001))
                
                lat_idx = np.clip(lat_idx, 0, 19)
                lon_idx = np.clip(lon_idx, 0, 19)
                
                # Add severity to grid
                grid[lat_idx][lon_idx] += fall.get('severity', 0.5)
            
            # Normalize grid (0-1 scale)
            max_val = max(max(row) for row in grid) + 0.001
            grid = [[cell / max_val for cell in row] for row in grid]
        
        return grid
    
    
    def _calculate_statistics(self, falls: List[Dict]) -> Dict:
        """Calculate area statistics"""
        
        if not falls:
            return {
                'fall_density': 0,
                'avg_severity': 0
            }
        
        return {
            'fall_density': len(falls) / 3.14,  # Rough sq mile calculation
            'avg_severity': np.mean([f['severity'] for f in falls]),
            'avg_age': np.mean([f['patient_age'] for f in falls]),
            'critical_injuries': len([f for f in falls if f['severity'] > 0.7])
        }
    
    
    def _analyze_seasonal_trends(self, falls: List[Dict]) -> Dict:
        """Analyze seasonal patterns"""
        
        seasonal = {'winter': 0, 'spring': 0, 'summer': 0, 'fall': 0}
        
        for fall_record in falls:
            timestamp = fall_record['timestamp']
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            
            month = timestamp.month
            if month in [12, 1, 2]:
                seasonal['winter'] += 1
            elif month in [3, 4, 5]:
                seasonal['spring'] += 1
            elif month in [6, 7, 8]:
                seasonal['summer'] += 1
            else:
                seasonal['fall'] += 1
        
        return {
            'seasonal_distribution': seasonal,
            'trend': 'Winter highest (ice/cold)' if seasonal['winter'] > 0 else 'Even distribution'
        }
    
    
    def _analyze_time_patterns(self, falls: List[Dict]) -> Dict:
        """Analyze time-of-day patterns"""
        
        time_periods = {
            'morning (6am-12pm)': 0,
            'afternoon (12pm-6pm)': 0,
            'evening (6pm-10pm)': 0,
            'night (10pm-6am)': 0
        }
        
        for fall_record in falls:
            timestamp = fall_record['timestamp']
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            
            hour = timestamp.hour
            if 6 <= hour < 12:
                time_periods['morning (6am-12pm)'] += 1
            elif 12 <= hour < 18:
                time_periods['afternoon (12pm-6pm)'] += 1
            elif 18 <= hour < 22:
                time_periods['evening (6pm-10pm)'] += 1
            else:
                time_periods['night (10pm-6am)'] += 1
        
        return time_periods
    
    
    def _generate_hotspot_recommendation(self, location_type: str,
                                        cause: str) -> str:
        """Generate specific recommendation for hotspot"""
        
        if 'uneven' in cause.lower() or location_type == 'street':
            return 'Repair sidewalk, improve surface safety'
        elif 'wet' in cause.lower():
            return 'Improve drainage, add non-slip surfaces'
        elif 'lighting' in cause.lower():
            return 'Install/upgrade street lighting, motion-activated lights'
        elif 'stairs' in location_type.lower():
            return 'Add handrails, improve step visibility'
        else:
            return 'Conduct safety assessment and implement targeted interventions'
    
    
    def _get_priority_interventions(self, hotspots: List[Dict]) -> List[Dict]:
        """Get highest-priority interventions"""
        
        interventions = []
        
        for hotspot in hotspots[:5]:  # Top 5 hotspots
            interventions.append({
                'location': hotspot['location'],
                'current_risk': hotspot['risk_level'],
                'action': hotspot['recommendation'],
                'expected_reduction': '40-60% fewer falls',
                'cost_per_life_saved': hotspot['estimated_cost'] / max(1, hotspot['fall_count'])
            })
        
        return interventions
    
    
    def _estimate_preventable(self, falls: List[Dict],
                             recommendations: List[Dict]) -> int:
        """Estimate how many falls could be prevented"""
        
        # Rough estimate: 40% of falls preventable through environmental interventions
        preventable = int(len(falls) * 0.4)
        
        return preventable
    
    
    def _calculate_potential_savings(self, falls: List[Dict],
                                    recommendations: List[Dict]) -> Dict:
        """Calculate potential financial savings from prevention"""
        
        preventable = self._estimate_preventable(falls, recommendations)
        cost_per_fall = 35000  # Average elder fall cost (direct medical + lost productivity)
        
        total_cost = len(falls) * cost_per_fall
        preventable_cost = preventable * cost_per_fall
        
        # Estimate intervention cost
        intervention_cost = 500000  # Rough estimate for city-level interventions
        
        net_savings = preventable_cost - intervention_cost
        roi = (net_savings / intervention_cost) * 100 if intervention_cost > 0 else 0
        
        return {
            'total_annual_cost_of_falls': total_cost,
            'preventable_falls': preventable,
            'preventable_cost': preventable_cost,
            'estimated_intervention_cost': intervention_cost,
            'net_savings_year_1': max(0, net_savings),
            'return_on_investment': f'{roi:.0f}%'
        }
    
    
    def _estimate_intervention_cost(self, hotspot: Dict) -> str:
        """Estimate cost for intervention at hotspot"""
        
        cost = hotspot['fall_count'] * 5000  # ~$5k per fall for targeted intervention
        
        if cost > 50000:
            return f'${cost:,}'
        else:
            return f'${cost:,.0f}'
    
    
    def _estimate_lives_saved(self, hotspot: Dict) -> int:
        """Estimate lives saved by intervention"""
        
        # Rough estimate: 2-5% of falls result in death
        mortality_rate = 0.03
        
        return max(0, int(hotspot['fall_count'] * mortality_rate * 0.5))
    
    
    def _generate_action_items(self, hotspots: List[Dict],
                              patterns: List[Dict]) -> List[str]:
        """Generate action items for city/municipality"""
        
        actions = []
        
        # Critical actions
        if hotspots:
            actions.append(f"Safety audit at {hotspots[0]['location']} (CRITICAL - within 7 days)")
        
        # Quarterly actions
        actions.extend([
            'Publish quarterly fall safety report to public',
            'Share data with City Planning for infrastructure improvements',
            'Coordinate with hospitals on fall prevention programs',
            'Train first responders on fall response protocols'
        ])
        
        # Annual actions
        actions.extend([
            'Update community fall prevention strategy',
            'Allocate budget for identified hotspot improvements',
            'Conduct public awareness campaign',
            'Evaluate intervention effectiveness'
        ])
        
        return actions
