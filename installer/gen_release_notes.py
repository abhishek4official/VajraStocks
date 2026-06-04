"""
Generates release/ReleaseNotes.md from installer/release_notes_template.md.

Usage:
  python3 installer/gen_release_notes.py <version> <commits_file>

  version       — e.g. 1.0.0
  commits_file  — path to a file containing one commit line per row
"""

import sys
from pathlib import Path

version = sys.argv[1] if len(sys.argv) > 1 else "1.0.0"
commits_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/tmp/commits.txt")

commits = commits_file.read_text().strip() if commits_file.exists() else ""
commits = commits or "- Initial release"

template = Path("installer/release_notes_template.md").read_text()
notes = template.replace("VERSION_PLACEHOLDER", version)
notes = notes.replace("COMMITS_PLACEHOLDER", commits)

Path("release").mkdir(exist_ok=True)
Path("release/ReleaseNotes.md").write_text(notes)
print(f"Generated release/ReleaseNotes.md for v{version}")
