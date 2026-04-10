#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path


def run_capture(args: list[str], cwd: Path) -> bytes:
    proc = subprocess.run(args, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr.decode("utf-8", errors="ignore"))
        raise SystemExit(proc.returncode)
    return proc.stdout


def _full_fingerprint(repo_root: Path) -> str:
    """Full fingerprint: staged + unstaged + untracked + file contents."""
    sha = hashlib.sha256()

    status = run_capture(["git", "status", "--porcelain=v1", "--untracked-files=all"], repo_root)
    worktree_diff = run_capture(["git", "diff", "--no-ext-diff", "--binary"], repo_root)
    index_diff = run_capture(["git", "diff", "--no-ext-diff", "--cached", "--binary"], repo_root)
    untracked = run_capture(["git", "ls-files", "--others", "--exclude-standard", "-z"], repo_root)

    sha.update(b"--STATUS--\n")
    sha.update(status)
    sha.update(b"\n--WORKTREE-DIFF--\n")
    sha.update(worktree_diff)
    sha.update(b"\n--INDEX-DIFF--\n")
    sha.update(index_diff)
    sha.update(b"\n--UNTRACKED-CONTENTS--\n")

    for raw_path in sorted(part for part in untracked.split(b"\x00") if part):
        rel_path = raw_path.decode("utf-8", errors="surrogateescape")
        path = repo_root / rel_path
        sha.update(rel_path.encode("utf-8", errors="surrogateescape"))
        sha.update(b"\n")
        try:
            sha.update(path.read_bytes())
        except FileNotFoundError:
            sha.update(b"<missing>")
        sha.update(b"\n--NEXT-UNTRACKED--\n")

    return sha.hexdigest()


def _staged_only_fingerprint(repo_root: Path) -> str:
    """Reduced fingerprint for worktrees: staged diff + staged paths + HEAD + branch + worktree_id."""
    sha = hashlib.sha256()

    staged_diff = run_capture(["git", "diff", "--no-ext-diff", "--cached", "--binary"], repo_root)
    staged_paths = run_capture(["git", "diff", "--cached", "--name-only"], repo_root)
    head = run_capture(["git", "rev-parse", "HEAD"], repo_root)
    branch = run_capture(["git", "branch", "--show-current"], repo_root)
    git_dir = run_capture(["git", "rev-parse", "--git-dir"], repo_root)

    # worktree_id: basename of git-dir (e.g. "dev-codex-web-build-hotfix")
    worktree_id = Path(git_dir.decode("utf-8", errors="ignore").strip()).name

    sha.update(b"--STAGED-DIFF--\n")
    sha.update(staged_diff)
    sha.update(b"\n--STAGED-PATHS--\n")
    sha.update(staged_paths)
    sha.update(b"\n--HEAD--\n")
    sha.update(head)
    sha.update(b"\n--BRANCH--\n")
    sha.update(branch)
    sha.update(b"\n--WORKTREE-ID--\n")
    sha.update(worktree_id.encode("utf-8"))

    return sha.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--staged-only", action="store_true",
                        help="Reduced fingerprint for worktrees: staged diff + HEAD + branch + worktree_id")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()

    if args.staged_only:
        print(_staged_only_fingerprint(repo_root))
    else:
        print(_full_fingerprint(repo_root))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
