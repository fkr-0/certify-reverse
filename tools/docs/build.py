#!/usr/bin/env python3
"""Build the certify-reverse documentation site, handbook, and man pages."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT / "tools" / "docs"
DIST_DIR = ROOT / "dist" / "docs"
CACHE_DIR = ROOT / ".cache" / "docs"
LOCK_FILE = TOOLS_DIR / "requirements.lock.txt"
INPUT_FILE = TOOLS_DIR / "requirements.in"
TOOLCHAIN_FILE = TOOLS_DIR / "toolchain.toml"
HANDBOOK_FILE = TOOLS_DIR / "handbook.toml"


class DocsBuildError(RuntimeError):
    """Raised when documentation output cannot be built or validated."""


def run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(command), file=sys.stderr)
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=False,
    )
    if completed.returncode != 0:
        detail = ""
        if capture:
            detail = f"\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        raise DocsBuildError(
            f"command failed with exit code {completed.returncode}: {' '.join(command)}{detail}"
        )
    return completed


def read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def project_version() -> str:
    return str(read_toml(ROOT / "pyproject.toml")["project"]["version"])


def source_date() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).date().isoformat()
    completed = run(["git", "log", "-1", "--format=%cs"], capture=True)
    value = completed.stdout.strip()
    return value or datetime.now(tz=timezone.utc).date().isoformat()


def command_version(command: str) -> str:
    executable = shutil.which(command)
    if executable is None:
        raise DocsBuildError(f"required documentation tool is unavailable: {command}")
    completed = run([executable, "--version"], capture=True)
    first_line = (completed.stdout or completed.stderr).splitlines()[0]
    match = re.search(r"(\d+(?:\.\d+)+)", first_line)
    if match is None:
        raise DocsBuildError(f"could not parse {command} version from: {first_line}")
    return match.group(1)


def ensure_external_toolchain() -> dict[str, str]:
    expected = read_toml(TOOLCHAIN_FILE)["renderers"]
    actual = {
        "pandoc": command_version("pandoc"),
        "weasyprint": command_version("weasyprint"),
        "groff": command_version("groff"),
    }
    drift = {
        name: {"expected": str(expected[name]), "actual": actual[name]}
        for name in actual
        if actual[name] != str(expected[name])
    }
    if drift and os.environ.get("DOCS_ALLOW_TOOLCHAIN_DRIFT") != "1":
        details = ", ".join(
            f"{name} expected {values['expected']}, found {values['actual']}"
            for name, values in drift.items()
        )
        raise DocsBuildError(
            f"documentation renderer version drift: {details}. "
            "Set DOCS_ALLOW_TOOLCHAIN_DRIFT=1 only for an intentional local trial."
        )
    return actual


def ensure_docs_environment() -> Path:
    if shutil.which("uv") is None:
        raise DocsBuildError("uv is required to create the pinned documentation environment")
    if not LOCK_FILE.exists():
        raise DocsBuildError(
            f"missing {LOCK_FILE.relative_to(ROOT)}; run tools/docs/update-lock.sh"
        )

    python_version = str(read_toml(TOOLCHAIN_FILE)["python"]["version"])
    venv = CACHE_DIR / "venv"
    python = venv / "bin" / "python"
    if not python.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        run(["uv", "venv", "--python", python_version, str(venv)])

    lock_hash = hashlib.sha256(LOCK_FILE.read_bytes()).hexdigest()
    stamp = venv / ".requirements.sha256"
    if not stamp.exists() or stamp.read_text(encoding="utf-8").strip() != lock_hash:
        run(
            [
                "uv",
                "pip",
                "sync",
                "--python",
                str(python),
                "--require-hashes",
                str(LOCK_FILE),
            ]
        )
        stamp.write_text(lock_hash + "\n", encoding="utf-8")
    return venv


def slugify_heading(value: str) -> str:
    value = re.sub(r"[`*_~]", "", value).strip().lower()
    value = re.sub(r"[^a-z0-9\s-]", "", value)
    value = re.sub(r"[\s-]+", "-", value)
    return value.strip("-")


def first_heading(markdown: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", markdown, re.MULTILINE)
    return slugify_heading(match.group(1)) if match else slugify_heading(fallback)


def rewrite_markdown_links(
    markdown: str,
    *,
    source: Path,
    anchors: dict[Path, str],
) -> str:
    """Rewrite links between handbook chapters to in-document anchors."""

    pattern = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+\.md)(#[^)]+)?\)")

    def replace(match: re.Match[str]) -> str:
        label, target_raw, fragment = match.groups()
        target = (source.parent / target_raw).resolve()
        anchor = fragment[1:] if fragment else anchors.get(target)
        if anchor is None:
            return match.group(0)
        return f"[{label}](#{anchor})"

    return pattern.sub(replace, markdown)


def add_explicit_chapter_anchor(markdown: str, anchor: str) -> str:
    """Give the first level-one heading a renderer-independent identifier."""
    return re.sub(
        r"^(#\s+.+?)\s*$",
        rf"\1 {{#{anchor}}}",
        markdown,
        count=1,
        flags=re.MULTILINE,
    )


def load_handbook_sources() -> tuple[dict[str, Any], list[Path]]:
    config = read_toml(HANDBOOK_FILE)
    sources = [(ROOT / value).resolve() for value in config["chapters"]]
    missing = [path for path in sources if not path.exists()]
    if missing:
        formatted = ", ".join(str(path.relative_to(ROOT)) for path in missing)
        raise DocsBuildError(f"handbook source files are missing: {formatted}")
    return config, sources


def assemble_handbook(destination: Path) -> list[str]:
    config, sources = load_handbook_sources()
    contents = {path: path.read_text(encoding="utf-8") for path in sources}
    anchors = {
        path.resolve(): first_heading(text, path.stem)
        for path, text in contents.items()
    }
    version = project_version()
    header = (
        "---\n"
        f"title: {json.dumps(config['title'])}\n"
        f"subtitle: {json.dumps(config['subtitle'])}\n"
        f"date: {json.dumps(source_date())}\n"
        f"version: {json.dumps(version)}\n"
        "lang: en\n"
        "---\n\n"
        f"> Documentation for certify-reverse **v{version}**.\n\n"
    )
    chapters: list[str] = []
    for path in sources:
        rewritten = rewrite_markdown_links(
            contents[path], source=path, anchors=anchors
        ).rstrip()
        rewritten = add_explicit_chapter_anchor(rewritten, anchors[path.resolve()])
        chapters.append(rewritten)
    page_break = '\n\n<div class="page-break"></div>\n\n'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(header + page_break.join(chapters) + "\n", encoding="utf-8")
    return [str(path.relative_to(ROOT)) for path in sources]


def build_site(venv: Path) -> None:
    mkdocs = venv / "bin" / "mkdocs"
    site_dir = DIST_DIR / "site"
    run(
        [
            str(mkdocs),
            "build",
            "--strict",
            "--config-file",
            str(ROOT / "mkdocs.yml"),
            "--site-dir",
            str(site_dir),
        ]
    )


def build_site_only() -> None:
    venv = ensure_docs_environment()
    shutil.rmtree(DIST_DIR / "site", ignore_errors=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    build_site(venv)
    index = DIST_DIR / "site" / "index.html"
    search_index = DIST_DIR / "site" / "search" / "search_index.json"
    if not index.exists() or not search_index.exists():
        raise DocsBuildError("static site or search index is missing")
    print(f"Static documentation site built in {(DIST_DIR / 'site').relative_to(ROOT)}")


def build_handbook() -> list[str]:
    build_dir = CACHE_DIR / "build"
    source = build_dir / "handbook.md"
    chapters = assemble_handbook(source)
    html_output = DIST_DIR / "certify-reverse-handbook.html"
    pdf_output = DIST_DIR / "certify-reverse-handbook.pdf"
    html_output.parent.mkdir(parents=True, exist_ok=True)

    run(
        [
            "pandoc",
            str(source),
            "--from=gfm+attributes",
            "--to=html5",
            "--standalone",
            "--toc",
            "--toc-depth=3",
            "--number-sections",
            "--embed-resources",
            "--css",
            str(TOOLS_DIR / "assets" / "handbook.css"),
            "--metadata",
            f"pagetitle=certify-reverse Handbook v{project_version()}",
            "--output",
            str(html_output),
        ]
    )
    run(["weasyprint", str(html_output), str(pdf_output)])
    return chapters


def replace_version_tokens(source: str) -> str:
    return source.replace("@VERSION@", project_version()).replace(
        "@DATE@", source_date()
    )


def build_man_pages() -> list[str]:
    config = read_toml(HANDBOOK_FILE)
    man_dir = DIST_DIR / "man"
    man_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    for entry in config["man_pages"]:
        source = ROOT / str(entry["source"])
        output = man_dir / str(entry["output"])
        if not source.exists():
            raise DocsBuildError(f"missing man-page source: {source.relative_to(ROOT)}")
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".md", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(replace_version_tokens(source.read_text(encoding="utf-8")))
        try:
            run(
                [
                    "pandoc",
                    str(temporary),
                    "--standalone",
                    "--from=gfm",
                    "--to=man",
                    "--output",
                    str(output),
                ]
            )
        finally:
            temporary.unlink(missing_ok=True)
        with output.open("rb") as input_stream, gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=(output.with_suffix(output.suffix + ".gz")).open("wb"),
            mtime=0,
        ) as gzip_stream:
            shutil.copyfileobj(input_stream, gzip_stream)
        outputs.extend(
            [
                str(output.relative_to(ROOT)),
                str(output.with_suffix(output.suffix + ".gz").relative_to(ROOT)),
            ]
        )
    return outputs


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_output_files() -> Iterable[Path]:
    for path in sorted(DIST_DIR.rglob("*")):
        if path.is_file() and path.name not in {"build-manifest.json", "certify-reverse-docs.tar.gz"}:
            yield path


def build_archive() -> Path:
    archive = DIST_DIR / "certify-reverse-docs.tar.gz"
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as tar:
                for path in iter_output_files():
                    info = tar.gettarinfo(str(path), arcname=str(path.relative_to(DIST_DIR)))
                    info.mtime = 0
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    with path.open("rb") as stream:
                        tar.addfile(info, stream)
    return archive


def write_manifest(
    *,
    renderer_versions: dict[str, str],
    chapters: list[str],
    man_outputs: list[str],
) -> None:
    manifest = {
        "project": "certify-reverse",
        "version": project_version(),
        "source_date": source_date(),
        "renderers": renderer_versions,
        "python_requirements_sha256": sha256(LOCK_FILE),
        "handbook_chapters": chapters,
        "man_outputs": man_outputs,
        "outputs": {
            str(path.relative_to(DIST_DIR)): {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in iter_output_files()
        },
    }
    (DIST_DIR / "build-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_outputs() -> None:
    required = [
        DIST_DIR / "site" / "index.html",
        DIST_DIR / "site" / "search" / "search_index.json",
        DIST_DIR / "certify-reverse-handbook.html",
        DIST_DIR / "certify-reverse-handbook.pdf",
        DIST_DIR / "man" / "certify-reverse.1",
        DIST_DIR / "man" / "certify-reverse.1.gz",
        DIST_DIR / "man" / "caddy-docker.1",
        DIST_DIR / "man" / "caddy-docker.1.gz",
        DIST_DIR / "build-manifest.json",
        DIST_DIR / "certify-reverse-docs.tar.gz",
    ]
    missing = [path for path in required if not path.exists() or path.stat().st_size == 0]
    if missing:
        formatted = ", ".join(str(path.relative_to(ROOT)) for path in missing)
        raise DocsBuildError(f"documentation outputs are missing or empty: {formatted}")
    if not (DIST_DIR / "certify-reverse-handbook.pdf").read_bytes().startswith(b"%PDF"):
        raise DocsBuildError("handbook PDF does not have a PDF file signature")
    for man_page in ("certify-reverse.1", "caddy-docker.1"):
        content = (DIST_DIR / "man" / man_page).read_text(encoding="utf-8")
        if ".TH" not in content:
            raise DocsBuildError(f"generated man page lacks a .TH header: {man_page}")


def clean() -> None:
    shutil.rmtree(DIST_DIR, ignore_errors=True)
    shutil.rmtree(CACHE_DIR / "build", ignore_errors=True)


def build() -> None:
    renderer_versions = ensure_external_toolchain()
    venv = ensure_docs_environment()
    clean()
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    build_site(venv)
    chapters = build_handbook()
    man_outputs = build_man_pages()
    build_archive()
    write_manifest(
        renderer_versions=renderer_versions,
        chapters=chapters,
        man_outputs=man_outputs,
    )
    validate_outputs()
    print(f"Documentation built in {DIST_DIR.relative_to(ROOT)}")


def serve() -> None:
    venv = ensure_docs_environment()
    mkdocs = venv / "bin" / "mkdocs"
    os.execv(
        str(mkdocs),
        [
            str(mkdocs),
            "serve",
            "--config-file",
            str(ROOT / "mkdocs.yml"),
        ],
    )


def update_lock() -> None:
    run(
        [
            "uv",
            "pip",
            "compile",
            "--generate-hashes",
            "--universal",
            "--python-version",
            str(read_toml(TOOLCHAIN_FILE)["python"]["version"]),
            str(INPUT_FILE),
            "--output-file",
            str(LOCK_FILE),
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("build", "check", "site", "serve", "clean", "update-lock"),
        nargs="?",
        default="build",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        if args.command in {"build", "check"}:
            build()
        elif args.command == "site":
            build_site_only()
        elif args.command == "serve":
            serve()
        elif args.command == "clean":
            clean()
        elif args.command == "update-lock":
            update_lock()
    except DocsBuildError as error:
        print(f"documentation build failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
