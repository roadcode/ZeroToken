"""
ScriptEngine: deterministic replay of scripts without LLM.
Resolves {{varname}} in params, iterates steps, calls BrowserController, writes SessionStore.
"""
import re
import uuid
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from zerotoken.controller import BrowserController
    from zerotoken.storage import SessionStore, DFUStore, SessionRuntimeStore

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


def _trigger_matches_step(trigger: Dict[str, Any], *, action: str, selector: Optional[str]) -> bool:
    """Exact-match trigger evaluation (MVP): action_is / selector_is."""
    if not isinstance(trigger, dict):
        return False
    if "action_is" in trigger and trigger.get("action_is") != action:
        return False
    if "selector_is" in trigger and trigger.get("selector_is") != (selector or ""):
        return False
    return True


def _match_dfus_for_step(
    dfus: List[Dict[str, Any]],
    *,
    action: str,
    selector: Optional[str],
) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    Return (dfu, matched_trigger) if any DFU trigger matches this step.
    `dfus` is a list of dfu dicts with keys: dfu_id, triggers (list[dict]), prompt, allowed_resolutions.
    """
    for dfu in dfus:
        triggers = dfu.get("triggers") or []
        for trig in triggers:
            if _trigger_matches_step(trig, action=action, selector=selector):
                return dfu, trig
    return None


class ScriptEngine:
    """
    Deterministic script runner: resolves params, runs steps via BrowserController, writes SessionStore.
    """

    def __init__(self, vars_map: Optional[Dict[str, Any]] = None):
        self.vars_map = vars_map or {}

    def resolve_steps(self, steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return steps with params resolved from self.vars_map."""
        return resolve_params(steps, self.vars_map)

    def _load_all_dfus(self, dfu_store: "DFUStore", limit: int = 200) -> List[Dict[str, Any]]:
        items = []
        for it in (dfu_store.dfu_list(limit=limit) or []):
            dfu_id = it.get("dfu_id")
            if not dfu_id:
                continue
            full = dfu_store.dfu_load(dfu_id)
            if full:
                items.append(full)
        return items

    async def run_script_start(
        self,
        script: Dict[str, Any],
        controller: "BrowserController",
        store: Any,
        *,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Start-mode entrypoint: create session + runtime, then run from cursor 0.

        Returns one of:
        - {"success": True, "status": "success", "session_id": "..."}
        - {"success": False, "status": "paused", "session_id": "...", "pause_event": {...}}
        - {"success": False, "status": "failed", "session_id": "...", "error": {...}}
        """
        task_id = script.get("task_id") or "unknown"
        sid = session_id or f"{task_id}_{uuid.uuid4().hex[:12]}"
        steps = list(script.get("steps") or [])
        store.session_start(sid, task_id=task_id, session_type="replay")
        store.runtime_init(
            sid,
            task_id=task_id,
            cursor_step_index=0,
            status="running",
            pause_event=None,
            vars=dict(self.vars_map or {}),
        )
        dfus = self._load_all_dfus(store)
        return await self._run_from_cursor(
            sid,
            task_id,
            steps,
            controller,
            store,
            dfus,
            start_index=0,
            step_patch=None,
            vars_env=dict(self.vars_map or {}),
        )

    async def run_script_resume(
        self,
        session_id: str,
        resolution: Dict[str, Any],
        controller: "BrowserController",
        store: Any,
    ) -> Dict[str, Any]:
        """
        Resume-mode entrypoint: validate runtime is paused, apply resolution, then continue.
        """
        rt = store.runtime_get(session_id)
        if rt is None:
            return {
                "success": False,
                "status": "failed",
                "session_id": session_id,
                "error": {"code": "RUNTIME_NOT_FOUND", "message": "runtime state not found"},
            }
        if rt.get("status") != "paused":
            return {
                "success": False,
                "status": "failed",
                "session_id": session_id,
                "error": {"code": "INVALID_STATE", "message": f"session not paused (status={rt.get('status')})"},
            }
        task_id = rt.get("task_id") or "unknown"
        script = store.script_load(task_id)
        if script is None:
            return {
                "success": False,
                "status": "failed",
                "session_id": session_id,
                "error": {"code": "SCRIPT_NOT_FOUND", "message": f"no script for task_id: {task_id}"},
            }
        steps = list(script.get("steps") or [])
        cursor = int(rt.get("cursor_step_index") or 0)
        vars_env = dict(rt.get("vars") or {})

        rtype = (resolution or {}).get("type")
        note = (resolution or {}).get("note")
        incoming_vars = (resolution or {}).get("vars") or {}
        vars_overwritten: List[str] = []
        if isinstance(incoming_vars, dict) and incoming_vars:
            for k, v in incoming_vars.items():
                if k in vars_env:
                    vars_overwritten.append(k)
                vars_env[k] = v
            store.runtime_update(session_id, vars=vars_env)
        store.session_append(
            session_id,
            step_index=cursor,
            action="resolution",
            selector=None,
            url=None,
            payload={"resolution": resolution, "note": note, "vars_overwritten": vars_overwritten},
        )

        if rtype == "abort":
            store.runtime_update(session_id, status="failed", pause_event=None)
            return {
                "success": False,
                "status": "failed",
                "session_id": session_id,
                "error": {"code": "ABORTED", "message": note or "aborted by orchestrator"},
            }

        step_patch = None
        if rtype == "human_done":
            cursor += 1  # H1: continue next step
        elif rtype == "skip_step":
            cursor += 1
        elif rtype == "retry_step":
            cursor = cursor
        elif rtype == "patch_step":
            step_patch = (resolution or {}).get("patch") or {}
        else:
            return {
                "success": False,
                "status": "failed",
                "session_id": session_id,
                "error": {"code": "INVALID_RESOLUTION", "message": f"unknown resolution type: {rtype}"},
            }

        store.runtime_update(session_id, cursor_step_index=cursor, status="running", pause_event=None)
        dfus = self._load_all_dfus(store)
        return await self._run_from_cursor(
            session_id,
            task_id,
            steps,
            controller,
            store,
            dfus,
            start_index=cursor,
            step_patch=step_patch,
            vars_env=vars_env,
        )

    async def _run_from_cursor(
        self,
        session_id: str,
        task_id: str,
        steps: List[Dict[str, Any]],
        controller: "BrowserController",
        store: Any,
        dfus: List[Dict[str, Any]],
        *,
        start_index: int,
        step_patch: Optional[Dict[str, Any]],
        vars_env: Dict[str, Any],
    ) -> Dict[str, Any]:
        step_index = int(start_index)
        try:
            while step_index < len(steps):
                step = dict(steps[step_index] or {})
                if step_patch:
                    # Apply patch once to the current step, then discard.
                    if isinstance(step_patch.get("params"), dict):
                        step["params"] = {**(step.get("params") or {}), **step_patch["params"]}
                    if "selector_candidates" in step_patch:
                        step["selector_candidates"] = step_patch.get("selector_candidates")
                    step_patch = None
                # Resolve placeholders against current vars environment (dynamic across resume).
                step = resolve_params([step], vars_env)[0]

                action = (step.get("action") or "").lower()
                params = step.get("params") or {}

                if action in ("browser_init", "trajectory_start"):
                    if action == "browser_init":
                        await controller.start(headless=params.get("headless", True))
                    step_index += 1
                    store.runtime_update(session_id, cursor_step_index=step_index)
                    continue

                selector_for_match = params.get("selector")
                matched = _match_dfus_for_step(dfus, action=action, selector=selector_for_match)
                if matched is not None:
                    dfu, trig = matched
                    pause_event = {
                        "kind": "dfu_pause",
                        "session_id": session_id,
                        "task_id": task_id,
                        "step_index": step_index,
                        "action": action,
                        "params": params,
                        "selector_candidates": step.get("selector_candidates") or [],
                        "dfu_id": dfu.get("dfu_id"),
                        "trigger_match": trig,
                        "prompt": dfu.get("prompt") or "",
                        "allowed_resolutions": dfu.get("allowed_resolutions") or [],
                        "vars_snapshot": dict(vars_env or {}),
                    }
                    store.session_append(
                        session_id,
                        step_index=step_index,
                        action="pause",
                        selector=selector_for_match,
                        url=None,
                        payload={"pause_event": pause_event},
                    )
                    store.runtime_update(session_id, status="paused", pause_event=pause_event)
                    return {"success": False, "status": "paused", "session_id": session_id, "pause_event": pause_event}

                if action == "browser_open":
                    url = params.get("url", "")
                    record = await controller.open(url, wait_until=params.get("wait_until", "networkidle"))
                    url_after = getattr(record.page_state, "url", url)
                    store.session_append(
                        session_id,
                        step_index=step_index,
                        action="open",
                        selector=None,
                        url=url_after,
                        payload={"url": url},
                    )
                    step_index += 1
                    store.runtime_update(session_id, cursor_step_index=step_index)
                    continue

                if action == "browser_click":
                    selectors = _effective_selectors(step)
                    record = None
                    last_err: Optional[Exception] = None
                    used_selector = selectors[0] if selectors else None
                    for sel in selectors:
                        used_selector = sel
                        try:
                            record = await controller.click(sel, timeout=params.get("timeout"))
                            if record and record.result.get("success"):
                                break
                        except Exception as e:
                            last_err = e
                    if not record or not record.result.get("success"):
                        raise RuntimeError(str(last_err or "click failed"))
                    url_after = getattr(record.page_state, "url", None)
                    store.session_append(
                        session_id,
                        step_index=step_index,
                        action="click",
                        selector=used_selector,
                        url=url_after,
                        payload=params,
                    )
                    step_index += 1
                    store.runtime_update(session_id, cursor_step_index=step_index)
                    continue

                if action == "browser_input":
                    selectors = _effective_selectors(step)
                    record = None
                    used_selector = selectors[0] if selectors else None
                    for sel in selectors:
                        used_selector = sel
                        try:
                            record = await controller.input(sel, params.get("text", ""), delay=params.get("delay", 50))
                            if record and record.result.get("success"):
                                break
                        except Exception:
                            continue
                    if not record or not record.result.get("success"):
                        raise RuntimeError("input failed")
                    url_after = getattr(record.page_state, "url", None)
                    store.session_append(
                        session_id,
                        step_index=step_index,
                        action="input",
                        selector=used_selector,
                        url=url_after,
                        payload=params,
                    )
                    step_index += 1
                    store.runtime_update(session_id, cursor_step_index=step_index)
                    continue

                # Unknown action: treat as failure pause.
                raise RuntimeError(f"unsupported action: {action}")

            store.runtime_update(session_id, status="success", pause_event=None)
            return {"success": True, "status": "success", "session_id": session_id}
        except Exception as e:
            pause_event = {
                "kind": "step_failed",
                "session_id": session_id,
                "task_id": task_id,
                "step_index": step_index,
                "action": (steps[step_index].get("action") if step_index < len(steps) else None),
                "params": (steps[step_index].get("params") if step_index < len(steps) else None),
                "selector_candidates": (steps[step_index].get("selector_candidates") if step_index < len(steps) else []),
                "error": {"code": "STEP_FAILED", "message": str(e), "retryable": True},
            }
            store.session_append(
                session_id,
                step_index=step_index,
                action="pause",
                selector=None,
                url=None,
                payload={"pause_event": pause_event},
            )
            store.runtime_update(session_id, status="paused", pause_event=pause_event)
            return {"success": False, "status": "paused", "session_id": session_id, "pause_event": pause_event}

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
        Backward-compatible start runner. Prefer run_script_start/run_script_resume for pause/resume.
        """
        res = await self.run_script_start(script, controller, session_store, session_id=session_id)
        if res.get("status") == "success":
            return {"success": True, "session_id": res.get("session_id")}
        if res.get("status") == "paused":
            return {"success": False, "error": "paused", "session_id": res.get("session_id"), "pause_event": res.get("pause_event")}
        return {"success": False, "error": (res.get("error") or {}).get("message", "failed"), "session_id": res.get("session_id")}
