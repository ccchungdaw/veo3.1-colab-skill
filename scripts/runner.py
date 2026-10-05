#!/usr/bin/env python3
"""Run Google Veo 3.1 & MiniMax H3 video generation jobs with GPU enhancements on Google Colab CLI."""

from __future__ import annotations

import argparse
import json
import math
import os
import queue
import random
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"

SKILL_DIR = Path(__file__).resolve().parents[1]
NOTEBOOK_VEO = SKILL_DIR / "assets" / "Veo_3_1_Colab.ipynb"
NOTEBOOK_MINIMAX = SKILL_DIR / "assets" / "MiniMax_H3_Turbo_Colab.ipynb"
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
NAME_RE = re.compile(r"[^A-Za-z0-9_-]+")
AUTH = os.environ.get("COLAB_AUTH", "oauth2")
DEFAULT_MODEL = "veo-3.1-fast-generate-preview"
SUPPORTED_ASPECT_RATIOS = {"16:9", "9:16"}
SUPPORTED_RESOLUTIONS = {"720p", "1080p", "4k"}

MODEL_ALIASES = {
    "veo-3": "veo-3.1-generate-preview",
    "veo-3-generate": "veo-3.1-generate-preview",
    "veo-3.0-generate": "veo-3.0-generate-001",
    "veo-3.1": "veo-3.1-generate-preview",
    "veo-3-fast": "veo-3.1-fast-generate-preview",
    "veo-3.0-fast": "veo-3.0-fast-generate-preview",
    "veo-3.1-fast": "veo-3.1-fast-generate-preview",
    "veo-3-lite": "veo-3.1-lite-generate-preview",
    "veo-3.0-lite": "veo-3.0-lite-generate-preview",
    "veo-3.1-lite": "veo-3.1-lite-generate-preview",
    "minimax": "minimax-h3",
    "h3": "minimax-h3",
}


def normalize_model_name(name: str) -> str:
    cleaned = (name or "").strip().lower()
    return MODEL_ALIASES.get(cleaned, name)


class ColabCommandError(RuntimeError):
    def __init__(self, label: str, returncode: int, output: list[str]):
        self.label = label
        self.returncode = returncode
        self.output = output
        full_text = "\n".join(output)
        if "To authorize colab-cli" in full_text or "Enter the authorization code" in full_text:
            msg = (
                f"{label} 失敗：Colab CLI 尚未完成 Google 帳號授權！\n"
                "👉 請先在終端機 (PowerShell/CMD) 執行一次：colab --auth=oauth2 usage\n"
                "   依照指示於瀏覽器登入授權並貼回授權碼。\n"
                "💡 提示：若僅需生成 Veo 3 原生影片（不需 Colab GPU 補幀/超解析度/首幀圖），請取消勾選增強選項，即可使用 Direct API 模式極速生成！"
            )
            super().__init__(msg)
            return
        tail = "\n".join(line for line in output[-12:] if line)
        super().__init__(f"{label} failed (exit {returncode})" + (f":\n{tail}" if tail else ""))


class ColabTimeoutError(TimeoutError):
    pass


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def clean_output(value: str) -> str:
    return ANSI_RE.sub("", value).replace("\r", "").strip()


