"""Run the extractor on a briefing JSON and write the result to an output JSON file.

By default, the script regenerates the extractor test fixture.
"""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from un_llm_analysis import extractor

DEFAULT_INPUT = Path("tests/fixtures/briefing_2026-08-25.json")
DEFAULT_OUTPUT = Path("tests/fixtures/extracted_briefing_2026-08-25.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input briefing JSON (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output extracted JSON (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    result = extractor.extract_briefing(args.input)

    args.output.write_text(
        json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
