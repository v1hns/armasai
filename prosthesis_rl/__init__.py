"""Prosthesis-RL package."""

# Auto-load a repo-root .env (project/provider config) if python-dotenv is
# installed. Optional and side-effect-free when absent — keeps entrypoints
# turnkey without each one re-exporting GOOGLE_* / provider env vars.
try:
    from dotenv import load_dotenv as _load_dotenv

    _load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass

__all__ = ["__version__"]

__version__ = "0.1.0"
