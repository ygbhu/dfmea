from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = REPO_ROOT / "engine"
ENGINE_SRC = ENGINE_ROOT / "src"


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        _print_usage()
        return 0

    tool = args[0]
    if tool not in {"quality", "dfmea"}:
        print(f"Unknown quality assistant entrypoint: {tool}", file=sys.stderr)
        _print_usage(file=sys.stderr)
        return 2

    if str(ENGINE_SRC) not in sys.path:
        sys.path.insert(0, str(ENGINE_SRC))

    entrypoint = _load_entrypoint(tool)
    sys.argv = [tool, *args[1:]]
    entrypoint()
    return 0


def _load_entrypoint(tool: str) -> Callable[[], None]:
    try:
        if tool == "quality":
            from quality_adapters.cli.quality import main as quality_main

            return quality_main

        from quality_adapters.cli.dfmea import main as dfmea_main

        return dfmea_main
    except ModuleNotFoundError as exc:
        print(
            "Unable to import the quality assistant engine or its dependencies. "
            'Run `cd engine` then `python -m pip install -e ".[dev]"` and retry.',
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


def _print_usage(*, file=sys.stdout) -> None:
    print(
        "Usage: python scripts/quality_cli.py <quality|dfmea> [args...]\n\n"
        "Examples:\n"
        "  python scripts/quality_cli.py quality workspace init --workspace .\n"
        "  python scripts/quality_cli.py quality project create demo --workspace .\n"
        "  python scripts/quality_cli.py quality method list --workspace . --project demo\n"
        "  python scripts/quality_cli.py dfmea init --workspace . --project demo\n",
        file=file,
    )


if __name__ == "__main__":
    raise SystemExit(main())
