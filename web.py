#!/usr/bin/env python3
"""Ratatoskr Web: compose and schedule WhatsApp Web messages in the browser.

    python web.py                  # http://127.0.0.1:8744

Pick recipients (recent ones are remembered), write the message with a live
preview, set repeats, delay and an optional send time, and either try it as a
dry run or send it. Jobs are listed with their status and the result for each
recipient; a scheduled job can be cancelled. Sending uses the same Chrome
profile and WhatsApp flow as `python main.py`, and the same limits: at most 20
messages per job, at least one second apart. This is not a spam tool.
Local only: see web_base.py.
"""
import argparse
import contextlib
import datetime as dt
import io
import json
import sys
import threading
import uuid
from pathlib import Path
from types import SimpleNamespace

import main as ratatoskr
from web_base import App, HttpError, field

HERE = Path(__file__).resolve().parent
MAX_JOBS = 30
MAX_RECENT = 12


class Courier:
    def __init__(self, state_file: Path, runner=ratatoskr.run):
        self.state_file = state_file
        self.runner = runner
        self.lock = threading.Lock()
        self.send_lock = threading.Lock()  # one browser at a time
        self.jobs = []

    # recent recipients are kept in a small JSON file next to the profile
    def recent(self):
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return [c for c in data.get("recent", []) if isinstance(c, str)][:MAX_RECENT]
        except (OSError, ValueError, AttributeError):
            return []

    def remember(self, contacts):
        recent = list(dict.fromkeys(contacts + self.recent()))[:MAX_RECENT]
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"recent": recent}, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.state_file)

    def view(self):
        with self.lock:
            return {"jobs": [j["public"] for j in self.jobs], "recent": self.recent(),
                    "limits": {"total": ratatoskr.MAX_TOTAL, "length": ratatoskr.MAX_LENGTH},
                    "version": ratatoskr.__version__}

    def create(self, contacts, text, repeat, delay, at, dry_run):
        contacts = list(dict.fromkeys(c.strip() for c in contacts if c.strip()))
        text = text.strip()
        if not contacts:
            raise HttpError(400, "add at least one recipient")
        if any(len(c) > 80 or "\n" in c for c in contacts):
            raise HttpError(400, "a recipient name is at most 80 characters on one line")
        if not text:
            raise HttpError(400, "the message is empty")
        if len(text) > ratatoskr.MAX_LENGTH:
            raise HttpError(400, f"the message is longer than {ratatoskr.MAX_LENGTH} characters")
        if repeat < 1 or len(contacts) * repeat > ratatoskr.MAX_TOTAL:
            raise HttpError(400, f"recipients × repeat must be 1 to {ratatoskr.MAX_TOTAL}: this is not a spam tool")
        if not 1 <= delay <= 60:
            raise HttpError(400, "delay: 1 to 60 seconds")
        send_at = None
        if at:
            try:
                send_at = ratatoskr.parse_at(at, dt.datetime.now())
            except ValueError:
                raise HttpError(400, "time: HH:MM, for example 21:30")
        job = {"cancel": threading.Event(), "public": {
            "id": uuid.uuid4().hex[:10], "contacts": contacts, "text": text, "repeat": repeat, "delay": delay,
            "dry_run": dry_run, "send_at": send_at.isoformat(timespec="minutes") if send_at else None,
            "created": dt.datetime.now().isoformat(timespec="seconds"),
            "state": "scheduled" if send_at else "queued", "log": [], "sent": 0}}
        with self.lock:
            self.jobs.insert(0, job)
            del self.jobs[MAX_JOBS:]
        if not dry_run:
            self.remember(contacts)
        threading.Thread(target=self._run, args=(job, send_at), daemon=True).start()
        return job["public"]

    def cancel(self, job_id):
        with self.lock:
            job = next((j for j in self.jobs if j["public"]["id"] == job_id), None)
        if not job:
            raise HttpError(404, "no such job")
        if job["public"]["state"] not in ("scheduled", "queued"):
            raise HttpError(409, "this job has already started")
        job["cancel"].set()
        job["public"]["state"] = "cancelled"

    def _run(self, job, send_at):
        pub = job["public"]
        if send_at:
            while (remaining := (send_at - dt.datetime.now()).total_seconds()) > 0:
                if job["cancel"].wait(min(remaining, 1.0)):
                    return
        if job["cancel"].is_set():
            return
        with self.send_lock:
            if job["cancel"].is_set():
                return
            pub["state"] = "running"
            args = SimpleNamespace(contacts=pub["contacts"], text=pub["text"], repeat=pub["repeat"],
                                   delay=pub["delay"], send_at=None, dry_run=pub["dry_run"], login_wait=60,
                                   profile=None)
            out = io.StringIO()
            try:
                with contextlib.redirect_stdout(out):
                    code = self.runner(args)
            except Exception as exc:  # the job shows the error; the server keeps running
                code = 1
                out.write(f"Failed: {type(exc).__name__}\n")
            pub["log"] = [ln for ln in out.getvalue().splitlines() if ln.strip()][-60:]
            pub["sent"] = sum(1 for ln in pub["log"] if ln.strip().startswith("sent to")) * pub["repeat"]
            pub["state"] = "dry-run" if pub["dry_run"] and code == 0 else ("sent" if code == 0 else "failed")
            pub["finished"] = dt.datetime.now().isoformat(timespec="seconds")


def build_app(courier: Courier) -> App:
    app = App(HERE / "static")

    @app.get("/api/state")
    def state(query):
        return courier.view()

    @app.post("/api/jobs")
    def create(body):
        contacts = body.get("contacts") if isinstance(body, dict) else None
        if not isinstance(contacts, list) or not all(isinstance(c, str) for c in contacts) or len(contacts) > 20:
            raise HttpError(400, "contacts must be a list of up to 20 names")
        courier.create(contacts, field(body, "text", max_len=ratatoskr.MAX_LENGTH),
                       field(body, "repeat", int, required=False, default=1),
                       field(body, "delay", float, required=False, default=1.5),
                       field(body, "at", required=False, max_len=5, default=""),
                       field(body, "dry_run", bool, required=False, default=True))
        return courier.view()

    @app.post(r"/api/jobs/(?P<job_id>[0-9a-f]{10})/cancel")
    def cancel(body, job_id):
        courier.cancel(job_id)
        return courier.view()

    return app


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Ratatoskr Web: WhatsApp Web messages from the browser (local only)")
    parser.add_argument("--port", type=int, default=8744)
    args = parser.parse_args(argv)
    state = Path(ratatoskr.default_profile_dir()).with_name(".ratatoskr_web.json")
    build_app(Courier(state)).serve(args.port, "Ratatoskr Web")
    return 0


if __name__ == "__main__":
    sys.exit(main())
