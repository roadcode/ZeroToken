"""
ZeroToken - Record once, automate forever.
A lightweight MCP for agent-driven browser automation.

Architecture:
- BrowserController: Enhanced browser control with detailed operation records
- TrajectoryRecorder: Records complete operation trajectory for AI analysis

Stability Modules:
- SmartSelector: Intelligent selector generation with fallbacks
- SmartWait: Advanced waiting strategies
- ErrorRecovery: Automatic error detection and recovery
"""

from .controller import BrowserController, PageState, OperationRecord
from .trajectory import Trajectory, TrajectoryRecorder

# Stability modules
from .selector import SmartSelector, SmartSelectorGenerator, SelectorType, SelectorCandidate
from .wait_strategy import SmartWait, WaitConfig, WaitCondition, WaitForResult, WaitChain
from .recovery import ErrorRecovery, ErrorType, RetryWrapper, RecoveryResult
# Adaptive element locating
from .adaptive import extract_fingerprint, relocate, similarity_score
from .adaptive_storage import AdaptiveStorage

__version__ = "0.4.0"
__all__ = [
    # Core modules
    "BrowserController",
    "PageState",
    "OperationRecord",
    "Trajectory",
    "TrajectoryRecorder",

    # Stability modules
    "SmartSelector",
    "SmartSelectorGenerator",
    "SelectorType",
    "SelectorCandidate",
    "SmartWait",
    "WaitConfig",
    "WaitCondition",
    "WaitForResult",
    "WaitChain",
    "ErrorRecovery",
    "ErrorType",
    "RetryWrapper",
    "RecoveryResult",
    "extract_fingerprint",
    "relocate",
    "similarity_score",
    "AdaptiveStorage",
]
