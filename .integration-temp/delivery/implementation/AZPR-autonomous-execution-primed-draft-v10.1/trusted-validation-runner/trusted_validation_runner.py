#!/usr/bin/env python3
"""Trusted immutable-container validator for AZPR.

Install this file outside the agent-writable repository and pin its SHA-256 in
controller.config.json. It snapshots the current worktree into a disposable
regular-file-only tree, mounts that snapshot read-only in a pinned container,
and writes only bounded evidence outside the repository.
"""
from __future__ import annotations

import argparse
import hashlib
import fcntl
import tarfile
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Iterable

import trusted_installation as ti

CONTROL = set(range(0, 32)) | {127}
DEFAULT_OUTPUT_BYTE_LIMIT = 4 * 1024 * 1024
DEFAULT_FILE_COUNT_LIMIT = 10000
DEFAULT_DEPTH_LIMIT = 40


class RunnerError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_name(value: str) -> None:
    if not value or value.startswith("/") or ".." in Path(value).parts:
        raise RunnerError(f"Unsafe relative path: {value!r}")
    if any(ord(char) in CONTROL for char in value):
        raise RunnerError(f"Control-character path rejected: {value!r}")


def no_symlink_ancestors(path: Path) -> None:
    absolute = path.absolute()
    cursor = Path(absolute.parts[0])
    for part in absolute.parts[1:]:
        cursor = cursor / part
        try:
            info = os.lstat(cursor)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode):
            raise RunnerError(f"Symlink ancestry rejected: {cursor}")


def _trusted_git() -> str:
    if ti.production_mode():
        try: return str(ti.load_installation().component("git_binary"))
        except ti.InstallationError as exc: raise RunnerError(str(exc)) from exc
    value=os.environ.get("AZPR_TRUSTED_GIT","/usr/bin/git"); path=Path(value).absolute(); no_symlink_ancestors(path)
    st=os.stat(path)
    if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o022: raise RunnerError("development Git binary is unsafe")
    return str(path)


def _git_env(extra: dict[str,str] | None = None) -> dict[str,str]:
    env={"PATH":"/usr/bin:/bin","HOME":"/nonexistent","LANG":"C.UTF-8","LC_ALL":"C.UTF-8","GIT_CONFIG_NOSYSTEM":"1","GIT_CONFIG_GLOBAL":"/dev/null","GIT_CONFIG_SYSTEM":"/dev/null","GIT_TERMINAL_PROMPT":"0","GIT_PAGER":"cat","GIT_OPTIONAL_LOCKS":"0"}
    if extra: env.update(extra)
    return env


def _git_run(source:Path,argv:list[str],*,env_extra:dict[str,str]|None=None,stdout=None)->subprocess.CompletedProcess:
    command=[_trusted_git(),"-c","core.hooksPath=/dev/null","-c","core.fsmonitor=false","-c","commit.gpgSign=false","-c","credential.helper=",*argv]
    result=run_group(command,120,output_byte_limit=16*1024*1024,cwd=source,env=_git_env(env_extra))
    if result.returncode!=0: raise RunnerError(f"trusted Git snapshot command failed: {argv}: {result.stderr[-1000:]!r}")
    if stdout is not None:
        value=result.stdout.encode('utf-8') if isinstance(result.stdout,str) else result.stdout
        stdout.write(value); stdout.flush()
        return subprocess.CompletedProcess(command,result.returncode,b'',result.stderr.encode('utf-8'))
    return subprocess.CompletedProcess(command,result.returncode,result.stdout.encode('utf-8'),result.stderr.encode('utf-8'))


def _git_paths(source: Path, argv: list[str]) -> list[str]:
    result=_git_run(source,argv)
    if result.stdout and not result.stdout.endswith(b"\0"): raise RunnerError(f"trusted Git path query was not NUL terminated: {argv}")
    values=[]
    for raw in result.stdout[:-1].split(b"\0") if result.stdout else []:
        value=raw.decode("utf-8",errors="strict"); safe_name(value); values.append(value)
    return values

