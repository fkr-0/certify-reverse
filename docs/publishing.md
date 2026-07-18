# Documentation publishing

The documentation pipeline treats the Markdown files under `docs/` as the canonical
source. One command produces a searchable site, standalone handbook, PDF, man pages,
checksums, and a deterministic archive.

## Quick commands

Build every format:

```bash
./caddy-docker.sh docs
```

Build and validate every format:

```bash
./caddy-docker.sh docs-check
```

Build only the static site, as used by the Pages workflow:

```bash
./caddy-docker.sh docs-site
```

Preview the static site while editing:

```bash
./caddy-docker.sh docs-serve
```

Remove generated documentation:

```bash
./caddy-docker.sh docs-clean
```

## Output layout

A successful build creates:

```text
dist/docs/
├── site/                                  # searchable MkDocs site
├── man/
│   ├── certify-reverse.1
│   ├── certify-reverse.1.gz
│   ├── caddy-docker.1
│   └── caddy-docker.1.gz
├── certify-reverse-handbook.html          # standalone embedded-resource HTML
├── certify-reverse-handbook.pdf           # A4 PDF
├── certify-reverse-docs.tar.gz             # deterministic release archive
└── build-manifest.json                     # tool versions, sizes, SHA-256 hashes
```

The static site can be copied to any ordinary web server. It has no server-side
runtime requirement.

## Toolchain model

The pipeline has two layers.

### Pinned Python layer

MkDocs and MkDocs Material dependencies are compiled into:

```text
tools/docs/requirements.lock.txt
```

The lock contains exact package versions and hashes. The build script creates a
dedicated environment below `.cache/docs/venv` and synchronizes it with `uv`.

Refresh the lock only as an intentional maintenance change:

```bash
./caddy-docker.sh docs-update-lock
```

Review the complete lock diff and rebuild every output before committing it.

### Pinned renderer layer

Expected renderer versions are recorded in:

```text
tools/docs/toolchain.toml
```

The current pipeline uses:

- Pandoc to assemble the handbook and render man pages;
- WeasyPrint to print the standalone handbook HTML to A4 PDF;
- groff as the local man-page inspection tool.

The build fails when renderer versions drift. For an intentional local experiment,
you may set:

```bash
DOCS_ALLOW_TOOLCHAIN_DRIFT=1 ./caddy-docker.sh docs
```

Do not use that override for a release build. Update `toolchain.toml`, inspect the
rendered changes, and commit the version change instead.

## How the formats are built

```text
Markdown sources
   |
   +-- mkdocs.yml + MkDocs Material
   |      -> multi-page static site + search index
   |
   +-- tools/docs/handbook.toml + Pandoc
   |      -> one standalone HTML handbook
   |      -> internal Markdown links rewritten to chapter anchors
   |
   +-- handbook HTML + WeasyPrint
   |      -> A4 PDF with page numbers and print typography
   |
   +-- docs/reference/*.1.md + Pandoc man writer
          -> roff man pages + reproducible gzip files
```

`tools/docs/handbook.toml` defines chapter order. A page can be part of the static
site but excluded from the printed handbook, or vice versa, by changing this list.

## Add a new documentation page

1. Create the Markdown file below `docs/`.
2. Add it to `nav` in `mkdocs.yml`.
3. Add it to `tools/docs/handbook.toml` when it belongs in the PDF handbook.
4. Link it from the nearest overview page.
5. Build with strict validation:

```bash
./caddy-docker.sh docs-check
```

MkDocs strict mode rejects broken internal links, missing snippets, and many
configuration mistakes.

## Write beginner-friendly pages

Each task-oriented page should answer these questions in order:

1. **What will I achieve?**
2. **What do I need before starting?**
3. **What exact command do I run?**
4. **What should successful output look like?**
5. **What does the command change?**
6. **How do I verify the result independently?**
7. **How do I undo or clean it up?**
8. **Where do I go when it fails?**

Prefer complete examples over fragments. When a command contains placeholders,
list every placeholder immediately below the block.

Use admonitions consistently:

```markdown
!!! note
    Additional context that is useful but not urgent.

!!! tip
    A simpler or safer workflow.

!!! warning
    A mistake that can break setup or expose data.

!!! danger
    A destructive action such as deleting volumes.
```

Avoid hiding required information in an admonition.

## Code example rules

- Examples must use fake tokens and non-sensitive domains.
- Commands should run from the repository root unless the page says otherwise.
- Shell snippets should use `set -eu` when saved as scripts.
- Compose examples should validate with `docker compose config --quiet`.
- YAML examples should use spaces, never tabs.
- Show cleanup commands for every tutorial stack.
- Do not recommend `curl -k` as a normal final state.
- Explain whether an HTTP error means unreachable, unhealthy, or merely unauthorized.

## Man page sources

The source files are:

```text
docs/reference/certify-reverse.1.md
docs/reference/caddy-docker.1.md
```

They contain `@VERSION@` and `@DATE@` placeholders. The build script replaces those
from `pyproject.toml` and the source date before invoking Pandoc.

Preview generated pages:

```bash
man -l dist/docs/man/certify-reverse.1
man -l dist/docs/man/caddy-docker.1
```

Inspect raw roff when debugging:

```bash
groff -man -Tutf8 dist/docs/man/caddy-docker.1 | less -R
```

## PDF review checklist

After a documentation release, inspect at least:

- cover/title and table of contents;
- first and last page numbers;
- code blocks near page boundaries;
- wide tables;
- long URLs and file paths;
- admonitions and block quotes;
- chapter page breaks;
- non-ASCII characters such as arrows and en dashes.

The build validates the PDF signature and file presence, but visual review remains
necessary for typography and pagination.

## Reproducibility

Set `SOURCE_DATE_EPOCH` to control the handbook date and archive metadata:

```bash
SOURCE_DATE_EPOCH=$(git log -1 --format=%ct) ./caddy-docker.sh docs-check
```

The generated archive uses zeroed timestamps, numeric ownership, and stable path
ordering. `build-manifest.json` records renderer versions and SHA-256 hashes for all
other outputs.

## Release integration

The main release gate calls the documentation check:

```bash
./caddy-docker.sh verify
```

A release is not ready when:

- the site cannot build in strict mode;
- the search index is missing;
- the PDF is absent or malformed;
- either man page lacks its roff header;
- the dependency lock and environment differ;
- renderer versions differ from `toolchain.toml`;
- documentation examples fail their syntax or Compose checks.
