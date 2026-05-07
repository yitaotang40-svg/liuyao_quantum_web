#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import importlib.util
import json
import mimetypes
import os
import socket
import sys
import threading
import time
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import unquote, urlparse


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
RESULTS_DIR = APP_DIR / "results"
LIUYAO_SCRIPT = Path("/Users/yitao/Downloads/ibm_liuyao_qiskit.py")

JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()
ACTIVE_STATUSES = {
    "CREATED",
    "CONNECTING",
    "SELECTING_BACKEND",
    "TRANSPILING",
    "SUBMITTING",
    "QUEUED",
    "INITIALIZING",
    "VALIDATING",
    "RUNNING",
    "READING_RESULT",
}


def load_liuyao_module():
    if not LIUYAO_SCRIPT.exists():
        raise FileNotFoundError(f"找不到起卦脚本: {LIUYAO_SCRIPT}")

    spec = importlib.util.spec_from_file_location("ibm_liuyao_qiskit", LIUYAO_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载起卦脚本: {LIUYAO_SCRIPT}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


LIUYAO = load_liuyao_module()


def now_label() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def set_job(run_id: str, **updates: Any) -> None:
    with JOBS_LOCK:
        job = JOBS.setdefault(run_id, {})
        job.update(updates)
        job["updated_at"] = now_label()


def get_job(run_id: str) -> dict[str, Any] | None:
    with JOBS_LOCK:
        job = JOBS.get(run_id)
        if job is None:
            return None
        return json.loads(json.dumps(job, ensure_ascii=False))


def active_job_locked() -> dict[str, Any] | None:
    for job in JOBS.values():
        if job.get("status") in ACTIVE_STATUSES:
            return job
    return None


def get_active_job() -> dict[str, Any] | None:
    with JOBS_LOCK:
        job = active_job_locked()
        if job is None:
            return None
        return json.loads(json.dumps(job, ensure_ascii=False))


def runtime_status_name(status: Any) -> str:
    if hasattr(status, "name"):
        return str(status.name).upper()
    text = str(status).strip()
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    return text.upper()


def service_args(backend_name: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        token=None,
        instance=None,
        channel=os.getenv("IBM_QUANTUM_CHANNEL", "ibm_quantum_platform"),
        backend=backend_name,
        save_account=False,
        optimization_level=1,
        print_circuit=False,
        calibrate_shots=0,
        output=None,
    )


def compact_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "backend": payload["backend"],
        "job_id": payload["job_id"],
        "yao_records": [
            {
                "yao": rec["yao"],
                "yao_name": rec["yao_name"],
                "yao_type": rec["yao_type"],
                "moving": rec["moving"],
            }
            for rec in payload["yao_records"]
        ],
        "dong_yao": payload["dong_yao"],
        "dong_yao_detail": payload["dong_yao_detail"],
    }


