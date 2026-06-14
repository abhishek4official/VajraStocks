import sys
import re
from pathlib import Path
import subprocess

def main():
    if len(sys.argv) < 2:
        print("Usage: python python/scripts/update_version.py <new_version>")
        sys.exit(1)
        
    new_version = sys.argv[1]
    if not re.match(r"^\d+\.\d+\.\d+$", new_version):
        print(f"Error: Version '{new_version}' must be in X.Y.Z format (e.g. 1.3.0).")
        sys.exit(1)

    # 1. Read current version from python/pyproject.toml
    repo_root = Path(__file__).resolve().parents[2]
    pyproject_path = repo_root / "python" / "pyproject.toml"
    
    if not pyproject_path.exists():
        print(f"Error: Could not find pyproject.toml at {pyproject_path}")
        sys.exit(1)
        
    content = pyproject_path.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        print("Error: Could not extract current version from pyproject.toml")
        sys.exit(1)
        
    old_version = match.group(1)
    print(f"Updating version from {old_version} to {new_version}...")
    
    if old_version == new_version:
        print("Version is already up to date.")
        sys.exit(0)

    # Define target files and replacement patterns
    targets = [
        (
            repo_root / "python" / "pyproject.toml",
            [
                (rf'^version\s*=\s*"{re.escape(old_version)}"', f'version = "{new_version}"'),
            ]
        ),
        (
            repo_root / "python" / "src" / "stocks" / "api" / "main.py",
            [
                (rf'version\s*=\s*"{re.escape(old_version)}"', f'version="{new_version}"'),
                (rf'"version":\s*"{re.escape(old_version)}"', f'"version": "{new_version}"'),
            ]
        ),
        (
            repo_root / "frontend" / "package.json",
            [
                (rf'"version":\s*"{re.escape(old_version)}"', f'"version": "{new_version}"'),
            ]
        ),
        (
            repo_root / "frontend" / "src" / "App.tsx",
            [
                (rf'v{re.escape(old_version)}', f'v{new_version}'),
            ]
        ),
        (
            repo_root / "frontend" / "src" / "components" / "AboutPanel.tsx",
            [
                (rf'v{re.escape(old_version)}', f'v{new_version}'),
            ]
        ),
        (
            repo_root / "installer" / "windows" / "setup.iss",
            [
                (rf'#define AppVersion "{re.escape(old_version)}"', f'#define AppVersion "{new_version}"'),
            ]
        )
    ]

    for file_path, replacements in targets:
        if not file_path.exists():
            print(f"Warning: File {file_path} not found. Skipping.")
            continue
            
        print(f"Updating {file_path.relative_to(repo_root)}...")
        txt = file_path.read_text(encoding="utf-8")
        
        for pattern, repl in replacements:
            regex = re.compile(pattern, re.MULTILINE)
            txt = regex.sub(repl, txt)
            
        file_path.write_text(txt, encoding="utf-8")

    # Run uv sync in python directory to update uv.lock
    python_dir = repo_root / "python"
    print("Running 'uv sync' to regenerate lockfile...")
    try:
        subprocess.run(["uv", "sync"], cwd=str(python_dir), check=True)
        print("Successfully regenerated lockfile.")
    except Exception as e:
        print(f"Warning: Could not run 'uv sync': {e}. Please run it manually.")

    print(f"Version update complete: {new_version}")

if __name__ == "__main__":
    main()
