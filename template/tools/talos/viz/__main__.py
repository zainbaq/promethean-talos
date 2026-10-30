"""`python -m viz` entry point; argument parsing lives in viz.server.main."""
from .server import main

raise SystemExit(main())
