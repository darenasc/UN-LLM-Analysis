import argparse
import subprocess
import sys

def run_script(script_name):
    """
    Run a Python script as a subprocess and stop the pipeline if it fails.

    We use subprocess rather than importing each script as a module because
    these scripts execute code at import time (not wrapped in functions),
    so importing them would run them anyway but with less control over
    error handling and output streaming.

    # run without scraping: python run_all.py
    # run WITH scraping: python run_all.py --scrape
    """
    print(f"\n{'=' * 60}")
    print(f"Running {script_name}...")
    print(f"{'=' * 60}\n")

    result = subprocess.run([sys.executable, script_name])

    if result.returncode != 0:
        print(f"\n✗ {script_name} failed with exit code {result.returncode}. Stopping pipeline.")
        sys.exit(1)

    print(f"\n✓ {script_name} completed successfully.")


def main():
    parser = argparse.ArgumentParser(
        description="Run the noon briefings analysis pipeline."
    )
    parser.add_argument(
        "--scrape",
        action="store_true",
        help="Run scrape.py first to fetch the latest briefings. "
             "Skipped by default since it takes a long time."
    )
    args = parser.parse_args()

    if args.scrape:
        run_script("scrape.py")


    run_script("extract_text_to_df.py")
    run_script("aggregation.py")
    run_script("heatmap.py")

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()