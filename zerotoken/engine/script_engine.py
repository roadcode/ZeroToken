"""
ScriptEngine: deterministic replay of scripts without LLM.
Resolves {{varname}} in params, iterates steps (BrowserController integration in Task 3).
"""
import re
from typing import Any, Dict, List, Optional

PLACEHOLDER_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def resolve_params(steps: List[Dict[str, Any]], vars_map: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Replace {{varname}} in each step's params with vars_map[varname].
    If a placeholder has no key in vars_map, it is left unchanged.
    """
    result = []
    for step in steps:
        step_copy = {**step, "params": dict(step.get("params") or {})}
        params = step_copy["params"]
        for k, v in list(params.items()):
            if isinstance(v, str):
                for m in PLACEHOLDER_PATTERN.finditer(v):
                    name = m.group(1)
                    if name in vars_map:
                        v = v.replace(m.group(0), str(vars_map[name]))
                params[k] = v
        result.append(step_copy)
    return result


class ScriptEngine:
    """
    Skeleton: resolves params and iterates steps.
    Task 3 will wire in BrowserController and SessionStore.
    """

    def __init__(self, vars_map: Optional[Dict[str, Any]] = None):
        self.vars_map = vars_map or {}

    def resolve_steps(self, steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return steps with params resolved from self.vars_map."""
        return resolve_params(steps, self.vars_map)
