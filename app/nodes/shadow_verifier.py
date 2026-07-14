"""Shadow Verifier node: run the patched test in the Shadow Runtime.

Serves as a fast, offline gate before invoking the live, slow, and potentially
flaky selector verifier and test runner. If the shadow replay fails, the loop
re-patches with feedback, saving a wasted test run.
"""

from pathlib import Path

import structlog

from app.shadow.config import ShadowConfig
from app.shadow.runtime import run_shadow
from app.shadow.schemas import ShadowRunResult
from app.shadow.snapshot_store import SnapshotNotFoundError, SnapshotStore
from app.shadow.workspace import ShadowWorkspace
from app.state import AgentState
from app.utils.files import atomic_write

logger = structlog.get_logger(__name__)


def _revert(code: str, instructions: list) -> str:
    """Undo an applied patch by restoring each instruction's original line."""
    lines = code.splitlines(keepends=True)
    for instruction in instructions:
        index = instruction.get("line", 1) - 1
        if 0 <= index < len(lines):
            newline = "\n" if lines[index].endswith("\n") else ""
            lines[index] = instruction.get("original", "") + newline
    return "".join(lines)


def _shadow_feedback(result: ShadowRunResult) -> str:
    """Build a diagnosis addendum naming the shadow replay failure details."""
    detail = (
        f"matched={result.matched_count}, missed={result.missed_count}, score={result.score:.2f}"
    )
    return (
        "\n\n[SHADOW VERIFICATION FEEDBACK] The previous patch was rejected because the shadow replay failed: "
        f"{detail}. Make sure to adjust selectors or wait conditions to match expected network interactions."
    )


def shadow_verifier(state: AgentState) -> dict:
    """Verify the patched test script using the Shadow Runtime replay.

    Temporarily writes the patched code to disk, executes the shadow replay,
    and reverts the changes on disk/state if the replay fails.

    If no snapshot exists for the test, skips shadow verification gracefully.
    """
    test_path = Path(state["test_script_path"])
    snapshot_id = test_path.stem

    logger.info("shadow_verify_started", test_script_path=str(test_path), snapshot_id=snapshot_id)

    # Check if the snapshot exists before running to skip gracefully if absent
    cfg = ShadowConfig()
    workspace = ShadowWorkspace(cfg)
    store = SnapshotStore(workspace)
    try:
        store.get_snapshot(snapshot_id)
    except SnapshotNotFoundError:
        logger.info("shadow_verify_skipped_no_snapshot", snapshot_id=snapshot_id)
        return {"shadow_report": {"ok": True, "skipped": True}}

    # Write the current candidate code to disk so run_shadow can execute it
    original_code = test_path.read_text(encoding="utf-8")
    atomic_write(test_path, state["current_code"])

    try:
        result = run_shadow(test_path=test_path, snapshot_id=snapshot_id, config=cfg)

        if not isinstance(result, ShadowRunResult):
            # Fallback if run_shadow returned placeholder string
            logger.info("shadow_verify_skipped_placeholder")
            return {"shadow_report": {"ok": True, "skipped": True}}

        if result.is_success:
            logger.info("shadow_verify_passed", score=result.score)
            return {"shadow_report": {"ok": True, "score": result.score}}

        # Replay failed: revert files and increment loop count
        logger.info("shadow_verify_failed", score=result.score)
        instructions = state["patch_instructions"].get("instructions", [])
        reverted_code = _revert(state["current_code"], instructions)
        atomic_write(test_path, reverted_code)

        next_count = state["loop_count"] + 1
        return {
            "current_code": reverted_code,
            "analysis_report": state["analysis_report"] + _shadow_feedback(result),
            "loop_count": next_count,
            "shadow_report": {"ok": False, "score": result.score},
        }

    except Exception as e:
        logger.exception("shadow_verify_exception")
        # In case of any exception, revert changes to disk
        atomic_write(test_path, original_code)

        next_count = state["loop_count"] + 1
        return {
            "current_code": original_code,
            "analysis_report": (
                state["analysis_report"]
                + f"\n\n[SHADOW VERIFICATION ERROR] Exception occurred during shadow verification: {e}"
            ),
            "loop_count": next_count,
            "shadow_report": {"ok": False, "error": str(e)},
        }