def write_progress(path: Path | None, state: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def parse_usage(output: str) -> dict[str, Any]:
    normalized = clean_output(output)

    def number(pattern: str, label: str) -> float:
        match = re.search(pattern, normalized, re.IGNORECASE | re.MULTILINE)
        if not match:
            raise ValueError(f"colab usage output did not contain {label!r}.")
        return float(match.group(1).replace(",", ""))

    balance = number(r"^Current balance:\s*([\d,]+(?:\.\d+)?)\s+compute units\s*$", "Current balance")
    rate = number(r"^Usage rate:\s*([\d,]+(?:\.\d+)?)\s*/\s*hr\s*$", "Usage rate")
    assignments = number(r"^Active assignments:\s*(\d+)\s*$", "Active assignments")
    return {
        "balance": balance,
        "rate_per_hour": rate,
        "active_assignments": int(assignments),
        "checked_at": now_iso(),
    }


def _colab_path() -> str:
    path = shutil.which("colab")
    if not path:
        raise FileNotFoundError("Colab CLI is not installed or not on PATH. Install google-colab-cli and authenticate.")
    return path


def call_colab(
    arguments: list[str],
    *,
    label: str,
    timeout: float,
    on_line: Callable[[str], None] | None = None,
) -> str:
    command = [_colab_path(), f"--auth={AUTH}", *arguments]
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    child = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
        start_new_session=True if hasattr(os, "setsid") else False,
    )
    lines: queue.Queue[str | None] = queue.Queue()

    def collect() -> None:
        assert child.stdout is not None
        for line in child.stdout:
            lines.put(line.rstrip("\n"))
        lines.put(None)

    reader = threading.Thread(target=collect, daemon=True)
    reader.start()
    output: list[str] = []
    eof = False
    started = time.monotonic()
    while not eof or child.poll() is None:
        if time.monotonic() - started > timeout and child.poll() is None:
            try:
                if hasattr(os, "killpg"):
                    os.killpg(child.pid, signal.SIGTERM)
                else:
                    child.terminate()
                child.wait(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    if hasattr(os, "killpg"):
                        os.killpg(child.pid, signal.SIGKILL)
                    else:
                        child.kill()
                except ProcessLookupError:
                    pass
            reader.join(timeout=2)
            if child.stdout is not None:
                child.stdout.close()
            raise ColabTimeoutError(f"{label} exceeded {timeout:g} seconds.")
        try:
            item = lines.get(timeout=0.25)
        except queue.Empty:
            continue
        if item is None:
            eof = True
            continue
        line = clean_output(item)
        output.append(line)
        if on_line:
            on_line(line)
    returncode = child.wait()
    reader.join(timeout=2)
    if child.stdout is not None:
        child.stdout.close()
    if returncode != 0:
        raise ColabCommandError(label, returncode, output)
    return "\n".join(line for line in output if line)


def check_cli() -> dict[str, str]:
    version = call_colab(["version"], label="colab version", timeout=20)
    return {"version": version, "auth": AUTH}


def get_usage() -> dict[str, Any]:
    output = call_colab(["usage"], label="colab usage", timeout=30)
    return parse_usage(output)


def start_session(
    session: str,
    gpu: str | None = None,
    high_mem: bool = False,
    progress_path: Path | None = None,
) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session):
        raise ValueError("Session name may contain only letters, numbers, underscores, and hyphens (up to 64 chars).")
    state: dict[str, Any] = {"task": "start", "status": "starting", "session": session, "log_tail": [], "updated_at": now_iso()}
    write_progress(progress_path, state)

    def on_line(line: str) -> None:
        state["log_tail"] = (state["log_tail"] + ([line] if line else []))[-30:]
        state["updated_at"] = now_iso()
        write_progress(progress_path, state)

    args = ["new", "--session", session]
    if gpu and gpu.lower() not in {"none", "false", "cpu"}:
        args.extend(["--gpu", gpu])
    if high_mem:
        args.append("--high-mem")

    try:
        output = call_colab(args, label="create Colab session", timeout=900, on_line=on_line)
        state.update({"status": "active", "session": session, "output": output, "updated_at": now_iso()})
        write_progress(progress_path, state)
    except Exception as exc:
        state.update({"status": "failed", "error": str(exc), "updated_at": now_iso()})
        write_progress(progress_path, state)
        raise


def stop_session(session: str, progress_path: Path | None = None) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session):
        raise ValueError("Invalid Colab session name.")
    state: dict[str, Any] = {"task": "stop", "status": "stopping", "session": session, "log_tail": [], "updated_at": now_iso()}
    write_progress(progress_path, state)

    def on_line(line: str) -> None:
        state["log_tail"] = (state["log_tail"] + ([line] if line else []))[-30:]
        state["updated_at"] = now_iso()
        write_progress(progress_path, state)

    try:
        output = call_colab(["stop", "--session", session], label="stop Colab session", timeout=300, on_line=on_line)
        state.update({"status": "stopped", "output": output, "updated_at": now_iso()})
        write_progress(progress_path, state)
    except Exception as exc:
        state.update({"status": "failed", "error": str(exc), "updated_at": now_iso()})
        write_progress(progress_path, state)
        raise


def safe_job_id(value: Any) -> str:
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,48}", value):
        return value
    return uuid.uuid4().hex[:16]


def safe_name(value: Any, fallback: str) -> str:
    candidate = NAME_RE.sub("_", str(value or "")).strip("_-")[:64]
    return candidate or fallback


def compose_cinematic_prompt(
    *,
    subject: str,
    action: str,
    setting: str,
    camera_movement: str = "",
    lighting: str = "",
    audio_description: str = "",
    style: str = "Cinematic, photorealistic",
) -> str:
    """Helper to compose a structured cinematic prompt tailored for Veo 3.1."""
    parts = []
    if style:
        parts.append(f"{style.strip()} shot of {subject.strip()} {action.strip()}.")
    else:
        parts.append(f"{subject.strip()} {action.strip()}.")
    if setting:
        parts.append(f"Setting: {setting.strip()}.")
    if camera_movement:
        parts.append(f"Camera: {camera_movement.strip()}.")
    if lighting:
        parts.append(f"Lighting: {lighting.strip()}.")
    if audio_description:
        parts.append(f"Audio: {audio_description.strip()}.")
    return " ".join(parts)


