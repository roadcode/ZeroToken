"""
ScriptEngine: deterministic replay of scripts without LLM.
Resolves {{varname}} in params, iterates steps, calls BrowserController, writes SessionStore.
"""
import re
import uuid
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from zerotoken.controller import BrowserController
    from zerotoken.storage import SessionStore

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


def _effective_selectors(step: Dict[str, Any]) -> List[str]:
    """Build list of selectors to try: params.selector first, then selector_candidates (css type)."""
    params = step.get("params") or {}
    candidates = step.get("selector_candidates") or []
    out = []
    if params.get("selector"):
        out.append(params["selector"])
    for c in candidates:
        if isinstance(c, dict) and c.get("type") == "css" and c.get("value"):
            out.append(c["value"])
        elif isinstance(c, dict) and "value" in c and c.get("value") and c.get("value") not in out:
            out.append(c["value"])
    return out if out else (out if not params.get("selector") else [params["selector"]])


class ScriptEngine:
    """
    Deterministic script runner: resolves params, runs steps via BrowserController, writes SessionStore.
    """

    def __init__(self, vars_map: Optional[Dict[str, Any]] = None):
        self.vars_map = vars_map or {}

    def resolve_steps(self, steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return steps with params resolved from self.vars_map."""
        return resolve_params(steps, self.vars_map)

    async def run_script(
        self,
        script: Dict[str, Any],
        controller: "BrowserController",
        session_store: "SessionStore",
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute script steps in order; write each step to session_store.
        Skips browser_init and trajectory_start; runs browser_open, browser_click, browser_input, etc.
        Returns {"success": True, "session_id": "..."} or {"success": False, "error": "..."}.
        """
        task_id = script.get("task_id") or "unknown"
        steps = self.resolve_steps(script.get("steps") or [])
        sid = session_id or f"{task_id}_{uuid.uuid4().hex[:12]}"
        session_store.session_start(sid, task_id=task_id, session_type="replay")
        step_index = 0
        try:
            for step in steps:
                action = (step.get("action") or "").lower()
                params = step.get("params") or {}
                if action in ("browser_init", "trajectory_start"):
                    if action == "browser_init":
                        await controller.start(headless=params.get("headless", True))
                    continue
                if action == "browser_open":
                    url = params.get("url", "")
                    record = await controller.open(url, wait_until=params.get("wait_until", "networkidle"))
                    url_after = getattr(record.page_state, "url", url)
                    session_store.session_append(
                        sid,
                        step_index=step_index,
                        action="open",
                        selector=None,
                        url=url_after,
                        payload={"url": url},
                    )
                    step_index += 1
                    continue
                if action == "browser_click":
                    selectors = _effective_selectors(step)
                    record = None
                    last_err = None
                    for sel in selectors:
                        try:
                            record = await controller.click(sel, timeout=params.get("timeout"))
                            if record and record.result.get("success"):
                                break
                        except Exception as e:
                            last_err = e
                    if not record or not record.result.get("success"):
                        raise RuntimeError(last_err or "click failed")
                    url_after = getattr(record.page_state, "url", None)
                    session_store.session_append(
                        sid,
                        step_index=step_index,
                        action="click",
                        selector=sel,
                        url=url_after,
                        payload=params,
                    )
                    step_index += 1
                    continue
                if action == "browser_input":
                    selectors = _effective_selectors(step)
                    record = None
                    for sel in selectors:
                        try:
                            record = await controller.input(sel, params.get("text", ""), delay=params.get("delay", 50))
                            if record and record.result.get("success"):
                                break
                        except Exception:
                            continue
                    if not record or not record.result.get("success"):
                        raise RuntimeError("input failed")
                    url_after = getattr(record.page_state, "url", None)
                    session_store.session_append(
                        sid,
                        step_index=step_index,
                        action="input",
                        selector=sel,
                        url=url_after,
                        payload=params,
                    )
                    step_index += 1
                    continue
                # other actions: could extend later (get_text, wait_for, etc.)
            return {"success": True, "session_id": sid}
        except Exception as e:
            return {"success": False, "error": str(e), "session_id": sid}
