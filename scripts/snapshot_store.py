import argparse
import hashlib
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "backend" / "storage" / "vectors.sqlite"
SNAPSHOT_DIR = ROOT / "evals" / "snapshots"


def get_store_hash(db_path: Path = DEFAULT_DB_PATH) -> str:
    """Computes SHA-256 hash of the SQLite database file."""
    if not db_path.exists():
        return "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"  # Empty file SHA256
    hasher = hashlib.sha256()
    with open(db_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def snapshot_store(label: str = "eval", db_path: Path = DEFAULT_DB_PATH) -> tuple[Path, str]:
    """Snapshots the SQLite store to evals/snapshots/ and returns (snapshot_path, sha256_hash)."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    current_hash = get_store_hash(db_path)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    snapshot_filename = f"store_{timestamp}_{label}_{current_hash[:8]}.sqlite"
    snapshot_path = SNAPSHOT_DIR / snapshot_filename

    if db_path.exists():
        shutil.copy2(db_path, snapshot_path)
    else:
        # Create empty placeholder snapshot
        snapshot_path.touch()

    return snapshot_path, current_hash


def reset_store(db_path: Path = DEFAULT_DB_PATH) -> str:
    """
    Resets the lessons store to a pristine, clean state before benchmark runs.
    Keeps any verified knowledge entries but purges candidate or transient lessons.
    """
    if db_path.exists():
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # Check if rag_documents exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rag_documents';")
            if cursor.fetchone():
                cursor.execute("DELETE FROM rag_documents WHERE collection = 'lessons';")
                cursor.execute("DELETE FROM rag_documents WHERE collection = 'traces';")
                conn.commit()
            cursor.execute("VACUUM;")
            conn.commit()

    return get_store_hash(db_path)


def main():
    parser = argparse.ArgumentParser(description="Lesson Store Hygiene & Snapshot Manager")
    parser.add_argument("--snapshot", action="store_true", help="Create a timestamped store snapshot")
    parser.add_argument("--reset", action="store_true", help="Reset store lessons to clean state")
    parser.add_argument("--hash", action="store_true", help="Print current store SHA256 hash")
    parser.add_argument("--label", type=str, default="pre_eval", help="Snapshot label")
    args = parser.parse_args()

    if args.reset:
        snap_path, pre_hash = snapshot_store(label="pre_reset")
        print(f"Pre-reset snapshot saved to: {snap_path} (hash: {pre_hash})")
        post_hash = reset_store()
        print(f"Store reset to clean state. Post-reset hash: {post_hash}")
    elif args.snapshot:
        snap_path, store_hash = snapshot_store(label=args.label)
        print(f"Snapshot created: {snap_path} (hash: {store_hash})")
    elif args.hash:
        print(f"Store SHA256: {get_store_hash()}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
