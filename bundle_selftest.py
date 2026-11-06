"""Exercise the frozen GUI worker during release validation, without dialogs."""
import json
import os
import traceback
from pathlib import Path


def run(app_class):
    root = Path(os.environ["NCM_CONVERTER_SELF_TEST"])
    report = {"result": "failed", "checks": []}
    app = None
    try:
        app = app_class()
        app.withdraw()
        for input_type, count in (("cache", 1), ("ncm", 2)):
            for mode in ("source", "mp3", "flac"):
                output = root / f"output-{input_type}-{mode}"
                if input_type == "cache":
                    meta = output / "work/metadata"
                    meta.mkdir(parents=True, exist_ok=True)
                    (meta / "1.json").write_text(json.dumps({"name": "Fixture", "artist": "CI", "album": "CI"}), encoding="utf-8")
                app._worker(root / input_type, output, 0, True, mode, input_type)
                messages = []
                while not app.messages.empty():
                    messages.append(app.messages.get())
                summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
                report["checks"].append({"type": input_type, "mode": mode, "summary": summary, "messages": messages})
                assert summary["ready"] == count and summary["failed"] == 0, summary
                if input_type == "ncm":
                    from mutagen.flac import FLAC
                    from mutagen.id3 import ID3
                    catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
                    for track in catalog["tracks"]:
                        audio = Path(track["audio_path"])
                        if audio.suffix == ".mp3":
                            tags = ID3(audio)
                            assert str(tags["TIT2"]) == "NCM 测试" and tags.getall("APIC")
                        elif audio.suffix == ".flac":
                            tags = FLAC(audio)
                            assert tags["title"] == ["NCM 测试"] and tags.pictures
        report["result"] = "passed"
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        if app is not None:
            app.destroy()
        (root / "bundle-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return int(report["result"] != "passed")
