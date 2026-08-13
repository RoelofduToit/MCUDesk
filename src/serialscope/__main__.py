"""Allow packaging-safe startup with ``python -m serialscope``."""

from serialscope.app import main


if __name__ == "__main__":
    raise SystemExit(main())
