from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import runner


FAKE_COLAB = r'''#!PYTHON_EXECUTABLE
import json, os, pathlib, shutil, sys
args = sys.argv[1:]
if args and args[0].startswith("--auth="):
    args = args[1:]
command = args[0]
args = args[1:]
root = pathlib.Path(os.environ["FAKE_COLAB_STATE_DIR"])
root.mkdir(parents=True, exist_ok=True)
log = root / "calls.jsonl"
def record(kind, **values):
    with log.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"command": kind, **values}) + "\n")
if command == "usage":
    print("Current balance: 150.00 compute units")
    print("Usage rate: 0.00/hr")
    print("Active assignments: 0")
elif command == "version":
    print("google-colab-cli 0.7.4")
elif command == "new":
    record("new", args=args)
    print("Session created")
elif command == "stop":
    record("stop", args=args)
    print("Session stopped")
elif command == "upload":
    remote = args[-1]
    source = pathlib.Path(args[-2])
    remote_path = root / "remote" / remote.lstrip("/")
    remote_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, remote_path)
    record("upload", remote=remote, source=source.name)
elif command == "exec":
    envs = [args[i + 1] for i, value in enumerate(args[:-1]) if value == "--env"]
    values = dict(item.split("=", 1) for item in envs)
    output = values["VEO_OUTPUT_PATH"]
    record("exec", output=output, prompt=values.get("VEO_PROMPT_FILE"), model=values.get("VEO_MODEL"))
    if values.get("VEO_MODEL") == os.environ.get("FAKE_FAIL_MODEL"):
        print("simulated inference failure", file=sys.stderr)
        sys.exit(7)
    remote_path = root / "remote" / output.lstrip("/")
    remote_path.parent.mkdir(parents=True, exist_ok=True)
    remote_path.write_bytes(b"fake mp4 video bytes")
elif command == "download":
    remote = args[-2]
    target = pathlib.Path(args[-1])
    source = root / "remote" / remote.lstrip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    record("download", remote=remote, target=target.name)
else:
    print("unexpected fake command: " + command, file=sys.stderr)
    sys.exit(2)
'''

FAKE_FFPROBE = r'''#!PYTHON_EXECUTABLE
print('{"streams":[{"codec_type":"video"},{"codec_type":"audio"}]}')
'''


class VeoRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()

        # On Windows, create .bat or python wrapper if needed, or script
        if sys.platform == "win32":
            colab_bat = self.fake_bin / "colab.bat"
            colab_py = self.fake_bin / "colab_script.py"
            colab_py.write_text(FAKE_COLAB.replace("#!PYTHON_EXECUTABLE\n", ""), encoding="utf-8")
            colab_bat.write_text(f'@"{sys.executable}" "{colab_py}" %*\n', encoding="utf-8")

            ffprobe_bat = self.fake_bin / "ffprobe.bat"
            ffprobe_py = self.fake_bin / "ffprobe_script.py"
            ffprobe_py.write_text(FAKE_FFPROBE.replace("#!PYTHON_EXECUTABLE\n", ""), encoding="utf-8")
            ffprobe_bat.write_text(f'@"{sys.executable}" "{ffprobe_py}" %*\n', encoding="utf-8")
        else:
            for name, content in (("colab", FAKE_COLAB), ("ffprobe", FAKE_FFPROBE)):
                path = self.fake_bin / name
                path.write_text(content.replace("PYTHON_EXECUTABLE", sys.executable), encoding="utf-8")
                path.chmod(0o755)

        self.state_dir = self.root / "state"
        path_sep = ";" if sys.platform == "win32" else ":"
        self.env_patch = patch.dict(os.environ, {
            "PATH": f"{self.fake_bin}{path_sep}{os.environ.get('PATH', '')}",
            "FAKE_COLAB_STATE_DIR": str(self.state_dir),
        })
        self.env_patch.start()

    def tearDown(self) -> None:
        self.env_patch.stop()
        self.temp.cleanup()

    def make_manifest(self, job_count: int = 2) -> Path:
        jobs = []
        for index in range(job_count):
            img = self.root / f"ref-{index}.png"
            img.write_bytes(b"test image")
            jobs.append({
                "id": f"job-{index}",
                "title": f"Test Video {index}",
                "reference_images": [str(img)],
                "prompt": f"Cinematic shot of a character in scene {index}",
                "duration_seconds": 5,
                "aspect_ratio": "16:9",
                "resolution": "1080p",
                "output_name": f"clip_{index}",
            })
        manifest = self.root / "jobs.json"
        manifest.write_text(json.dumps({"jobs": jobs}), encoding="utf-8")
        return manifest

    def test_parse_usage(self) -> None:
        raw = "Current balance: 125.5 compute units\nUsage rate: 0.0/hr\nActive assignments: 1\n"
        parsed = runner.parse_usage(raw)
        self.assertEqual(parsed["balance"], 125.5)
        self.assertEqual(parsed["rate_per_hour"], 0.0)
        self.assertEqual(parsed["active_assignments"], 1)

    def test_prompt_composer(self) -> None:
        prompt = runner.compose_cinematic_prompt(
            subject="a futuristic sports car",
            action="speeding through a glowing cyber tunnel",
            setting="underground Neo-Tokyo",
            camera_movement="low tracking shot moving forward",
            lighting="high-contrast neon reflections",
            audio_description="roaring electric engine sound and techno beats",
        )
        self.assertIn("futuristic sports car", prompt)
        self.assertIn("Camera: low tracking shot moving forward", prompt)
        self.assertIn("Audio: roaring electric engine sound", prompt)

    def test_resolve_jobs_validation(self) -> None:
        out_dir = self.root / "outputs"
        manifest = self.make_manifest(job_count=2)
        jobs = runner.resolve_jobs(json.loads(manifest.read_text(encoding="utf-8")), out_dir)
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0]["duration_seconds"], 5)
        self.assertEqual(jobs[0]["aspect_ratio"], "16:9")

    def test_batch_run_success(self) -> None:
        manifest = self.make_manifest(job_count=2)
        out_dir = self.root / "outputs"
        progress_file = self.root / "progress.json"

        result = runner.run_batch(
            manifest,
            session=None,
            output_dir=out_dir,
            progress_path=progress_file,
            api_key="fake-test-key",
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["completed_count"], 2)

        # Check outputs exist
        for job in result["results"]:
            out_file = Path(job["output"])
            self.assertTrue(out_file.is_file())
            self.assertGreater(out_file.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
