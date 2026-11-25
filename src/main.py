"""Console entry point for the Maven dependency visualizer."""

import argparse
import sys
from pathlib import Path

from config import ConfigError, load_config


def main():
    """Print the validated CSV configuration."""
    parser = argparse.ArgumentParser(description="Maven dependency visualizer")
    default_config = Path(__file__).resolve().parents[1] / "config.csv"
    parser.add_argument("config", type=Path, nargs="?", default=default_config)
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1

    for key, value in config.items():
        print(f"{key} = {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
