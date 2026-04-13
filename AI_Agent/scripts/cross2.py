from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = PROJECT_ROOT.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_ready_data import DEFAULT_OUTPUT, DEFAULT_SOURCE, build_ready_data
from build_index import DEFAULT_SECTION_MAX_TOKENS
from ready_data_tools import (
    READY_DATA_ROOT,
    add_feedback,
    explain_formula,
    inspect_ready_data,
    run_retrieval_eval,
    search_formulas,
    search_sections,
    search_summaries,
    trace_adjustments,
    trace_notices,
    trace_relations,
    validate_ready_data,
)
from regulatory_engine import answer_verified, collect_evidence, plan_regulatory_query, search_titles


def _json_print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _doc_ids_from_args(args: argparse.Namespace) -> list[str] | None:
    doc_ids: list[str] = []
    if getattr(args, "doc_id", None):
        doc_ids.append(str(args.doc_id))
    doc_ids.extend(str(item) for item in getattr(args, "doc_ids", []) or [])
    return doc_ids or None


def _cmd_build_ready_data(args: argparse.Namespace) -> int:
    stats = build_ready_data(
        source=args.source.resolve(),
        output_root=args.output.resolve(),
        section_max_tokens=args.section_max_tokens,
    )
    _json_print(stats)
    return 0


def _cmd_inspect_ready_data(args: argparse.Namespace) -> int:
    _json_print(inspect_ready_data(args.root.resolve(), sample_size=args.sample_size))
    return 0


def _cmd_validate_ready_data(args: argparse.Namespace) -> int:
    result = validate_ready_data(args.root.resolve())
    _json_print(result)
    return 0 if result["ok"] else 1


def _cmd_search(args: argparse.Namespace) -> int:
    if args.target == "titles":
        result = {"query": args.query, "hits": search_titles(args.query, limit=args.limit)}
    elif args.target == "summaries":
        result = {"query": args.query, "hits": search_summaries(args.query, limit=args.limit, doc_ids=_doc_ids_from_args(args))}
    elif args.target == "sections":
        result = {"query": args.query, "hits": search_sections(args.query, limit=args.limit, doc_ids=_doc_ids_from_args(args))}
    elif args.target == "formulas":
        result = {"query": args.query, "hits": search_formulas(args.query, limit=args.limit, doc_ids=_doc_ids_from_args(args))}
    else:
        raise ValueError(f"Unknown search target: {args.target}")
    _json_print(result)
    return 0


def _cmd_explain_formula(args: argparse.Namespace) -> int:
    result = explain_formula(query=args.query, formula_id=args.formula_id)
    _json_print(result)
    return 0 if result.get("ok") else 1


def _cmd_trace(args: argparse.Namespace) -> int:
    if args.target == "relations":
        result = trace_relations(
            doc_id=args.doc_id,
            query=args.query,
            direction=args.direction,
            relation=args.relation,
            limit=args.limit,
        )
    elif args.target == "notices":
        result = trace_notices(args.rule, limit=args.limit)
    elif args.target == "adjustments":
        result = trace_adjustments(args.notice, limit=args.limit)
    else:
        raise ValueError(f"Unknown trace target: {args.target}")
    _json_print(result)
    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    _json_print(plan_regulatory_query(args.question))
    return 0


def _cmd_evidence(args: argparse.Namespace) -> int:
    _json_print(collect_evidence(args.question, limit=args.limit))
    return 0


def _cmd_answer(args: argparse.Namespace) -> int:
    _json_print(answer_verified(args.question))
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    if args.target != "retrieval":
        raise ValueError(f"Unknown eval target: {args.target}")
    result = run_retrieval_eval(cases_path=args.cases, planner=plan_regulatory_query)
    _json_print(result)
    return 0 if result["failed"] == 0 else 1