def _filesystem_paths(source: Path) -> list[str]:
    """Inventory all non-Git-admin paths without honoring ignore metadata."""
    root=source.resolve(); values=set()
    for current,dirs,files in os.walk(root,topdown=True,followlinks=False):
        current_path=Path(current)
        if current_path==root:
            if ".git" in dirs: dirs.remove(".git")
            if ".git" in files: files.remove(".git")
        else:
            if ".git" in dirs:
                values.add((current_path/".git").relative_to(root).as_posix());dirs.remove(".git")
            if ".git" in files:
                values.add((current_path/".git").relative_to(root).as_posix());files.remove(".git")
        dirs[:]=sorted(dirs)
        for name in sorted(files):
            rel=(current_path/name).relative_to(root).as_posix();safe_name(rel);values.add(rel)
        for name in list(dirs):
            candidate=current_path/name
            try:
                if stat.S_ISLNK(os.lstat(candidate).st_mode):
                    values.add(candidate.relative_to(root).as_posix());dirs.remove(name)
            except FileNotFoundError:
                values.add(candidate.relative_to(root).as_posix())
    return sorted(values)

def _worktree_paths(source: Path) -> list[str]:
    tracked=set(_git_paths(source,["ls-files","-z"]))
    changed=set(_git_paths(source,["diff","--name-only","-z","HEAD","--"]))
    changed.update(path for path in _filesystem_paths(source) if path not in tracked)
    return sorted(changed)

def _read_relative_regular(root_fd:int, relative:str, *, byte_limit:int) -> tuple[bytes,int,tuple[int,int,int,int]] | None:
    parts=Path(relative).parts; current=root_fd; opened=[]
    try:
        for part in parts[:-1]:
            flags=os.O_RDONLY|getattr(os,"O_DIRECTORY",0)|getattr(os,"O_NOFOLLOW",0)
            try: nxt=os.open(part,flags,dir_fd=current)
            except FileNotFoundError:return None
            info=os.fstat(nxt)
            if not stat.S_ISDIR(info.st_mode):raise RunnerError(f"snapshot ancestor is not a directory: {relative}")
            opened.append(nxt);current=nxt
        try: fd=os.open(parts[-1],os.O_RDONLY|getattr(os,"O_NOFOLLOW",0),dir_fd=current)
        except FileNotFoundError:return None
        except OSError as exc:raise RunnerError(f"symlink or unsafe changed path rejected: {relative}") from exc
        try:
            before=os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>byte_limit:raise RunnerError(f"unsafe or oversized changed file: {relative}")
            data=bytearray()
            while True:
                chunk=os.read(fd,65536)
                if not chunk:break
                data.extend(chunk)
                if len(data)>byte_limit:raise RunnerError(f"changed file exceeds size limit: {relative}")
            after=os.fstat(fd)
            identity=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)
            if identity!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise RunnerError(f"changed file mutated during snapshot: {relative}")
            current_info=os.stat(parts[-1],dir_fd=current,follow_symlinks=False)
            if identity!=(current_info.st_dev,current_info.st_ino,current_info.st_size,current_info.st_mtime_ns):raise RunnerError(f"changed file identity swapped during snapshot: {relative}")
            return bytes(data),before.st_mode,identity
        finally:os.close(fd)
    finally:
        for fd in reversed(opened):os.close(fd)

def _write_snapshot_file(destination:Path, relative:str, data:bytes, source_mode:int)->None:
    target=destination/relative; target.parent.mkdir(parents=True,exist_ok=True)
    no_symlink_ancestors(target.parent)
    flags=os.O_WRONLY|os.O_CREAT|os.O_TRUNC|getattr(os,"O_NOFOLLOW",0);fd=os.open(target,flags,0o700 if source_mode&0o111 else 0o600)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise RunnerError(f"unsafe snapshot destination: {relative}")
        view=memoryview(data)
        while view:view=view[os.write(fd,view):]
        os.fsync(fd)
    finally:os.close(fd)