def resolve_jobs(manifest: dict[str, Any], output_dir: Path) -> list[dict[str, Any]]:
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("Manifest must contain a non-empty jobs list.")
    if len(jobs) > 50:
        raise ValueError("A single batch may contain at most 50 videos.")
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_outputs: set[Path] = set()

    for index, raw in enumerate(jobs, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"Job {index} must be an object.")

        engine = str(raw.get("engine", "veo")).strip().lower()
        if engine in {"minimax", "h3", "minimax-h3"}:
            engine = "minimax"
        else:
            engine = "veo"

        # Reference images / First frame
        refs = raw.get("reference_images", raw.get("images", []))
        if refs is None:
            refs = []
        max_refs = 9 if engine == "minimax" else 3
        if not isinstance(refs, list) or len(refs) > max_refs:
            raise ValueError(f"Job {index} supports 0–{max_refs} reference images for {engine}.")
        image_paths: list[Path] = []
        for img in refs:
            path = Path(str(img)).expanduser().resolve()
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"Reference image is missing or empty: {path}")
            image_paths.append(path)

        first_frame = raw.get("first_frame")
        first_frame_path = None
        if first_frame:
            ff_p = Path(str(first_frame)).expanduser().resolve()
            if not ff_p.is_file() or ff_p.stat().st_size == 0:
                raise ValueError(f"First frame image is missing or empty: {ff_p}")
            first_frame_path = ff_p

        last_frame = raw.get("last_frame")
        last_frame_path = None
        if last_frame:
            lf_p = Path(str(last_frame)).expanduser().resolve()
            if not lf_p.is_file() or lf_p.stat().st_size == 0:
                raise ValueError(f"Last frame image is missing or empty: {lf_p}")
            last_frame_path = lf_p

        # Prompt resolution
        prompt_file = raw.get("prompt_file")
        if prompt_file:
            prompt_path = Path(str(prompt_file)).expanduser().resolve()
            if not prompt_path.is_file() or prompt_path.stat().st_size == 0:
                raise ValueError(f"Prompt file is missing or empty: {prompt_path}")
            prompt = prompt_path.read_text(encoding="utf-8")
        else:
            prompt = str(raw.get("prompt", ""))
        if not prompt.strip():
            raise ValueError(f"Job {index} needs a non-empty UTF-8 prompt.")

        duration = int(raw.get("duration_seconds", raw.get("duration", 5 if engine == "veo" else 12)))
        if engine == "veo" and not (4 <= duration <= 12):
            raise ValueError(f"Job {index} Veo duration must be between 5 and 8 seconds.")
        if engine == "minimax" and not (4 <= duration <= 15):
            raise ValueError(f"Job {index} MiniMax duration must be between 4 and 15 seconds.")

        aspect_ratio = str(raw.get("aspect_ratio", "16:9")).strip()
        if aspect_ratio not in SUPPORTED_ASPECT_RATIOS:
            raise ValueError(f"Job {index} aspect_ratio must be one of {SUPPORTED_ASPECT_RATIOS}.")

        resolution = str(raw.get("resolution", "1080p")).strip().lower()
        if resolution not in SUPPORTED_RESOLUTIONS:
            raise ValueError(f"Job {index} resolution must be one of {SUPPORTED_RESOLUTIONS}.")

        model = normalize_model_name(str(raw.get("model", DEFAULT_MODEL)).strip())

        job_id = safe_job_id(raw.get("id"))
        if job_id in seen_ids:
            raise ValueError(f"Job {index} duplicates job id {job_id!r}.")
        seen_ids.add(job_id)

        stem = safe_name(raw.get("output_name") or raw.get("title"), f"{engine}_{index:02d}")
        output = Path(str(raw.get("output_path") or output_dir / f"{stem}_{job_id}.mp4")).expanduser().resolve()
        if output in seen_outputs:
            raise ValueError(f"Multiple jobs target the same output path: {output}")
        seen_outputs.add(output)
        output.parent.mkdir(parents=True, exist_ok=True)

        seed = raw.get("seed")
        seed_val = random.SystemRandom().randrange(0, 2**64) if seed in (None, "") else int(seed)

        resolved.append({
            "id": job_id,
            "engine": engine,
            "title": str(raw.get("title") or f"Video {index}")[:120],
            "prompt": prompt,
            "reference_images": image_paths,
            "first_frame": first_frame_path,
            "last_frame": last_frame_path,
            "model": model,
            "duration_seconds": duration,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "negative_prompt": str(raw.get("negative_prompt", "")),
            "seed": seed_val,
            # 4 Enhancement modules
            "flux_prompt": str(raw.get("flux_prompt", "")),
            "face_restore": bool(raw.get("face_restore", False)),
            "upscale": str(raw.get("upscale", "none")),
            "interpolate": str(raw.get("interpolate", "none")),
            "output_path": output,
        })
    return resolved


