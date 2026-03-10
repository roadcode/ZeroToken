"""
Storage interfaces for ZeroToken: scripts, trajectories, sessions.
MCP and Engine depend on these abstractions; implementation is SQLite by default.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

_RUNTIME_UNSET = object()


class ScriptStore(ABC):
    """Abstract script storage."""

    @abstractmethod
    def script_save(
        self,
        task_id: str,
        *,
        goal: str,
        steps: List[Dict[str, Any]],
        params_schema: Optional[Dict[str, Any]] = None,
        source_trajectory_id: Optional[int] = None,
    ) -> None:
        """Save or overwrite script by task_id."""
        ...

    @abstractmethod
    def script_load(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Load script by task_id. Returns None if not found."""
        ...

    @abstractmethod
    def script_list(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List scripts (task_id, goal, created_at)."""
        ...

    @abstractmethod
    def script_delete(self, task_id: str) -> bool:
        """Delete script. Returns True if deleted."""
        ...


class TrajectoryStore(ABC):
    """Abstract trajectory storage."""

    @abstractmethod
    def trajectory_save(
        self,
        *,
        task_id: str,
        goal: str,
        operations: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Save trajectory. Returns id."""
        ...

    @abstractmethod
    def trajectory_load(self, trajectory_id: int) -> Optional[Dict[str, Any]]:
        """Load trajectory by id. Returns None if not found."""
        ...

    @abstractmethod
    def trajectory_list(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List trajectories (id, task_id, goal, created_at)."""
        ...

    @abstractmethod
    def trajectory_delete(self, trajectory_id: int) -> bool:
        """Delete trajectory. Returns True if deleted."""
        ...


class SessionStore(ABC):
    """Abstract session/trace storage."""

    @abstractmethod
    def session_start(
        self,
        session_id: str,
        *,
        task_id: Optional[str] = None,
        session_type: str = "replay",
    ) -> None:
        """Start a new session (create placeholder or first row)."""
        ...

    @abstractmethod
    def session_append(
        self,
        session_id: str,
        *,
        step_index: int,
        action: str,
        selector: Optional[str] = None,
        url: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append a step to the session."""
        ...

    @abstractmethod
    def session_get(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all steps for session_id, ordered by step_index."""
        ...

    @abstractmethod
    def session_list(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List sessions (session_id, task_id, type, created_at)."""
        ...


class DFUStore(ABC):
    """Abstract DFU (Dynamic Fuzzy Unit) storage."""

    @abstractmethod
    def dfu_save(
        self,
        dfu_id: str,
        *,
        name: str,
        description: str = "",
        triggers: List[Dict[str, Any]],
        prompt: str = "",
        allowed_resolutions: Optional[List[str]] = None,
    ) -> None:
        """Save or overwrite a DFU by dfu_id."""
        ...

    @abstractmethod
    def dfu_load(self, dfu_id: str) -> Optional[Dict[str, Any]]:
        """Load DFU by dfu_id. Returns None if not found."""
        ...

    @abstractmethod
    def dfu_list(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List DFUs (dfu_id, name, updated_at)."""
        ...

    @abstractmethod
    def dfu_delete(self, dfu_id: str) -> bool:
        """Delete DFU. Returns True if deleted."""
        ...


class SessionRuntimeStore(ABC):
    """Abstract runtime state store for pause/resume."""

    @abstractmethod
    def runtime_init(
        self,
        session_id: str,
        *,
        task_id: Optional[str],
        cursor_step_index: int,
        status: str,
        pause_event: Optional[Dict[str, Any]] = None,
        vars: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize runtime state for a session."""
        ...

    @abstractmethod
    def runtime_get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get runtime state for a session. Returns None if missing."""
        ...

    @abstractmethod
    def runtime_update(
        self,
        session_id: str,
        *,
        cursor_step_index: Optional[int] = None,
        status: Optional[str] = None,
        pause_event: Any = _RUNTIME_UNSET,
        vars: Any = _RUNTIME_UNSET,
    ) -> None:
        """Update runtime state fields for a session."""
        ...
