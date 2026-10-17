"""Run one development prompt against the contract RAG agent."""
import argparse
from dataclasses import asdict
import json

from rag.factory import create_agent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract-id", required=True)
    parser.add_argument("--question", required=True)
    args = parser.parse_args()

    response = create_agent().answer(
        args.question,
        contract_id=args.contract_id,
        user_pseudo_id="PROMPT-TEST",
        role="assure",
    )
    print(response.answer)
    if response.sources:
        print("\nSources:")
        print(json.dumps(
            [asdict(source) for source in response.sources],
            ensure_ascii=False,
            indent=2,
        ))
    if response.blocked:
        print("\nRequest blocked by an input guardrail.")


if __name__ == "__main__":
    main()