def _cmd_feedback(args: argparse.Namespace) -> int:
    if args.target != "add":
        raise ValueError(f"Unknown feedback target: {args.target}")
    kwargs = {
        "question": args.question,
        "expected_doc": args.expected_doc or "",
        "note": args.note or "",
    }
    if args.output:
        kwargs["path"] = args.output.resolve()
    _json_print(add_feedback(**kwargs))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cross2", description="CLI for c-ross-2 ready_data and agent tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build-ready-data", help="Build Knowledge_Base_MarkDown/ready_data artifacts.")
    build_parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    build_parser.add_argument("--output", "--output-root", type=Path, default=DEFAULT_OUTPUT)
    build_parser.add_argument("--section-max-tokens", type=int, default=DEFAULT_SECTION_MAX_TOKENS)
    build_parser.set_defaults(func=_cmd_build_ready_data)

    inspect_parser = subparsers.add_parser("inspect-ready-data", help="Inspect ready_data counts and sample rows.")
    inspect_parser.add_argument("--root", type=Path, default=READY_DATA_ROOT)
    inspect_parser.add_argument("--sample-size", type=int, default=2)
    inspect_parser.set_defaults(func=_cmd_inspect_ready_data)

    validate_parser = subparsers.add_parser("validate-ready-data", help="Validate ready_data schema and manifest counts.")
    validate_parser.add_argument("--root", type=Path, default=READY_DATA_ROOT)
    validate_parser.set_defaults(func=_cmd_validate_ready_data)

    search_parser = subparsers.add_parser("search", help="Search ready_data artifacts.")
    search_subparsers = search_parser.add_subparsers(dest="target", required=True)
    for target in ("titles", "summaries", "sections", "formulas"):
        item = search_subparsers.add_parser(target)
        item.add_argument("--query", required=True)
        item.add_argument("--limit", type=int, default=5)
        if target != "titles":
            item.add_argument("--doc-id", default=None)
            item.add_argument("--doc-ids", nargs="*", default=[])
        item.set_defaults(func=_cmd_search)

    explain_parser = subparsers.add_parser("explain", help="Explain formulas and other ready_data items.")
    explain_subparsers = explain_parser.add_subparsers(dest="target", required=True)
    formula_parser = explain_subparsers.add_parser("formula")
    formula_group = formula_parser.add_mutually_exclusive_group(required=True)
    formula_group.add_argument("--query")
    formula_group.add_argument("--formula-id")
    formula_parser.set_defaults(func=_cmd_explain_formula)

    trace_parser = subparsers.add_parser("trace", help="Trace relations among notices, rules, and attachments.")
    trace_subparsers = trace_parser.add_subparsers(dest="target", required=True)
    relations_parser = trace_subparsers.add_parser("relations")
    relations_parser.add_argument("--doc-id", default=None)
    relations_parser.add_argument("--query", default=None)
    relations_parser.add_argument("--direction", choices=["both", "in", "out"], default="both")
    relations_parser.add_argument("--relation", default=None)
    relations_parser.add_argument("--limit", type=int, default=20)
    relations_parser.set_defaults(func=_cmd_trace)
    notices_parser = trace_subparsers.add_parser("notices")
    notices_parser.add_argument("--rule", required=True)
    notices_parser.add_argument("--limit", type=int, default=20)
    notices_parser.set_defaults(func=_cmd_trace)
    adjustments_parser = trace_subparsers.add_parser("adjustments")
    adjustments_parser.add_argument("--notice", required=True)
    adjustments_parser.add_argument("--limit", type=int, default=20)
    adjustments_parser.set_defaults(func=_cmd_trace)

    plan_parser = subparsers.add_parser("plan", help="Plan a regulatory query.")
    plan_parser.add_argument("--question", required=True)
    plan_parser.set_defaults(func=_cmd_plan)

    evidence_parser = subparsers.add_parser("evidence", help="Collect ready_data evidence for a question.")
    evidence_parser.add_argument("--question", required=True)
    evidence_parser.add_argument("--limit", type=int, default=5)
    evidence_parser.set_defaults(func=_cmd_evidence)

    answer_parser = subparsers.add_parser("answer", help="Generate a deterministic verified answer.")
    answer_parser.add_argument("--question", required=True)
    answer_parser.add_argument("--mode", choices=["verified"], default="verified")
    answer_parser.set_defaults(func=_cmd_answer)

    eval_parser = subparsers.add_parser("eval", help="Run offline evaluations.")
    eval_subparsers = eval_parser.add_subparsers(dest="target", required=True)
    retrieval_parser = eval_subparsers.add_parser("retrieval")
    retrieval_parser.add_argument("--cases", type=Path, default=PROJECT_ROOT / "eval" / "cases.jsonl")
    retrieval_parser.set_defaults(func=_cmd_eval)

    feedback_parser = subparsers.add_parser("feedback", help="Record user feedback as regression input.")
    feedback_subparsers = feedback_parser.add_subparsers(dest="target", required=True)
    feedback_add_parser = feedback_subparsers.add_parser("add")
    feedback_add_parser.add_argument("--question", required=True)
    feedback_add_parser.add_argument("--expected-doc", default="")
    feedback_add_parser.add_argument("--note", default="")
    feedback_add_parser.add_argument("--output", type=Path, default=None)
    feedback_add_parser.set_defaults(func=_cmd_feedback)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