def snapshot_repository(
    source: Path, destination: Path, *, file_count_limit: int = DEFAULT_FILE_COUNT_LIMIT,
    depth_limit: int = DEFAULT_DEPTH_LIMIT, changed_file_byte_limit:int=128*1024*1024,
    total_changed_byte_limit:int=512*1024*1024, include_identity:bool=False,
) -> str | dict[str,str]:
    """Archive immutable HEAD then overlay the bounded diff through no-follow FDs."""
    source=source.resolve();no_symlink_ancestors(source)
    git_dir_result=_git_run(source,["rev-parse","--git-dir"]);git_dir=Path(git_dir_result.stdout.decode().strip())
    if not git_dir.is_absolute():git_dir=(source/git_dir).resolve()
    lock_fd=os.open(git_dir/"azpr-validation.lock",os.O_RDWR|os.O_CREAT|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        fcntl.flock(lock_fd,fcntl.LOCK_EX)
        head=_git_run(source,["rev-parse","HEAD"]).stdout.decode().strip()
        tree=_git_run(source,["rev-parse","HEAD^{tree}"]).stdout.decode().strip()
        listing=_git_run(source,["ls-tree","-r","-z",tree]).stdout
        entries=listing[:-1].split(b"\0") if listing else []
        if len(entries)>file_count_limit:raise RunnerError("validation snapshot exceeds file-count limit")
        for raw in entries:
            meta,name=raw.split(b"\t",1);mode,kind,_obj=meta.split(b" ",2);rel=name.decode("utf-8","strict");safe_name(rel)
            if len(Path(rel).parts)>depth_limit:raise RunnerError(f"snapshot path exceeds depth limit: {rel}")
            if mode in {b"120000",b"160000"} or kind!=b"blob":raise RunnerError(f"baseline contains symlink/submodule/non-blob: {rel}")
        with tempfile.TemporaryDirectory(prefix="azpr-head-archive-") as td:
            tar_path=Path(td)/"head.tar"
            with tar_path.open("wb") as out:_git_run(source,["archive","--format=tar",head],stdout=out)
            with tarfile.open(tar_path,"r:") as archive:
                for member in archive.getmembers():
                    if member.name.rstrip():safe_name(member.name.rstrip("/"))
                    if member.issym() or member.islnk() or member.isdev() or member.isfifo():raise RunnerError(f"unsafe archive member: {member.name}")
                archive.extractall(destination,filter="data")
        paths_before=_worktree_paths(source)
        ignored_paths=_git_paths(source,["ls-files","--others","--ignored","--exclude-standard","-z"])
        if ignored_paths:
            raise RunnerError(f"ignored worktree artifacts are forbidden and must be removed before validation: {ignored_paths[:20]}")
        if len(paths_before)+len(entries)>file_count_limit:raise RunnerError("candidate snapshot exceeds file-count limit")
        root_fd=os.open(source,os.O_RDONLY|getattr(os,"O_DIRECTORY",0));fingerprints={};total=0
        try:
            for rel in paths_before:
                safe_name(rel)
                if len(Path(rel).parts)>depth_limit:raise RunnerError(f"changed path exceeds depth limit: {rel}")
                record=_read_relative_regular(root_fd,rel,byte_limit=changed_file_byte_limit)
                target=destination/rel
                if record is None:
                    if target.exists():
                        info=os.lstat(target)
                        if not stat.S_ISREG(info.st_mode):raise RunnerError(f"unsafe deletion target in snapshot: {rel}")
                        target.unlink()
                    fingerprints[rel]=None;continue
                data,mode,identity=record;total+=len(data)
                if total>total_changed_byte_limit:raise RunnerError("candidate diff exceeds changed-byte limit")
                fingerprints[rel]=(hashlib.sha256(data).hexdigest(),mode&0o111,identity)
                _write_snapshot_file(destination,rel,data,mode)
            if _worktree_paths(source)!=paths_before:raise RunnerError("worktree path set changed during snapshot")
            for rel,expected in fingerprints.items():
                current=_read_relative_regular(root_fd,rel,byte_limit=changed_file_byte_limit)
                if expected is None:
                    if current is not None:raise RunnerError(f"deleted path reappeared during snapshot: {rel}")
                else:
                    if current is None or (hashlib.sha256(current[0]).hexdigest(),current[1]&0o111,current[2])!=expected:raise RunnerError(f"changed path mutated during snapshot: {rel}")
        finally:os.close(root_fd)
        for current,dirs,files in os.walk(destination,topdown=False):
            for name in files:
                path=Path(current)/name;info=os.lstat(path)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise RunnerError(f"unsafe extracted snapshot file: {path}")
                os.chmod(path,0o555 if info.st_mode&0o111 else 0o444)
            for name in dirs:os.chmod(Path(current)/name,0o555)
            os.chmod(current,0o555)
        digest=snapshot_repository_digest(destination)
        identity={"snapshot_sha256":digest,"source_commit":head,"source_tree":tree}
        return identity if include_identity else digest
    finally:
        fcntl.flock(lock_fd,fcntl.LOCK_UN);os.close(lock_fd)


def directory_stats(root: Path, *, file_limit: int = DEFAULT_FILE_COUNT_LIMIT, depth_limit: int = DEFAULT_DEPTH_LIMIT) -> tuple[int, int]:
    total = 0
    count = 0
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        rel = Path(current).relative_to(root)
        if len(rel.parts) > depth_limit:
            raise RunnerError("Evidence directory depth limit exceeded.")
        count += len(dirs) + len(files)
        if count > file_limit:
            raise RunnerError("Evidence inode/file-count limit exceeded.")
        for name in files:
            path = Path(current) / name
            info = os.lstat(path)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise RunnerError(f"Unsafe evidence file: {path}")
            total += info.st_size
    return total, count


def directory_size(root: Path) -> int:
    return directory_stats(root)[0]


def run_group(
    argv: list[str],
    timeout: int,
    *,
    watch_path: Path | None = None,
    max_watch_bytes: int | None = None,
    output_byte_limit: int = DEFAULT_OUTPUT_BYTE_LIMIT,
    file_count_limit: int = DEFAULT_FILE_COUNT_LIMIT,
    depth_limit: int = DEFAULT_DEPTH_LIMIT,
    cwd: Path | None = None,
    env: dict[str,str] | None = None,
) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="azpr-runner-output-") as capture_dir:
        stdout_path = Path(capture_dir) / "stdout"
        stderr_path = Path(capture_dir) / "stderr"
        with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
            process = subprocess.Popen(
                argv, stdin=subprocess.DEVNULL, stdout=stdout_handle, stderr=stderr_handle,
                start_new_session=True, cwd=cwd,
                env=env or {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "HOME": "/nonexistent"},
            )
            stop = threading.Event()
            exceeded: list[str] = []

            def monitor() -> None:
                while not stop.wait(0.1):
                    try:
                        if stdout_path.exists() and stdout_path.stat().st_size > output_byte_limit:
                            exceeded.append("stdout")
                        if stderr_path.exists() and stderr_path.stat().st_size > output_byte_limit:
                            exceeded.append("stderr")
                        if watch_path is not None and max_watch_bytes is not None:
                            size, _count = directory_stats(watch_path, file_limit=file_count_limit, depth_limit=depth_limit)
                            if size > max_watch_bytes:
                                exceeded.append("evidence")
                    except (RunnerError, OSError):
                        exceeded.append("evidence-topology")
                    if exceeded:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        return

            watcher = threading.Thread(target=monitor, name="azpr-output-quota", daemon=True)
            watcher.start()
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=10)
                raise RunnerError("Container validation timed out; the full process group was killed.") from exc
            finally:
                stop.set()
                watcher.join(timeout=1)
        if exceeded:
            raise RunnerError(f"Validation process exceeded bounded output/evidence limits: {exceeded[0]}")
        stdout = stdout_path.read_bytes()
        stderr = stderr_path.read_bytes()
        if len(stdout) > output_byte_limit or len(stderr) > output_byte_limit:
            raise RunnerError("Validation output exceeded its byte limit.")
        return subprocess.CompletedProcess(
            argv, process.returncode, stdout.decode("utf-8", "replace"), stderr.decode("utf-8", "replace")
        )


