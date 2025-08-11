"""
Compatibility Analysis for AudioPortManager Integration with BMAR

This module analyzes potential compatibility issues and provides solutions
for integrating class_PyAudio.py AudioPortManager into the existing BMAR system.
"""

import logging
import sys
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from enum import Enum

class CompatibilityLevel(Enum):
    COMPATIBLE = "compatible"
    MINOR_ISSUES = "minor_issues"
    MAJOR_ISSUES = "major_issues"
    INCOMPATIBLE = "incompatible"

@dataclass
class CompatibilityIssue:
    """Represents a specific compatibility issue."""
    component: str
    issue_type: str
    severity: str
    description: str
    impact: str
    solution: str
    code_example: str = ""

class CompatibilityAnalyzer:
    """
    Analyzes compatibility between AudioPortManager and existing BMAR components.
    """
    
    def __init__(self):
        self.issues = []
        self.compatibility_level = CompatibilityLevel.COMPATIBLE
    
    def analyze_full_compatibility(self) -> Dict[str, Any]:
        """
        Perform comprehensive compatibility analysis.
        
        Returns:
            Dictionary containing analysis results
        """
        # Reset analysis
        self.issues.clear()
        
        # Analyze different aspects
        self._analyze_dependency_conflicts()
        self._analyze_api_differences()
        self._analyze_data_structure_compatibility()
        self._analyze_error_handling_differences()
        self._analyze_performance_implications()
        self._analyze_platform_specific_issues()
        self._analyze_configuration_conflicts()
        self._analyze_threading_compatibility()
        
        # Determine overall compatibility level
        self._determine_compatibility_level()
        
        return self._generate_compatibility_report()
    
    def _analyze_dependency_conflicts(self):
        """Analyze potential dependency conflicts."""
        
        # PyAudio installation complexity
        self.issues.append(CompatibilityIssue(
            component="Dependencies",
            issue_type="Installation",
            severity="Medium",
            description="PyAudio installation can be complex on some systems",
            impact="Users may experience installation failures, especially on Windows without proper build tools",
            solution="Provide multiple installation methods and fallback to sounddevice-only mode",
            code_example="""
# Installation fallback strategy
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logging.warning("PyAudio not available, using sounddevice-only mode")
"""
        ))
        
        # Version compatibility
        self.issues.append(CompatibilityIssue(
            component="Dependencies",
            issue_type="Version_Compatibility",
            severity="Low",
            description="Different PyAudio versions may have API differences",
            impact="Some features may not be available in older PyAudio versions",
            solution="Check PyAudio version and disable incompatible features gracefully",
            code_example="""
try:
    import pyaudio
    pa_version = pyaudio.__version__
    if tuple(map(int, pa_version.split('.'))) < (0, 2, 11):
        logging.warning("Old PyAudio version detected, some features disabled")
except:
    pass
"""
        ))
    
    def _analyze_api_differences(self):
        """Analyze API differences between sounddevice and PyAudio."""
        
        # Device indexing differences
        self.issues.append(CompatibilityIssue(
            component="Device_Management",
            issue_type="API_Differences", 
            severity="High",
            description="Device indices may differ between sounddevice and PyAudio",
            impact="Device selection may fail or select wrong device when switching between APIs",
            solution="Implement device mapping and verification",
            code_example="""
def map_devices_between_apis(sd_index):
    # Find corresponding PyAudio device by name/characteristics
    sd_device = sd.query_devices(sd_index)
    pa = pyaudio.PyAudio()
    
    for i in range(pa.get_device_count()):
        pa_device = pa.get_device_info_by_index(i)
        if devices_match(sd_device, pa_device):
            return i
    return None
"""
        ))
        
        # Format specification differences
        self.issues.append(CompatibilityIssue(
            component="Audio_Formats",
            issue_type="API_Differences",
            severity="Medium", 
            description="Different format specification methods (numpy dtypes vs PyAudio constants)",
            impact="Format conversion needed when switching between APIs",
            solution="Create format mapping layer",
            code_example="""
DTYPE_MAP = {
    'float32': pyaudio.paFloat32,
    'int32': pyaudio.paInt32,
    'int16': pyaudio.paInt16,
    'int8': pyaudio.paInt8
}

def get_pyaudio_format(numpy_dtype):
    return DTYPE_MAP.get(str(numpy_dtype), pyaudio.paFloat32)
"""
        ))
    
    def _analyze_data_structure_compatibility(self):
        """Analyze data structure compatibility issues."""
        
        # Device info structure differences
        self.issues.append(CompatibilityIssue(
            component="Data_Structures",
            issue_type="Structure_Differences",
            severity="Medium",
            description="Device info dictionaries have different key names and structures",
            impact="Code expecting specific key names may fail",
            solution="Create unified device info structure",
            code_example="""
def normalize_device_info(device_info, source_api):
    normalized = {
        'index': device_info.get('index', -1),
        'name': device_info.get('name', 'Unknown'),
        'input_channels': 0,
        'output_channels': 0,
        'default_sample_rate': 44100,
        'api': 'Unknown'
    }
    
    if source_api == 'sounddevice':
        normalized['input_channels'] = device_info.get('max_input_channels', 0)
        normalized['output_channels'] = device_info.get('max_output_channels', 0)
        normalized['default_sample_rate'] = device_info.get('default_samplerate', 44100)
    elif source_api == 'pyaudio':
        normalized['input_channels'] = device_info.get('maxInputChannels', 0)
        normalized['output_channels'] = device_info.get('maxOutputChannels', 0)
        normalized['default_sample_rate'] = device_info.get('defaultSampleRate', 44100)
    
    return normalized
"""
        ))
    
    def _analyze_error_handling_differences(self):
        """Analyze error handling compatibility."""
        
        # Different exception types
        self.issues.append(CompatibilityIssue(
            component="Error_Handling",
            issue_type="Exception_Types",
            severity="Medium",
            description="sounddevice and PyAudio raise different exception types",
            impact="Error handling code may miss PyAudio-specific exceptions",
            solution="Create unified exception handling wrapper",
            code_example="""
class AudioException(Exception):
    pass

def unified_audio_operation(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except sd.PortAudioError as e:
        raise AudioException(f"Sounddevice error: {e}")
    except Exception as e:
        if 'pyaudio' in str(type(e)).lower():
            raise AudioException(f"PyAudio error: {e}")
        raise
"""
        ))
    
    def _analyze_performance_implications(self):
        """Analyze performance differences."""
        
        # Initialization overhead
        self.issues.append(CompatibilityIssue(
            component="Performance",
            issue_type="Initialization_Overhead",
            severity="Low",
            description="PyAudio initialization adds overhead",
            impact="Slightly slower startup when PyAudio features are used",
            solution="Lazy initialization and caching",
            code_example="""
class LazyAudioManager:
    def __init__(self):
        self._pyaudio_manager = None
    
    @property
    def pyaudio_manager(self):
        if self._pyaudio_manager is None:
            self._pyaudio_manager = AudioPortManager()
        return self._pyaudio_manager
"""
        ))
        
        # Device enumeration performance
        self.issues.append(CompatibilityIssue(
            component="Performance", 
            issue_type="Device_Enumeration",
            severity="Low",
            description="Enhanced device discovery takes longer due to capability testing",
            impact="Device list refresh may be slower",
            solution="Background caching and progressive enhancement",
            code_example="""
# Cache device capabilities
device_cache = {}
cache_ttl = 60  # seconds

def get_device_capabilities_cached(device_index):
    now = time.time()
    if device_index in device_cache:
        if now - device_cache[device_index]['timestamp'] < cache_ttl:
            return device_cache[device_index]['data']
    
    capabilities = test_device_capabilities(device_index)
    device_cache[device_index] = {
        'data': capabilities,
        'timestamp': now
    }
    return capabilities
"""
        ))
    
    def _analyze_platform_specific_issues(self):
        """Analyze platform-specific compatibility issues."""
        
        # Windows-specific issues
        self.issues.append(CompatibilityIssue(
            component="Platform_Windows",
            issue_type="API_Availability",
            severity="Medium",
            description="WASAPI/DirectSound/MME availability may vary",
            impact="Hierarchical strategy may not work as expected on all Windows versions",
            solution="Dynamic API availability detection",
            code_example="""
def detect_available_apis():
    available_apis = []
    test_devices = sd.query_devices()
    
    for device in test_devices:
        try:
            api_info = sd.query_hostapis(device['hostapi'])
            api_name = api_info['name']
            if api_name not in available_apis:
                available_apis.append(api_name)
        except:
            pass
    
    return available_apis
"""
        ))
        
        # Linux/macOS compatibility
        self.issues.append(CompatibilityIssue(
            component="Platform_Unix",
            issue_type="API_Differences",
            severity="Low",
            description="AudioPortManager Windows-focused API hierarchy not relevant on Unix",
            impact="API fallback strategy needs platform-specific adaptation",
            solution="Platform-specific API priority lists",
            code_example="""
def get_platform_api_priority():
    if sys.platform.startswith('win'):
        return ['WASAPI', 'DirectSound', 'MME']
    elif sys.platform.startswith('darwin'):
        return ['Core Audio']
    else:  # Linux
        return ['ALSA', 'PulseAudio', 'JACK']
"""
        ))
    
    def _analyze_configuration_conflicts(self):
        """Analyze configuration compatibility."""
        
        # Configuration parameter differences
        self.issues.append(CompatibilityIssue(
            component="Configuration",
            issue_type="Parameter_Mapping",
            severity="Low",
            description="BMAR configuration parameters may not map directly to AudioPortManager",
            impact="Some BMAR settings may not be honored by enhanced manager",
            solution="Create configuration translation layer",
            code_example="""
def translate_bmar_config(app):
    audio_config = {
        'target_sample_rate': getattr(app, 'samplerate', 44100),
        'target_bit_depth': getattr(app, 'bit_depth', 16),
        'channels': getattr(app, 'channels', 2),
        'preferred_api': getattr(app, 'preferred_api', None),
        'device_name_filter': getattr(app, 'make_name', None)
    }
    return audio_config
"""
        ))
    
    def _analyze_threading_compatibility(self):
        """Analyze threading and concurrency issues."""
        
        # Thread safety concerns
        self.issues.append(CompatibilityIssue(
            component="Threading",
            issue_type="Thread_Safety",
            severity="Medium",
            description="PyAudio initialization may not be thread-safe",
            impact="Concurrent audio operations may fail or cause crashes",
            solution="Use thread locks for PyAudio operations",
            code_example="""
import threading

class ThreadSafeAudioManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._pyaudio_instance = None
    
    def get_pyaudio_instance(self):
        with self._lock:
            if self._pyaudio_instance is None:
                self._pyaudio_instance = pyaudio.PyAudio()
            return self._pyaudio_instance
"""
        ))
    
    def _determine_compatibility_level(self):
        """Determine overall compatibility level based on issues found."""
        high_severity_count = len([i for i in self.issues if i.severity == "High"])
        medium_severity_count = len([i for i in self.issues if i.severity == "Medium"])
        
        if high_severity_count > 2:
            self.compatibility_level = CompatibilityLevel.MAJOR_ISSUES
        elif high_severity_count > 0 or medium_severity_count > 3:
            self.compatibility_level = CompatibilityLevel.MINOR_ISSUES
        else:
            self.compatibility_level = CompatibilityLevel.COMPATIBLE
    
    def _generate_compatibility_report(self) -> Dict[str, Any]:
        """Generate comprehensive compatibility report."""
        
        # Group issues by component
        issues_by_component = {}
        for issue in self.issues:
            if issue.component not in issues_by_component:
                issues_by_component[issue.component] = []
            issues_by_component[issue.component].append(issue)
        
        # Count issues by severity
        severity_counts = {"High": 0, "Medium": 0, "Low": 0}
        for issue in self.issues:
            severity_counts[issue.severity] += 1
        
        return {
            'compatibility_level': self.compatibility_level.value,
            'total_issues': len(self.issues),
            'severity_breakdown': severity_counts,
            'issues_by_component': issues_by_component,
            'recommendations': self._generate_recommendations(),
            'migration_strategy': self._generate_migration_strategy()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate specific recommendations based on issues found."""
        recommendations = []
        
        high_severity_issues = [i for i in self.issues if i.severity == "High"]
        
        if high_severity_issues:
            recommendations.append(
                "HIGH PRIORITY: Address device indexing differences before deployment"
            )
        
        recommendations.extend([
            "Implement gradual migration strategy to minimize disruption",
            "Add comprehensive fallback mechanisms for PyAudio failures", 
            "Create unified configuration translation layer",
            "Implement thorough testing across target platforms",
            "Add performance monitoring to track impact of enhancements"
        ])
        
        if any(i.component == "Dependencies" for i in self.issues):
            recommendations.append(
                "Provide clear installation documentation for PyAudio dependencies"
            )
        
        return recommendations
    
    def _generate_migration_strategy(self) -> Dict[str, List[str]]:
        """Generate step-by-step migration strategy."""
        return {
            'phase_1_minimal_risk': [
                "Add AudioPortManager as optional dependency",
                "Create hybrid wrapper functions with fallback",
                "Test enhanced device discovery on non-critical systems",
                "Implement compatibility layer for data structures"
            ],
            'phase_2_gradual_adoption': [
                "Replace device enumeration with enhanced version",
                "Add hierarchical API selection as option",
                "Implement enhanced configuration testing",
                "Add performance monitoring and comparison"
            ],
            'phase_3_full_integration': [
                "Make enhanced manager the default",
                "Remove redundant old code paths",
                "Optimize performance based on monitoring data",
                "Add advanced features like capability caching"
            ],
            'rollback_plan': [
                "Keep original audio_devices.py functions available",
                "Add configuration flag to disable enhancements",
                "Implement quick fallback mechanism",
                "Document rollback procedures"
            ]
        }

def print_compatibility_report():
    """Print comprehensive compatibility analysis report."""
    analyzer = CompatibilityAnalyzer()
    report = analyzer.analyze_full_compatibility()
    
    print("=" * 80)
    print("BMAR AudioPortManager Compatibility Analysis Report")
    print("=" * 80)
    
    print(f"\nOverall Compatibility Level: {report['compatibility_level'].upper()}")
    print(f"Total Issues Found: {report['total_issues']}")
    
    print("\nSeverity Breakdown:")
    for severity, count in report['severity_breakdown'].items():
        print(f"  {severity}: {count}")
    
    print("\nIssues by Component:")
    for component, issues in report['issues_by_component'].items():
        print(f"\n{component}:")
        for issue in issues:
            print(f"  • {issue.issue_type} ({issue.severity}): {issue.description}")
            print(f"    Impact: {issue.impact}")
            print(f"    Solution: {issue.solution}")
            if issue.code_example:
                print(f"    Example: {issue.code_example[:100]}...")
    
    print("\nRecommendations:")
    for i, rec in enumerate(report['recommendations'], 1):
        print(f"  {i}. {rec}")
    
    print("\nMigration Strategy:")
    for phase, steps in report['migration_strategy'].items():
        print(f"\n{phase.replace('_', ' ').title()}:")
        for step in steps:
            print(f"  • {step}")
    
    print("\n" + "=" * 80)
    
    return report

if __name__ == "__main__":
    # Run compatibility analysis when module is executed directly
    print_compatibility_report()
