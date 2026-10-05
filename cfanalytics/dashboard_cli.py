"""Console-script launcher for the Streamlit dashboard."""

import sys
from pathlib import Path

from streamlit.web import cli as streamlit_cli

from cfanalytics import dashboard


def main() -> None:
    """Start the dashboard through Streamlit's command-line runner."""
    dashboard_path = Path(dashboard.__file__).resolve()
    sys.argv = ["streamlit", "run", str(dashboard_path), *sys.argv[1:]]
    sys.exit(streamlit_cli.main())
