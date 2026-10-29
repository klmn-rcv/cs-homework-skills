"""Retain a real default acceptance that supplements missing teacher evidence."""
import argparse
from pathlib import Path
from test_acceptance_workflow import AcceptanceWorkflow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    case = AcceptanceWorkflow("test_default_acceptance_resolves_missing_proof_with_only_necessary_run_and_preserves_originals")
    case.demo_root = args.output.resolve()
    case.setUp()
    case.test_default_acceptance_resolves_missing_proof_with_only_necessary_run_and_preserves_originals()
    print(f"Actual necessary-check evidence retained at {case.root}")


if __name__ == "__main__":
    main()