def run_divination(run_id: str, backend_name: str | None) -> None:
    output_path = RESULTS_DIR / f"liuyao_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{run_id[:8]}.json"
    try:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        set_job(run_id, status="CONNECTING", status_label="连接 IBM Quantum", backend=backend_name or "自动选择")
        args = service_args(backend_name)
        service = LIUYAO.make_service(args)

        set_job(run_id, status="SELECTING_BACKEND", status_label="选择量子机")
        backend = LIUYAO.choose_backend(service, backend_name)
        set_job(run_id, backend=backend.name)

        set_job(run_id, status="TRANSPILING", status_label="编译量子电路")
        qc = LIUYAO.build_single_yao_circuit(register_name="meas")
        pm = LIUYAO.generate_preset_pass_manager(backend=backend, optimization_level=args.optimization_level)
        isa_circuit = pm.run(qc)
        sampler = LIUYAO.Sampler(mode=backend)

        set_job(run_id, status="SUBMITTING", status_label="提交到量子机")
        pubs = [isa_circuit for _ in range(6)]
        runtime_job = sampler.run(pubs, shots=1)
        job_id = runtime_job.job_id()
        set_job(run_id, status="QUEUED", status_label="等待 IBM Runtime", job_id=job_id)

        terminal_states = {"DONE", "ERROR", "CANCELLED", "CANCELED"}
        while True:
            raw_status = runtime_status_name(runtime_job.status())
            if raw_status in {"QUEUED", "INITIALIZING", "VALIDATING", "RUNNING"}:
                set_job(run_id, status=raw_status, status_label=f"IBM 状态: {raw_status}")
            if raw_status in terminal_states:
                break
            time.sleep(2)

        if raw_status != "DONE":
            raise RuntimeError(f"IBM Runtime 作业未完成: {raw_status}")

        set_job(run_id, status="READING_RESULT", status_label="读取测量结果")
        result = runtime_job.result()

        records = []
        for idx, pub_result in enumerate(result, start=1):
            bitstrings = pub_result.data.meas.get_bitstrings()
            if len(bitstrings) != 1:
                raise RuntimeError(f"第 {idx} 爻返回 {len(bitstrings)} 条 bitstring，预期 1 条。")
            bits = bitstrings[0]
            mapped = LIUYAO.map_bitstring_to_yao(bits, one_means_back=True)
            records.append(
                LIUYAO.YaoRecord(
                    yao=idx,
                    yao_name=LIUYAO.YAO_NAMES[idx],
                    bits=bits,
                    backs=mapped["backs"],
                    symbol=mapped["symbol"],
                    yao_type=mapped["yao_type"],
                    moving=mapped["moving"],
                    ben=mapped["ben"],
                    bian=mapped["bian"],
                )
            )

        payload = LIUYAO.build_result_payload(records, backend_name=backend.name, job_id=job_id)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        set_job(
            run_id,
            status="DONE",
            status_label="完成",
            output_path=str(output_path),
            result=compact_result(payload),
        )
    except Exception as exc:
        set_job(run_id, status="ERROR", status_label="出错", error=str(exc), output_path=str(output_path))


class Handler(SimpleHTTPRequestHandler):
    server_version = "LiuYaoQuantumWeb/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def json_response(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_static(self, send_body: bool = True) -> bool:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/" or path == "":
            path = "/index.html"

        target = (STATIC_DIR / path.lstrip("/")).resolve()
        if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.exists() or not target.is_file():
            return False

        data = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if send_body:
            self.wfile.write(data)
        return True

    def do_HEAD(self) -> None:
        if not self.serve_static(send_body=False):
            self.send_error(HTTPStatus.NOT_FOUND.value)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT.value)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/active-job":
            self.json_response({"job": get_active_job()})
            return

        if path.startswith("/api/jobs/"):
            run_id = path.rsplit("/", 1)[-1]
            job = get_job(run_id)
            if job is None:
                self.json_response({"error": "找不到这次起卦。"}, HTTPStatus.NOT_FOUND)
                return
            self.json_response(job)
            return

        if not self.serve_static(send_body=True):
            self.send_error(HTTPStatus.NOT_FOUND.value)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/divinations":
            self.send_error(HTTPStatus.NOT_FOUND.value)
            return

        content_length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {}

        backend_name = str(body.get("backend") or "").strip() or None
        run_id = uuid.uuid4().hex
        with JOBS_LOCK:
            active_job = active_job_locked()
            if active_job is not None:
                self.json_response(
                    {
                        "run_id": active_job["run_id"],
                        "already_running": True,
                        "message": "已有一卦正在运行。",
                    },
                    HTTPStatus.CONFLICT,
                )
                return

            JOBS[run_id] = {
                "run_id": run_id,
                "status": "CREATED",
                "status_label": "准备起卦",
                "backend": backend_name or "自动选择",
                "job_id": "",
                "created_at": now_label(),
                "updated_at": now_label(),
            }

        worker = threading.Thread(target=run_divination, args=(run_id, backend_name), daemon=True)
        worker.start()
        self.json_response({"run_id": run_id})


def port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) != 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IBM Quantum 六爻起卦本地网站")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not port_is_free(args.host, args.port):
        raise SystemExit(f"{args.host}:{args.port} 已被占用，请换一个端口。")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"六爻量子起卦网站已启动: http://{args.host}:{args.port}")
    print("按 Ctrl+C 停止。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
