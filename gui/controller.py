import copy
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QProcess, QProcessEnvironment, pyqtSignal
from PyQt6.QtWidgets import QWidget

from gui.config import PIPELINE_PATH, PIPELINE_PYTHON, ROOT
from gui.utils import (
    append_job_log,
    build_effective_analysis,
    classify_process_log_line,
    create_base_job,
    get_analysis_path,
    get_render_options_path,
    get_render_result_path,
    read_json,
    should_capture_process_log_line,
    write_json,
)


class DubStudioJobController(QWidget):
    analysis_ready = pyqtSignal(str, object)
    render_ready = pyqtSignal(str, object)
    status_changed = pyqtSignal(str, object)
    job_failed = pyqtSignal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self.jobs: dict[str, dict[str, Any]] = {}
        self.active_job_id: str | None = None

    def _get_running_job_id(self) -> str | None:
        if not self.active_job_id:
            return None
        job = self.jobs.get(self.active_job_id)
        process = job.get("process") if job else None
        if process is None:
            self.active_job_id = None
            return None
        if process.state() == QProcess.ProcessState.NotRunning:
            job["process"] = None
            self.active_job_id = None
            return None
        return self.active_job_id

    def has_running_job(self) -> bool:
        return self._get_running_job_id() is not None

    def _fail_job(self, job_id: str, message: str, *, emit_signal: bool = True) -> None:
        job = self.jobs.get(job_id)
        if not job:
            return
        job["process"] = None
        job["status"] = "error"
        job["lastError"] = message
        append_job_log(job, message, "error")
        if self.active_job_id == job_id:
            self.active_job_id = None
        self.status_changed.emit(job_id, self.get_job_status(job_id))
        if emit_signal:
            self.job_failed.emit(job_id, message)

    def analyze_video(
        self, input_path: str, options: dict[str, Any] | None = None
    ) -> str:
        if self._get_running_job_id():
            raise RuntimeError("A pipeline task is already running.")
        job_id = str(uuid.uuid4())
        job = create_base_job(job_id, input_path)
        self.jobs[job_id] = job
        if options:
            job["overrides"] = copy.deepcopy(options)
        target_language = ""
        if options:
            target_language = str(options.get("targetLanguage") or "").strip()
        self._start_process(
            job_id,
            [
                "analyze",
                "--job-id",
                job_id,
                "--input",
                input_path,
                *(
                    ["--target-language", target_language]
                    if target_language
                    else []
                ),
                "--output-json",
                str(get_analysis_path(job_id)),
            ],
            get_analysis_path(job_id),
            mode="analysis",
        )
        return job_id

    def get_analysis(self, job_id: str) -> dict[str, Any] | None:
        job = self.jobs.get(job_id)
        if not job or not job.get("analysis"):
            return None
        return build_effective_analysis(job)

    def update_analysis_config(
        self, job_id: str, overrides: dict[str, Any]
    ) -> dict[str, Any]:
        job = self.jobs.get(job_id)
        if not job:
            raise RuntimeError("Dub Studio job not found.")
        job["overrides"] = {
            **(job.get("overrides") or {}),
            **overrides,
            "voiceMapping": {
                **(job.get("overrides", {}).get("voiceMapping") or {}),
                **(overrides.get("voiceMapping") or {}),
            },
            "subtitleRegion": {
                **(job.get("overrides", {}).get("subtitleRegion") or {}),
                **(overrides.get("subtitleRegion") or {}),
            },
            "subtitleTimeline": copy.deepcopy(
                overrides.get(
                    "subtitleTimeline",
                    job.get("overrides", {}).get("subtitleTimeline"),
                )
            ),
            "subtitleSrt": overrides.get(
                "subtitleSrt", job.get("overrides", {}).get("subtitleSrt")
            ),
            "subtitleTimelineSource": overrides.get(
                "subtitleTimelineSource",
                job.get("overrides", {}).get("subtitleTimelineSource"),
            ),
        }
        effective = build_effective_analysis(job) or {}
        self.status_changed.emit(job_id, self.get_job_status(job_id))
        return effective

    def render_video(self, job_id: str, render_options: dict[str, Any]) -> None:
        if self._get_running_job_id():
            raise RuntimeError("A pipeline task is already running.")
        job = self.jobs.get(job_id)
        if not job or not job.get("analysis"):
            raise RuntimeError("Analyze the video before rendering.")
        effective_analysis = build_effective_analysis(job)
        if not effective_analysis:
            raise RuntimeError("Effective analysis is empty.")
        analysis_path = get_analysis_path(job_id)
        render_options_path = get_render_options_path(job_id)
        write_json(analysis_path, effective_analysis)
        write_json(
            render_options_path,
            {
                **render_options,
                "sourceLanguage": effective_analysis.get("sourceLanguage"),
                "voiceMapping": {
                    **{
                        speaker.get("speakerId"): speaker.get("voicePreset")
                        for speaker in effective_analysis.get("speakers", [])
                    },
                    **(render_options.get("voiceMapping") or {}),
                },
                "sourceSubtitleCleanupMode": render_options.get(
                    "sourceSubtitleCleanupMode"
                )
                or effective_analysis.get("subtitleRegion", {}).get("cleanupMode")
                or "localized_blur",
            },
        )
        self._start_process(
            job_id,
            [
                "render",
                "--analysis-json",
                str(analysis_path),
                "--render-options-json",
                str(render_options_path),
                "--output-json",
                str(get_render_result_path(job_id)),
            ],
            get_render_result_path(job_id),
            mode="render",
        )

    def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        job = self.jobs.get(job_id)
        if not job:
            return None
        return {
            "jobId": job_id,
            "inputPath": job.get("inputPath"),
            "status": job.get("status"),
            "phase": job.get("phase"),
            "step": job.get("step"),
            "progress": job.get("progress"),
            "logs": copy.deepcopy(job.get("logs") or []),
            "warnings": copy.deepcopy(job.get("warnings") or []),
            "lastError": job.get("lastError"),
            "hasAnalysis": bool(job.get("analysis")),
            "hasRenderResult": bool(job.get("renderResult")),
            "renderResult": copy.deepcopy(job.get("renderResult")),
        }

    def cancel_active_job(self) -> None:
        active_job_id = self._get_running_job_id()
        if not active_job_id:
            return
        job = self.jobs.get(active_job_id)
        process = job.get("process") if job else None
        if process is None:
            return
        job["cancelRequested"] = True
        process.kill()
        job["process"] = None
        job["status"] = "cancelled"
        append_job_log(job, "Job cancelled by user.", "warn")
        self.status_changed.emit(active_job_id, self.get_job_status(active_job_id))
        self.active_job_id = None

    def _start_process(
        self, job_id: str, args: list[str], result_file: Path, mode: str
    ) -> None:
        job = self.jobs[job_id]
        if not PIPELINE_PATH.exists():
            raise RuntimeError(f"Pipeline script not found: {PIPELINE_PATH}")
        process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        process.setProcessEnvironment(env)
        process.setProgram(str(PIPELINE_PYTHON))
        process.setArguments(["-u", str(PIPELINE_PATH), *args])
        process.setWorkingDirectory(str(ROOT))
        process.readyReadStandardOutput.connect(
            lambda: self._drain_output(job_id, "stdout")
        )
        process.readyReadStandardError.connect(
            lambda: self._drain_output(job_id, "stderr")
        )
        process.errorOccurred.connect(
            lambda error: self._handle_process_error(job_id, error)
        )
        process.finished.connect(
            lambda code, _status: self._handle_process_finished(
                job_id, code, result_file, mode
            )
        )
        job["process"] = process
        job["stdoutBuffer"] = ""
        job["stderrBuffer"] = ""
        job["status"] = "running"
        job["phase"] = mode
        job["step"] = "prepare"
        job["progress"] = 0.02
        job["lastError"] = None
        job["cancelRequested"] = False
        append_job_log(job, f"Starting {mode} pipeline.")
        self.active_job_id = job_id
        process.start()
        self.status_changed.emit(job_id, self.get_job_status(job_id))

    def _drain_output(self, job_id: str, stream: str) -> None:
        job = self.jobs.get(job_id)
        if not job or not job.get("process"):
            return
        process: QProcess = job["process"]
        if stream == "stdout":
            chunk = bytes(process.readAllStandardOutput()).decode(
                "utf-8", errors="ignore"
            )
            job["stdoutBuffer"] = job.get("stdoutBuffer", "") + chunk
            buffer_key = "stdoutBuffer"
        else:
            chunk = bytes(process.readAllStandardError()).decode(
                "utf-8", errors="ignore"
            )
            job["stderrBuffer"] = job.get("stderrBuffer", "") + chunk
            buffer_key = "stderrBuffer"
        lines = job[buffer_key].splitlines(keepends=False)
        if job[buffer_key] and not job[buffer_key].endswith(("\n", "\r")):
            job[buffer_key] = lines.pop() if lines else job[buffer_key]
        else:
            job[buffer_key] = ""
        for line in lines:
            self._handle_line(job_id, line.strip(), stream)

    def _handle_line(self, job_id: str, line: str, stream: str) -> None:
        if not line:
            return
        job = self.jobs[job_id]
        if stream == "stdout" and line.startswith("PROGRESS::"):
            try:
                payload = json.loads(line.split("PROGRESS::", 1)[1])
            except json.JSONDecodeError:
                append_job_log(job, f"Malformed progress payload: {line}", "warn")
                self.status_changed.emit(job_id, self.get_job_status(job_id))
                return
            job["phase"] = payload.get("phase", job.get("phase"))
            job["step"] = payload.get("step", job.get("step"))
            incoming_progress = float(payload.get("progress", job.get("progress") or 0))
            current_progress = float(job.get("progress") or 0)
            job["progress"] = max(current_progress, incoming_progress)
            job["status"] = payload.get("status", "running")
            append_job_log(
                job, payload.get("message") or f"{job['phase']}:{job['step']}"
            )
        elif stream == "stdout" and line.startswith("ERROR::"):
            try:
                payload = json.loads(line.split("ERROR::", 1)[1])
            except json.JSONDecodeError:
                payload = {"message": line}
            job["lastError"] = payload.get("message")
            append_job_log(job, payload.get("message", "Unknown error"), "error")
        elif stream == "stdout" and line.startswith("RESULT::"):
            append_job_log(job, "Pipeline reported a completed result.")
        else:
            if not should_capture_process_log_line(line, stream):
                return
            append_job_log(job, line, classify_process_log_line(line, stream))
        self.status_changed.emit(job_id, self.get_job_status(job_id))

    def _handle_process_error(self, job_id: str, error: QProcess.ProcessError) -> None:
        job = self.jobs.get(job_id)
        if not job or job.get("cancelRequested"):
            return
        process = job.get("process")
        try:
            error_message = (
                process.errorString() if process is not None else "Unknown process error."
            )
        except RuntimeError:
            error_message = f"Process error ({error})"
        if error == QProcess.ProcessError.FailedToStart:
            self._fail_job(job_id, f"Unable to start pipeline: {error_message}")
            return
        if error != QProcess.ProcessError.UnknownError:
            job["lastError"] = error_message
            append_job_log(job, error_message, "error")
            self.status_changed.emit(job_id, self.get_job_status(job_id))

    def _handle_process_finished(
        self, job_id: str, code: int, result_file: Path, mode: str
    ) -> None:
        job = self.jobs.get(job_id)
        if not job:
            return
        self._drain_output(job_id, "stdout")
        self._drain_output(job_id, "stderr")
        job["process"] = None
        self.active_job_id = None
        if job.get("cancelRequested"):
            job["status"] = "cancelled"
            job["progress"] = 0.0
            self.status_changed.emit(job_id, self.get_job_status(job_id))
            return
        if code != 0 and job.get("status") == "error" and job.get("lastError"):
            self.status_changed.emit(job_id, self.get_job_status(job_id))
            return
        if code != 0:
            message = job.get("lastError") or f"Pipeline failed with exit code {code}."
            self._fail_job(job_id, message)
            return
        try:
            payload = read_json(result_file)
        except FileNotFoundError:
            self._fail_job(
                job_id,
                f"Pipeline did not produce the expected result file: {result_file}",
            )
            return
        except json.JSONDecodeError as exc:
            self._fail_job(job_id, f"Pipeline returned invalid JSON: {exc}")
            return
        except OSError as exc:
            self._fail_job(job_id, f"Unable to read pipeline result: {exc}")
            return
        if not isinstance(payload, dict):
            self._fail_job(job_id, "Pipeline returned an unsupported result format.")
            return
        if mode == "analysis":
            job["analysis"] = payload
            job["warnings"] = payload.get("warnings") or []
            job["status"] = "success"
            job["progress"] = 1.0
            self.analysis_ready.emit(job_id, build_effective_analysis(job))
        else:
            job["renderResult"] = payload
            job["warnings"] = payload.get("warnings") or []
            job["status"] = "success"
            job["progress"] = 1.0
            self.render_ready.emit(job_id, payload)
        self.status_changed.emit(job_id, self.get_job_status(job_id))
