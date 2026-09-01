from __future__ import annotations

import json
from pathlib import Path


def set_active_workstream(project_root: Path, canonical_root: Path, workstream_id: str) -> None:
    path = project_root / ".talmudic" / "cache" / "active_workstream.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    resume_path = canonical_root / "workstreams" / workstream_id / "resume.json"
    path.write_text(
        json.dumps(
            {
                "workstream_id": workstream_id,
                "resume_path": str(resume_path.resolve()),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
