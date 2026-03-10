"""
Trajectory Recorder - Records complete operation trajectories.
Stores and manages operation records for replay and analysis.
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from pathlib import Path

from .controller import OperationRecord, BrowserController

if TYPE_CHECKING:
    from .storage import TrajectoryStore


class Trajectory:
    """Represents a complete operation trajectory."""

    def __init__(self, task_id: str, goal: str):
        self.task_id = task_id
        self.goal = goal
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.operations: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {
            "browser_info": None,
            "total_steps": 0,
            "successful_steps": 0,
            "failed_steps": 0
        }

    def add_operation(self, record: OperationRecord) -> None:
        """Add an operation record to trajectory."""
        self.operations.append(record.to_dict())
        self.metadata["total_steps"] = len(self.operations)
        if record.result.get("success"):
            self.metadata["successful_steps"] += 1
        else:
            self.metadata["failed_steps"] += 1

    def complete(self) -> None:
        """Mark trajectory as complete."""
        self.end_time = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.end_time else None,
            "metadata": self.metadata,
            "operations": self.operations
        }

    def to_ai_prompt_format(self) -> str:
        """
        Export trajectory as AI-friendly text format.
        Steps with fuzzy_point are marked with [需判断: {reason}].
        """
        lines = [f"Task Goal: {self.goal}", "", "Operation History:"]
        for op in self.operations:
            step = op.get("step", 0)
            action = op.get("action", "")
            params = op.get("params", {})
            param_str = ", ".join(f"{k}={repr(v)}" for k, v in params.items())
            line = f"[Step {step}] {action}({param_str})"
            fp = op.get("fuzzy_point")
            if fp and fp.get("requires_judgment"):
                reason = fp.get("reason", "需AI/人判断")
                hint = fp.get("hint", "")
                if hint:
                    line += f" [需判断: {reason}; 提示: {hint}]"
                else:
                    line += f" [需判断: {reason}]"
            lines.append(line)
        return "\n".join(lines)


class TrajectoryRecorder:
    """
    Records and manages operation trajectories.
    Integrates with BrowserController to capture all operations.
    """

    def __init__(
        self,
        trajectories_dir: str = "trajectories",
        auto_save: bool = True,
        trajectory_store: Optional["TrajectoryStore"] = None,
    ):
        self.trajectories_dir = Path(trajectories_dir)
        self.trajectories_dir.mkdir(parents=True, exist_ok=True)
        self.auto_save = auto_save
        self.trajectory_store = trajectory_store
        self._current_trajectory: Optional[Trajectory] = None
        self._controller: Optional[BrowserController] = None

    def bind_controller(self, controller: BrowserController) -> None:
        """Bind to a BrowserController for automatic recording."""
        self._controller = controller

    def start_trajectory(self, task_id: str, goal: str) -> Trajectory:
        """
        Start a new trajectory recording.

        Args:
            task_id: Unique task identifier
            goal: Natural language description of the task goal

        Returns:
            The new Trajectory object
        """
        if self._current_trajectory is not None and self._current_trajectory.task_id.startswith("_implicit_"):
            self.complete_trajectory()
        self._current_trajectory = Trajectory(task_id, goal)

        # Clear controller history if bound
        if self._controller:
            self._controller.clear_history()

        return self._current_trajectory

    def ensure_current_trajectory(self) -> None:
        """若无当前轨迹则创建隐式轨迹（不清理 controller history）。"""
        if self._current_trajectory is not None:
            return
        task_id = "_implicit_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        self._current_trajectory = Trajectory(task_id, "未命名会话")

    def record_operation(self, record: OperationRecord) -> None:
        """Record an operation to current trajectory."""
        if self._current_trajectory:
            self._current_trajectory.add_operation(record)

            if self.auto_save:
                self.save_trajectory()

    def get_current_trajectory(self) -> Optional[Trajectory]:
        """Get the current trajectory."""
        return self._current_trajectory

    def complete_trajectory(self) -> Trajectory:
        """Complete the current trajectory and return it."""
        if self._current_trajectory:
            self._current_trajectory.complete()

            # Sync with controller history
            if self._controller:
                for op_dict in self._controller.get_operation_history():
                    # Check if already recorded
                    already_recorded = any(
                        op['step'] == op_dict['step']
                        for op in self._current_trajectory.operations
                    )
                    if not already_recorded:
                        # Create OperationRecord from dict
                        record = self._dict_to_record(op_dict)
                        self._current_trajectory.add_operation(record)

            if self.auto_save:
                self.save_trajectory()

        trajectory = self._current_trajectory
        self._current_trajectory = None
        return trajectory

    def _dict_to_record(self, data: Dict[str, Any]) -> OperationRecord:
        """Convert dictionary back to OperationRecord."""
        from .controller import PageState

        page_state = PageState(
            url=data['page_state']['url'],
            title=data['page_state']['title']
        )

        return OperationRecord(
            step=data['step'],
            action=data['action'],
            params=data['params'],
            result=data['result'],
            page_state=page_state,
            screenshot=data.get('screenshot'),
            error=data.get('error'),
            fuzzy_point=data.get('fuzzy_point'),
            selector_candidates=data.get('selector_candidates'),
        )

    def save_trajectory(self, trajectory: Optional[Trajectory] = None) -> str:
        """
        Save trajectory to file and optionally to TrajectoryStore (DB).

        Returns:
            File path where trajectory was saved
        """
        traj = trajectory or self._current_trajectory
        if not traj:
            raise ValueError("No trajectory to save")

        filename = f"{traj.task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.trajectories_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(traj.to_dict(), f, indent=2, ensure_ascii=False)

        if self.trajectory_store:
            self.trajectory_store.trajectory_save(
                task_id=traj.task_id,
                goal=traj.goal,
                operations=traj.operations,
                metadata=traj.metadata,
            )

        return str(filepath)

    def load_trajectory(self, filepath: str) -> Trajectory:
        """Load trajectory from file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        trajectory = Trajectory(data['task_id'], data['goal'])
        trajectory.start_time = datetime.fromisoformat(data['start_time'])
        if data.get('end_time'):
            trajectory.end_time = datetime.fromisoformat(data['end_time'])
        trajectory.metadata = data['metadata']

        for op_data in data['operations']:
            record = self._dict_to_record(op_data)
            trajectory.operations.append(record.to_dict())

        return trajectory

    def load_trajectory_by_task_id(self, task_id: str) -> Optional[Trajectory]:
        """Load the most recently saved trajectory for the given task_id. Returns None if none found."""
        files = sorted(
            self.trajectories_dir.glob(f"{task_id}_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        if not files:
            return None
        return self.load_trajectory(str(files[0]))

    def list_trajectories(self) -> List[Dict[str, Any]]:
        """List all saved trajectories."""
        trajectories = []
        for f in self.trajectories_dir.glob("*.json"):
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                trajectories.append({
                    "task_id": data['task_id'],
                    "goal": data['goal'],
                    "file": str(f),
                    "saved_at": f.stat().st_mtime,
                    "operations_count": len(data.get("operations", []))
                })
        return sorted(trajectories, key=lambda x: x['saved_at'], reverse=True)

    def delete_trajectory(self, task_id: str) -> bool:
        """Delete a trajectory by task_id."""
        deleted = False
        for f in self.trajectories_dir.glob(f"{task_id}_*"):
            f.unlink()
            deleted = True
        return deleted
