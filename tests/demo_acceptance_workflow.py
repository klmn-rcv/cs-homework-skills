"""Retain the real mixed-bug acceptance/repair scenario and its CLI receipts."""
import argparse
from pathlib import Path
from test_acceptance_workflow import AcceptanceWorkflow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    case = AcceptanceWorkflow("test_mixed_assignment_readonly_then_authorized_code_repair_partial_block_and_report_reacceptance")
    case.demo_root = args.output.resolve()
    case.setUp()
    case.test_mixed_assignment_readonly_then_authorized_code_repair_partial_block_and_report_reacceptance()
    print(f"Actual evidence retained at {case.root}")


if __name__ == "__main__":
    main()