def inspect_image(engine: str, image: str, expected_digest: str) -> None:
    result = run_group([engine, "image", "inspect", image, "--format", "{{json .RepoDigests}}"], 60)
    if result.returncode != 0:
        raise RunnerError(f"Could not inspect pinned image: {result.stderr[-2000:]}")
    try:
        digests = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise RunnerError("Container engine returned invalid image metadata.") from exc
    if not isinstance(digests, list) or not any(str(value).endswith("@" + expected_digest) for value in digests):
        raise RunnerError("Local container image does not match the configured digest.")


def build_container_command(args: argparse.Namespace, snapshot: Path, evidence: Path, command: list[str]) -> list[str]:
    uid = os.getuid()
    gid = os.getgid()
    fsize_blocks = max(1, int(args.file_size_limit) // 512)
    return [
        args.engine,
        "run",
        "--rm",
        "--network=none",
        "--ipc=none",
        "--read-only",
        "--init",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit", str(args.pids_limit),
        "--cpus", str(args.cpus),
        "--memory", str(args.memory),
        "--memory-swap", str(args.memory),
        "--ulimit", f"nproc={args.pids_limit}:{args.pids_limit}",
        "--ulimit", "nofile=1024:1024",
        "--ulimit", f"fsize={fsize_blocks}:{fsize_blocks}",
        "--user", f"{uid}:{gid}",
        "--workdir", "/workspace",
        "--env", "HOME=/home/validator",
        "--env", "TMPDIR=/tmp",
        "--env", "LANG=C.UTF-8",
        "--env", "LC_ALL=C.UTF-8",
        "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--env", "AZPR_VALIDATION=1",
        "--mount", f"type=bind,src={snapshot},dst=/workspace,readonly",
        "--mount", f"type=bind,src={evidence},dst=/evidence",
        "--tmpfs", f"/tmp:rw,noexec,nosuid,nodev,size={args.tmpfs_size}",
        "--tmpfs", " /home/validator:rw,noexec,nosuid,nodev,size=64m".strip(),
        args.image,
        *command,
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--expected-digest", required=True)
    parser.add_argument("--engine-path", required=True)
    parser.add_argument("--engine-sha256", required=True)
    parser.add_argument("--timeout", type=int, required=True)
    parser.add_argument("--cpus", default="2")
    parser.add_argument("--memory", default="2g")
    parser.add_argument("--pids-limit", type=int, default=256)
    parser.add_argument("--tmpfs-size", default="512m")
    parser.add_argument("--file-size-limit", type=int, default=134217728)
    parser.add_argument("--output-byte-limit", type=int, default=DEFAULT_OUTPUT_BYTE_LIMIT)
    parser.add_argument("--file-count-limit", type=int, default=DEFAULT_FILE_COUNT_LIMIT)
    parser.add_argument("--depth-limit", type=int, default=DEFAULT_DEPTH_LIMIT)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command or args.command[0] != "--" or len(args.command) < 2:
        raise RunnerError("A validation command must follow --.")
    command = args.command[1:]
    if args.timeout < 1 or args.timeout > 7200:
        raise RunnerError("Timeout must be between 1 and 7200 seconds.")
    if not args.expected_digest.startswith("sha256:") or not args.image.endswith("@" + args.expected_digest):
        raise RunnerError("Image reference and expected digest are inconsistent.")
    if ti.production_mode():
        try:
            installed_engine = ti.load_installation().component("container_engine")
        except ti.InstallationError as exc:
            raise RunnerError(str(exc)) from exc
        engine_path = Path(args.engine_path).absolute()
        if engine_path != installed_engine:
            raise RunnerError("production container engine is not the pinned installed binary")
    else:
        engine_path = Path(args.engine_path).absolute()
    no_symlink_ancestors(engine_path)
    info = os.stat(engine_path)
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022:
        raise RunnerError("Container engine must be a pinned non-writable regular file.")
    if sha256_file(engine_path) != args.engine_sha256:
        raise RunnerError("Container engine binary hash mismatch.")
    args.engine = str(engine_path)
    repo = Path(args.repo).absolute()
    evidence = Path(args.evidence_dir).absolute()
    no_symlink_ancestors(repo)
    no_symlink_ancestors(evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    os.chmod(evidence, 0o700)
    inspect_image(args.engine, args.image, args.expected_digest)
    with tempfile.TemporaryDirectory(prefix="azpr-validation-") as temporary:
        snapshot = Path(temporary) / "snapshot"
        snapshot.mkdir(mode=0o700)
        snapshot_identity = snapshot_repository(repo, snapshot, file_count_limit=args.file_count_limit, depth_limit=args.depth_limit, include_identity=True)
        assert isinstance(snapshot_identity,dict)
        snapshot_hash = snapshot_identity["snapshot_sha256"]
        before = snapshot_repository_digest(snapshot)
        container_argv = build_container_command(args, snapshot, evidence, command)
        start = time.monotonic()
        result = run_group(
            container_argv,
            args.timeout + 30,
            watch_path=evidence,
            max_watch_bytes=args.file_size_limit,
            output_byte_limit=args.output_byte_limit,
            file_count_limit=args.file_count_limit,
            depth_limit=args.depth_limit,
        )
        duration = time.monotonic() - start
        after = snapshot_repository_digest(snapshot)
        if before != after:
            raise RunnerError("Read-only validation snapshot changed unexpectedly.")
        evidence_bytes, evidence_file_count = directory_stats(evidence, file_limit=args.file_count_limit, depth_limit=args.depth_limit)
        if evidence_bytes > args.file_size_limit:
            raise RunnerError("Validation evidence exceeded the configured size limit.")
        record = {
            "format_version": "1.0",
            "image": args.image,
            "expected_digest": args.expected_digest,
            "snapshot_sha256": snapshot_hash,
            "source_commit": snapshot_identity["source_commit"],
            "source_tree": snapshot_identity["source_tree"],
            "command": command,
            "returncode": result.returncode,
            "duration_seconds": round(duration, 3),
            "evidence_bytes": evidence_bytes,
            "evidence_file_count": evidence_file_count,
        }
        record_bytes = (json.dumps(record, indent=2) + "\n").encode("utf-8")
        record_hash = hashlib.sha256(record_bytes).hexdigest()
        record_path = evidence / f"runner-record-{record_hash}.json"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(record_path, flags, 0o600)
        try:
            os.write(fd, record_bytes)
            os.fsync(fd)
        finally:
            os.close(fd)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        return result.returncode


def snapshot_repository_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        dirs.sort()
        for name in sorted(files):
            path = Path(current) / name
            rel = path.relative_to(root).as_posix()
            info = os.lstat(path)
            if not stat.S_ISREG(info.st_mode):
                raise RunnerError(f"Snapshot contains non-regular file: {rel}")
            digest.update(rel.encode("utf-8") + b"\0" + sha256_file(path).encode("ascii") + b"\0")
    return digest.hexdigest()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RunnerError as exc:
        print(f"VALIDATION RUNNER BLOCKED: {exc}", file=sys.stderr)
        raise SystemExit(2)