def verify_mp4(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(f"Downloaded MP4 is missing or empty: {path}")
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "stream=codec_type", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if probe.returncode != 0:
        raise ValueError(f"Downloaded output is not a readable MP4: {clean_output(probe.stderr)}")
    streams = {item.get("codec_type") for item in json.loads(probe.stdout).get("streams", [])}
    if "video" not in streams:
        raise ValueError(f"Downloaded MP4 must contain video stream; found {sorted(streams)}.")


def run_batch(
    manifest_path: Path,
    *,
    session: str | None,
    gpu: str | None = None,
    high_mem: bool = False,
    stop_on_complete: bool = False,
    progress_path: Path | None = None,
    output_dir: Path,
    exec_timeout: float = 1800,
    api_key: str | None = None,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    jobs = resolve_jobs(manifest, output_dir)
    owns_session = session is None
    if session is None:
        session = f"vid-{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}-{uuid.uuid4().hex[:6]}"
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session):
        raise ValueError("Invalid Colab session name.")

    api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    # If any job is minimax, default to A100 GPU and high mem
    has_minimax = any(j["engine"] == "minimax" for j in jobs)
    has_flux = any(bool(j.get("flux_prompt")) for j in jobs)
    if (has_minimax or has_flux) and not gpu:
        gpu = "A100"
        high_mem = True

    progress: dict[str, Any] = {
        "task": "batch",
        "status": "starting",
        "session": session,
        "jobs": [{"id": job["id"], "engine": job["engine"], "title": job["title"], "status": "queued", "output": str(job["output_path"])} for job in jobs],
        "log_tail": [],
        "updated_at": now_iso(),
    }
    write_progress(progress_path, progress)

    def log_line(line: str) -> None:
        if not line or len(line) > 320:
            return
        progress["log_tail"] = (progress["log_tail"] + [line])[-30:]
        progress["updated_at"] = now_iso()
        write_progress(progress_path, progress)

    results: list[dict[str, Any]] = []
    batch_error: str | None = None
    work_root = manifest_path.parent / f"work_{uuid.uuid4().hex[:8]}"
    work_root.mkdir(parents=True, exist_ok=True)

    try:
        if owns_session:
            start_session(session, gpu=gpu, high_mem=high_mem)
        progress["status"] = "running"
        progress["updated_at"] = now_iso()
        write_progress(progress_path, progress)

        for index, job in enumerate(jobs):
            current = progress["jobs"][index]
            current.update({"status": "uploading", "started_at": now_iso()})
            progress["current_job"] = job["id"]
            progress["updated_at"] = now_iso()
            write_progress(progress_path, progress)

            remote_prefix = f"/content/{job['engine']}_{job['id']}"
            remote_refs: list[str] = []
            for img_index, img_path in enumerate(job["reference_images"], start=1):
                remote_img = f"{remote_prefix}_ref_{img_index}.png"
                call_colab(
                    ["upload", "--session", session, str(img_path), remote_img],
                    label=f"upload reference {img_index} for {job['title']}",
                    timeout=300,
                    on_line=log_line,
                )
                remote_refs.append(remote_img)

            remote_first_frame = ""
            if job["first_frame"]:
                remote_first_frame = f"{remote_prefix}_first_frame.png"
                call_colab(
                    ["upload", "--session", session, str(job["first_frame"]), remote_first_frame],
                    label=f"upload first frame for {job['title']}",
                    timeout=300,
                    on_line=log_line,
                )

            remote_last_frame = ""
            if job["last_frame"]:
                remote_last_frame = f"{remote_prefix}_last_frame.png"
                call_colab(
                    ["upload", "--session", session, str(job["last_frame"]), remote_last_frame],
                    label=f"upload last frame for {job['title']}",
                    timeout=300,
                    on_line=log_line,
                )

            prompt_path = work_root / f"{job['id']}.txt"
            prompt_path.write_text(job["prompt"], encoding="utf-8")
            remote_prompt = f"{remote_prefix}_prompt.txt"
            remote_output = f"{remote_prefix}_output.mp4"
            call_colab(
                ["upload", "--session", session, str(prompt_path), remote_prompt],
                label=f"upload prompt for {job['title']}",
                timeout=120,
                on_line=log_line,
            )

            job_dir = work_root / job["id"]
            job_dir.mkdir(parents=True, exist_ok=True)

            if job["engine"] == "minimax":
                notebook_src = NOTEBOOK_MINIMAX
                notebook_copy = job_dir / "MiniMax_H3_Turbo_Colab.ipynb"
                shutil.copy2(notebook_src, notebook_copy)
                env_values = [
                    "H3_INFERENCE_MODE=reference",
                    "H3_REFERENCE_IMAGES=" + json.dumps(remote_refs, separators=(",", ":")),
                    "H3_PROMPT_FILE=" + remote_prompt,
                    "H3_DURATION_SECONDS=" + str(job["duration_seconds"]),
                    "H3_SEED=" + str(job["seed"]),
                    "H3_OUTPUT_PATH=" + remote_output,
                ]
            else:
                notebook_src = NOTEBOOK_VEO
                notebook_copy = job_dir / "Veo_3_1_Colab.ipynb"
                shutil.copy2(notebook_src, notebook_copy)
                env_values = [
                    f"VEO_MODEL={job['model']}",
                    f"VEO_PROMPT_FILE={remote_prompt}",
                    f"VEO_REFERENCE_IMAGES={json.dumps(remote_refs, separators=(',', ':'))}",
                    f"VEO_FIRST_FRAME={remote_first_frame}",
                    f"VEO_LAST_FRAME={remote_last_frame}",
                    f"VEO_DURATION_SECONDS={job['duration_seconds']}",
                    f"VEO_ASPECT_RATIO={job['aspect_ratio']}",
                    f"VEO_RESOLUTION={job['resolution']}",
                    f"VEO_NEGATIVE_PROMPT={job['negative_prompt']}",
                    f"VEO_OUTPUT_PATH={remote_output}",
                    f"ENABLE_FLUX={'1' if job.get('flux_prompt') else '0'}",
                    f"FLUX_PROMPT={job.get('flux_prompt', '')}",
                    f"ENABLE_FACE_RESTORE={'1' if job.get('face_restore') else '0'}",
                    f"ENABLE_UPSCALE={'1' if job.get('upscale') in ('2x', '4k', '4x') else '0'}",
                    f"ENABLE_INTERPOLATE={'1' if job.get('interpolate') in ('48', '60', '120') else '0'}",
                    f"TARGET_FPS={job.get('interpolate', '60')}",
                ]
                if api_key:
                    env_values.append(f"GEMINI_API_KEY={api_key}")

            exec_args = ["exec", "--session", session, "--timeout", str(int(exec_timeout))]
            for env in env_values:
                exec_args.extend(["--env", env])
            exec_args.extend(["--file", str(notebook_copy)])

            current.update({"status": "generating", "engine": job["engine"], "duration_seconds": job["duration_seconds"]})
            progress["updated_at"] = now_iso()
            write_progress(progress_path, progress)

            call_colab(exec_args, label=f"generate {job['title']}", timeout=exec_timeout + 60, on_line=log_line)

            current["status"] = "downloading"
            progress["updated_at"] = now_iso()
            write_progress(progress_path, progress)
            call_colab(
                ["download", "--session", session, remote_output, str(job["output_path"])],
                label=f"download {job['title']}",
                timeout=600,
                on_line=log_line,
            )
            verify_mp4(job["output_path"])
            current.update({"status": "completed", "finished_at": now_iso(), "bytes": job["output_path"].stat().st_size})
            results.append({"id": job["id"], "output": str(job["output_path"]), "status": "completed"})
            progress["updated_at"] = now_iso()
            write_progress(progress_path, progress)

    except ColabTimeoutError as exc:
        batch_error = str(exc)
        if "current_job" in progress:
            cur = next((item for item in progress["jobs"] if item["id"] == progress["current_job"]), None)
            if cur and cur["status"] not in {"completed", "failed"}:
                cur.update({"status": "failed", "error": batch_error, "finished_at": now_iso()})
        for item in progress["jobs"]:
            if item["status"] == "queued":
                item["status"] = "cancelled"
    except Exception as exc:
        batch_error = str(exc)
        if "current_job" in progress:
            cur = next((item for item in progress["jobs"] if item["id"] == progress["current_job"]), None)
            if cur and cur["status"] not in {"completed", "failed"}:
                cur.update({"status": "failed", "error": batch_error, "finished_at": now_iso()})
        for item in progress["jobs"]:
            if item["status"] == "queued":
                item["status"] = "cancelled"
    finally:
        if (owns_session or stop_on_complete) and session:
            progress["status"] = "stopping_session"
            progress["updated_at"] = now_iso()
            write_progress(progress_path, progress)
            try:
                stop_session(session)
                progress["session_status"] = "stopped"
            except Exception as exc:
                progress["session_status"] = "stop_failed"
                progress["cleanup_error"] = str(exc)
                batch_error = batch_error or f"Batch ended, but session {session} could not be stopped: {exc}"
        elif not owns_session:
            progress["session_status"] = "active"
        shutil.rmtree(work_root, ignore_errors=True)

    completed = sum(item["status"] == "completed" for item in progress["jobs"])
    failed = sum(item["status"] == "failed" for item in progress["jobs"])
    cancelled = sum(item["status"] == "cancelled" for item in progress["jobs"])
    progress.update({
        "status": "completed" if not batch_error and completed == len(jobs) else "partial" if completed else "failed",
        "completed_count": completed,
        "failed_count": failed,
        "cancelled_count": cancelled,
        "error": batch_error,
        "updated_at": now_iso(),
        "results": results,
    })
    write_progress(progress_path, progress)
    return progress


def run_direct_veo(
    prompt: str,
    output_path: Path,
    *,
    model: str = DEFAULT_MODEL,
    duration: int = 5,
    aspect_ratio: str = "16:9",
    resolution: str = "1080p",
    negative_prompt: str = "",
    first_frame: Path | None = None,
    last_frame: Path | None = None,
    reference_images: list[Path] | None = None,
    api_key: str | None = None,
) -> Path:
    from google import genai
    from google.genai import types

    api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is required for Veo 3 video generation. Please provide an API key.")
    client = genai.Client(api_key=api_key)

    input_image = None
    if first_frame and first_frame.is_file():
        input_image = types.Image.from_file(location=str(first_frame))
    elif reference_images and len(reference_images) > 0 and reference_images[0].is_file():
        input_image = types.Image.from_file(location=str(reference_images[0]))

    config_kwargs: dict[str, Any] = {
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "duration_seconds": duration,
        "negative_prompt": negative_prompt or "blurry, low quality",
    }
    if last_frame and last_frame.is_file():
        try:
            config_kwargs["last_frame"] = types.Image.from_file(location=str(last_frame))
        except Exception:
            pass

    config = types.GenerateVideosConfig(**config_kwargs)
    source = types.GenerateVideosSource(
        prompt=prompt,
        image=input_image,
    )

    norm_model = normalize_model_name(model)
    print(f"[Direct API] 正在發送請求至 {norm_model}...")
    op = client.models.generate_videos(
        model=norm_model,
        source=source,
        config=config,
    )
    print(f"[Direct API] 任務已建立: {getattr(op, 'name', 'submitted')}")
    start_t = time.time()
    while not op.done:
        elapsed = int(time.time() - start_t)
        print(f"[Direct API] 影片生成中... 已耗時 {elapsed} 秒")
        time.sleep(10)
        op = client.operations.get(op)

    if op.error:
        raise RuntimeError(f"Veo 3 生成錯誤: {op.error}")

    if not op.response or not op.response.generated_videos:
        raise RuntimeError("Veo 3 生成完成但未收到生成的視訊物件。")

    video_item = op.response.generated_videos[0]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[Direct API] 正在下載產生的視訊至 {output_path.name}...")

    downloaded = False
    if getattr(video_item.video, "video_bytes", None):
        output_path.write_bytes(video_item.video.video_bytes)
        downloaded = True
    else:
        # Standard google-genai: stream download using client.files.download
        try:
            client.files.download(file=video_item.video, destination=str(output_path))
            if output_path.is_file() and output_path.stat().st_size > 0:
                downloaded = True
        except Exception as dl_err:
            print(f"[Direct API] 串流下載失敗 ({dl_err})，嘗試記憶體下載...")

        if not downloaded:
            try:
                data = client.files.download(file=video_item.video)
                if data:
                    output_path.write_bytes(data)
                    downloaded = True
            except Exception as mem_err:
                print(f"[Direct API] 記憶體下載失敗 ({mem_err})")

        if not downloaded:
            # Fallback to direct HTTP download if URI is a web URL
            uri = getattr(video_item.video, "uri", None)
            if uri and str(uri).startswith("http"):
                import urllib.request
                urllib.request.urlretrieve(uri, str(output_path))
                downloaded = True

    if not downloaded:
        raise RuntimeError(f"無法下載 Veo 生成的影片 (URI: {getattr(video_item.video, 'uri', 'unknown')})")

    verify_mp4(output_path)
    print(f"[Direct API] 視訊生成完成！檔案大小: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
    return output_path


def run_single(
    prompt: str | Path,
    *,
    engine: str = "veo",
    images: list[Path] | None = None,
    first_frame: Path | None = None,
    last_frame: Path | None = None,
    output: Path | None = None,
    model: str = DEFAULT_MODEL,
    duration: int = 5,
    aspect_ratio: str = "16:9",
    resolution: str = "1080p",
    seed: int | None = None,
    flux_prompt: str | None = None,
    face_restore: bool = False,
    upscale: str = "none",
    interpolate: str = "none",
    session: str | None = None,
    gpu: str | None = None,
    high_mem: bool = False,
    timeout: float = 1800,
    api_key: str | None = None,
    use_colab: bool = False,
) -> Path:
    images = images or []
    has_enhancements = bool(flux_prompt or face_restore or upscale not in ("none", "") or interpolate not in ("none", ""))
    target_output = output or (Path.cwd() / f"{engine}_{time.strftime('%Y%m%d_%H%M%S')}.mp4")

    if engine == "veo" and not has_enhancements and not use_colab:
        prompt_text = Path(prompt).read_text(encoding="utf-8") if (isinstance(prompt, Path) or os.path.isfile(str(prompt))) else str(prompt)
        print("[Direct Mode] 使用 Direct Google GenAI API 模式生成 Veo 視訊（速度更快且不消耗 Colab 運算點數）...")
        return run_direct_veo(
            prompt_text,
            target_output,
            model=model,
            duration=duration,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            first_frame=first_frame,
            last_frame=last_frame,
            reference_images=images,
            api_key=api_key,
        )

    temp_dir = Path(os.environ.get("TEMP", "/tmp")) / f"vid_single_{uuid.uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        manifest_path = temp_dir / "manifest.json"

        job_data: dict[str, Any] = {
            "id": "single",
            "engine": engine,
            "title": f"Single {engine.upper()} Video",
            "model": normalize_model_name(model),
            "duration_seconds": duration,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "reference_images": [str(p) for p in images],
            "flux_prompt": flux_prompt or "",
            "face_restore": face_restore,
            "upscale": upscale,
            "interpolate": interpolate,
            "output_path": str(target_output),
        }
        if seed is not None:
            job_data["seed"] = seed
        if first_frame:
            job_data["first_frame"] = str(first_frame)
        if last_frame:
            job_data["last_frame"] = str(last_frame)

        if isinstance(prompt, Path) or (isinstance(prompt, str) and os.path.isfile(prompt)):
            job_data["prompt_file"] = str(Path(prompt).resolve())
        else:
            job_data["prompt"] = str(prompt)

        manifest = {"jobs": [job_data]}
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        res = run_batch(
            manifest_path,
            session=session,
            gpu=gpu,
            high_mem=high_mem,
            output_dir=target_output.parent,
            exec_timeout=timeout,
            api_key=api_key,
        )
        if res.get("status") != "completed":
            raise RuntimeError(f"Video generation failed: {res.get('error')}")
        return target_output
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Google Veo 3 & MiniMax H3 Colab Video Runner with GPU Enhancements")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # version
    subparsers.add_parser("version", help="Check Colab CLI version")

    # usage
    p_usage = subparsers.add_parser("usage", help="Check Colab compute unit usage and balance")
    p_usage.add_argument("--json", action="store_true", help="Print json output")

    # start session
    p_start = subparsers.add_parser("start", help="Start a Colab session")
    p_start.add_argument("--session", required=True, help="Session name")
    p_start.add_argument("--gpu", default="none", help="GPU type (e.g. none, T4, A100)")
    p_start.add_argument("--high-mem", action="store_true", help="Request high memory runtime")

    # stop session
    p_stop = subparsers.add_parser("stop", help="Stop an active Colab session")
    p_stop.add_argument("--session", required=True, help="Session name")

    # single
    p_single = subparsers.add_parser("single", help="Generate a single video")
    p_single.add_argument("-p", "--prompt", required=True, help="Prompt text or path to prompt text file")
    p_single.add_argument("-e", "--engine", default="veo", choices=["veo", "minimax"], help="Model engine: veo or minimax (default: veo)")
    p_single.add_argument("-i", "--image", action="append", default=[], help="Reference image (repeat up to 3 for Veo, 9 for MiniMax)")
    p_single.add_argument("--first-frame", help="First frame image path")
    p_single.add_argument("--last-frame", help="Last frame image path")
    p_single.add_argument("-o", "--output", help="Output MP4 target path")
    p_single.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"Model variant (default: {DEFAULT_MODEL})")
    p_single.add_argument("-d", "--duration", type=int, default=5, help="Duration in seconds (Veo: 5-8, MiniMax: 4-15)")
    p_single.add_argument("-a", "--aspect-ratio", default="16:9", choices=["16:9", "9:16"])
    p_single.add_argument("-r", "--resolution", default="1080p", choices=["720p", "1080p", "4k"])
    p_single.add_argument("--seed", type=int, help="Random seed")
    # 4 Enhancement modules
    p_single.add_argument("--flux-prompt", help="Prompt for FLUX.1 first-frame pre-generation")
    p_single.add_argument("--face-restore", action="store_true", help="Enable CodeFormer face restoration")
    p_single.add_argument("--upscale", default="none", choices=["none", "2x", "4x", "4k"], help="Real-ESRGAN super-resolution")
    p_single.add_argument("--interpolate", default="none", choices=["none", "48", "60", "120"], help="RIFE frame interpolation (target fps)")
    p_single.add_argument("--session", help="Existing session name")
    p_single.add_argument("--gpu", help="Colab GPU (default: none for Veo, A100 for MiniMax)")
    p_single.add_argument("--timeout", type=float, default=1800, help="Execution timeout in seconds")
    p_single.add_argument("--api-key", help="Google GenAI API Key")
    p_single.add_argument("--use-colab", action="store_true", help="Force Colab cloud execution for Veo without enhancement modules")

    # batch
    p_batch = subparsers.add_parser("batch", help="Run a batch of videos from a JSON manifest")
    p_batch.add_argument("--manifest", required=True, help="Path to jobs.json manifest")
    p_batch.add_argument("--output-dir", required=True, help="Output directory for MP4s")
    p_batch.add_argument("--session", help="Session name to reuse or create")
    p_batch.add_argument("--gpu", help="Colab GPU (auto-selected if omitted)")
    p_batch.add_argument("--high-mem", action="store_true", help="Request high memory runtime")
    p_batch.add_argument("--stop-on-complete", action="store_true", help="Stop session after batch")
    p_batch.add_argument("--progress", help="Path to write progress.json")
    p_batch.add_argument("--timeout", type=float, default=1800, help="Per-job timeout in seconds")
    p_batch.add_argument("--api-key", help="Google GenAI API Key")

    args = parser.parse_args()

    if args.command == "version":
        info = check_cli()
        print(json.dumps(info, indent=2))
        return 0

    if args.command == "usage":
        usage = get_usage()
        if args.json:
            print(json.dumps(usage, indent=2))
        else:
            print(f"Current balance: {usage['balance']} compute units")
            print(f"Usage rate: {usage['rate_per_hour']}/hr")
            print(f"Active assignments: {usage['active_assignments']}")
        return 0

    if args.command == "start":
        start_session(args.session, gpu=args.gpu, high_mem=args.high_mem)
        print(f"Session {args.session} started successfully.")
        return 0

    if args.command == "stop":
        stop_session(args.session)
        print(f"Session {args.session} stopped successfully.")
        return 0

    if args.command == "single":
        images = [Path(img) for img in args.image]
        ff = Path(args.first_frame) if args.first_frame else None
        lf = Path(args.last_frame) if args.last_frame else None
        out = Path(args.output) if args.output else None
        result = run_single(
            args.prompt,
            engine=args.engine,
            images=images,
            first_frame=ff,
            last_frame=lf,
            output=out,
            model=args.model,
            duration=args.duration,
            aspect_ratio=args.aspect_ratio,
            resolution=args.resolution,
            seed=args.seed,
            flux_prompt=args.flux_prompt,
            face_restore=args.face_restore,
            upscale=args.upscale,
            interpolate=args.interpolate,
            session=args.session,
            gpu=args.gpu,
            timeout=args.timeout,
            api_key=args.api_key,
            use_colab=args.use_colab,
        )
        print(f"Video saved to: {result}")
        return 0

    if args.command == "batch":
        manifest_p = Path(args.manifest).resolve()
        out_dir = Path(args.output_dir).resolve()
        prog_p = Path(args.progress).resolve() if args.progress else None
        res = run_batch(
            manifest_p,
            session=args.session,
            gpu=args.gpu,
            high_mem=args.high_mem,
            stop_on_complete=args.stop_on_complete,
            progress_path=prog_p,
            output_dir=out_dir,
            exec_timeout=args.timeout,
            api_key=args.api_key,
        )
        print(json.dumps(res, indent=2))
        return 0 if res.get("status") == "completed" else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
