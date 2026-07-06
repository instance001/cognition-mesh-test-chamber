from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from pathlib import Path

from .assistant_review import run_assistant_review
from .dashboard import run_dashboard_server
from .evaluator_benchmark import materialize_evaluator_benchmark_runs, run_evaluator_benchmark_suite
from .gauntlet import (
    list_materialized_probe_drafts,
    load_gauntlet_spec,
    load_materialized_probe_draft,
    read_or_rebuild_gauntlet_history_index,
    materialize_probe_draft_files,
    rebuild_gauntlet_history_index,
    rebuild_probe_forge_drafts,
    validate_probe_draft_payload,
)
from .gauntlet.runner import GauntletRunner
from .model_catalog import format_catalog, load_catalog
from .preflight import (
    preflight_catalog_entry,
    preflight_model_config,
    preflight_run_folder,
    render_check_results,
)
from .runner.probe_runner import ProbeRunner
from .runner.run_config import load_host_profile, load_model_config, load_task_pack


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cm_test_chamber")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the fixed probe pack against a model config.")
    run_parser.add_argument("--model", required=True, type=Path)
    run_parser.add_argument("--host", required=True, type=Path)
    run_parser.add_argument("--task-pack", required=True, type=Path)
    run_parser.add_argument("--out", required=True, type=Path)

    gauntlet_parser = subparsers.add_parser("gauntlet-run", help="Run the dense multi-turn gauntlet lane.")
    gauntlet_parser.add_argument("--model", required=True, type=Path)
    gauntlet_parser.add_argument("--host", required=True, type=Path)
    gauntlet_parser.add_argument("--gauntlet", required=True, type=Path)
    gauntlet_parser.add_argument("--out", required=True, type=Path)
    gauntlet_parser.add_argument("--retry-policy", choices=["none", "auto"], default="none")

    catalog_parser = subparsers.add_parser("catalog", help="List registered assistant or model-under-test entries.")
    catalog_parser.add_argument(
        "--role",
        required=True,
        choices=["assistant", "model_under_test"],
    )

    review_parser = subparsers.add_parser(
        "assistant-review",
        help="Generate optional assistant commentary for a completed run folder.",
    )
    review_parser.add_argument("--run", required=True, type=Path)
    review_parser.add_argument("--assistant-id", required=True)

    benchmark_parser = subparsers.add_parser(
        "evaluator-benchmark",
        help="Materialize deterministic evaluator benchmark runs and optionally execute assistant reviews across them.",
    )
    benchmark_parser.add_argument(
        "--assistant-id",
        action="append",
        dest="assistant_ids",
        help="Assistant id to benchmark. Repeat to benchmark multiple assistants. Defaults to all assistant catalog entries.",
    )
    benchmark_parser.add_argument(
        "--materialize-only",
        action="store_true",
        help="Only write the deterministic benchmark run folders without running assistant reviews.",
    )

    draft_parser = subparsers.add_parser(
        "draft-probes",
        help="List or inspect materialized draft probe blueprints.",
    )
    draft_parser.add_argument("--draft-id")
    draft_parser.add_argument("--path", type=Path)
    draft_parser.add_argument("--materialize", action="store_true")

    atlas_parser = subparsers.add_parser(
        "gauntlet-atlas",
        help="Inspect historical gauntlet atlas summaries from the terminal.",
    )
    atlas_parser.add_argument("--family")
    atlas_parser.add_argument("--model")
    atlas_parser.add_argument("--refresh", action="store_true")

    preflight_parser = subparsers.add_parser(
        "preflight",
        help="Check local model files, endpoints, and run artifacts before a run or assistant review.",
    )
    preflight_parser.add_argument(
        "--mode",
        required=True,
        choices=["run", "assistant-review", "catalog-model"],
    )
    preflight_parser.add_argument("--model", type=Path)
    preflight_parser.add_argument("--role", choices=["assistant", "model_under_test"])
    preflight_parser.add_argument("--model-id")
    preflight_parser.add_argument("--run-dir", type=Path)
    preflight_parser.add_argument("--check-endpoint", action="store_true")

    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Start a thin local dashboard for catalogs, preflight, runs, and assistant review.",
    )
    dashboard_parser.add_argument("--host", default="127.0.0.1")
    dashboard_parser.add_argument("--port", default=8765, type=int)
    dashboard_parser.add_argument("--no-open", action="store_true", help="Do not auto-open the dashboard URL.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    if args.command == "catalog":
        catalog_path = repo_root / "configs" / "catalogs" / (
            "assistant_models.json" if args.role == "assistant" else "models_under_test.json"
        )
        print(format_catalog(load_catalog(catalog_path)), end="")
        return 0
    if args.command == "assistant-review":
        result = run_assistant_review(repo_root, repo_root / args.run, args.assistant_id)
        print(f"Assistant review written: {result.output_path}")
        return 0
    if args.command == "evaluator-benchmark":
        if args.materialize_only:
            run_dirs = materialize_evaluator_benchmark_runs(repo_root)
            print("Materialized benchmark runs:")
            for run_dir in run_dirs:
                print(f"- {run_dir.relative_to(repo_root).as_posix()}")
            return 0
        summary_path = run_evaluator_benchmark_suite(repo_root, args.assistant_ids)
        print(f"Evaluator benchmark summary written: {summary_path}")
        return 0
    if args.command == "draft-probes":
        if args.materialize:
            rebuild_probe_forge_drafts(repo_root)
            payload = materialize_probe_draft_files(repo_root)
            print(f"Materialized {len(payload.get('entries', []))} draft probe(s).")
            return 0
        if args.path is not None:
            payload = load_materialized_probe_draft(repo_root, args.path.as_posix())
            issues = validate_probe_draft_payload(payload)
            print(json.dumps({"payload": payload, "validation_issues": issues}, indent=2))
            return 0 if not issues else 1
        if args.draft_id:
            payload = load_materialized_probe_draft(repo_root, args.draft_id)
            issues = validate_probe_draft_payload(payload)
            print(json.dumps({"payload": payload, "validation_issues": issues}, indent=2))
            return 0 if not issues else 1
        drafts = list_materialized_probe_drafts(repo_root)
        if not drafts:
            print("No materialized draft probes found.")
            return 0
        for draft in drafts:
            print(
                f"- {draft['draft_id']} | family={draft['failure_family']} | "
                f"priority={draft['priority']} | status={draft['status']} | path={draft['path']}"
            )
        return 0
    if args.command == "gauntlet-atlas":
        atlas = (
            json.loads(rebuild_gauntlet_history_index(repo_root).read_text(encoding="utf-8"))
            if args.refresh
            else read_or_rebuild_gauntlet_history_index(repo_root)
        )
        aggregate = atlas.get("aggregate") or {}
        if args.family:
            family = (aggregate.get("failure_families") or {}).get(args.family)
            if family is None:
                print(f"Failure family not found: {args.family}")
                return 1
            print(json.dumps({"failure_family": args.family, "summary": family}, indent=2))
            return 0
        if args.model:
            model = (aggregate.get("models") or {}).get(args.model)
            if model is None:
                print(f"Model not found: {args.model}")
                return 1
            print(json.dumps({"model": args.model, "summary": model}, indent=2))
            return 0
        entries = atlas.get("entries", [])
        family_count = len((aggregate.get("failure_families") or {}))
        model_count = len((aggregate.get("models") or {}))
        print(f"Gauntlet runs indexed: {len(entries)}")
        print(f"Failure families tracked: {family_count}")
        print(f"Models tracked: {model_count}")
        print("Top failure families:")
        ranked_families = sorted(
            (aggregate.get("failure_families") or {}).items(),
            key=lambda item: (-item[1].get("appearances", 0), item[0]),
        )
        for family, summary in ranked_families[:5]:
            print(
                f"- {family} | appearances={summary.get('appearances', 0)} | "
                f"decision={summary.get('operator_decision', 'unreviewed')} | "
                f"severity={summary.get('highest_severity', 'low')}"
            )
        print("Models:")
        ranked_models = sorted(
            (aggregate.get("models") or {}).items(),
            key=lambda item: (-item[1].get("runs", 0), item[0]),
        )
        for model, summary in ranked_models[:5]:
            print(
                f"- {model} | runs={summary.get('runs', 0)} | "
                f"avg_score={summary.get('average_score', 0)} | "
                f"probe_needed={summary.get('probe_needed_count', 0)}"
            )
        return 0
    if args.command == "preflight":
        if args.mode == "run":
            if args.model is None:
                parser.error("--model is required when --mode run")
            results = preflight_model_config(repo_root, args.model, args.check_endpoint)
        elif args.mode == "assistant-review":
            if args.run_dir is None or args.model_id is None:
                parser.error("--run-dir and --model-id are required when --mode assistant-review")
            results = preflight_run_folder(repo_root / args.run_dir)
            results.extend(
                preflight_catalog_entry(
                    repo_root,
                    "assistant",
                    args.model_id,
                    args.check_endpoint,
                )
            )
        else:
            if args.role is None or args.model_id is None:
                parser.error("--role and --model-id are required when --mode catalog-model")
            results = preflight_catalog_entry(repo_root, args.role, args.model_id, args.check_endpoint)
        print(render_check_results(results), end="")
        return 0 if all(item.ok for item in results) else 1
    if args.command == "dashboard":
        server = run_dashboard_server(repo_root, args.host, args.port)
        dashboard_url = f"http://{args.host}:{args.port}"
        print(f"Dashboard running at {dashboard_url}")
        if not args.no_open:
            threading.Thread(target=lambda: webbrowser.open(dashboard_url), daemon=True).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    if args.command == "gauntlet-run":
        model = load_model_config(repo_root / args.model)
        host = load_host_profile(repo_root / args.host)
        gauntlet = load_gauntlet_spec(repo_root / args.gauntlet)
        out_dir = repo_root / args.out
        runner = GauntletRunner(
            repo_root=repo_root,
            model=model,
            host=host,
            gauntlet=gauntlet,
            out_dir=out_dir,
            retry_policy=args.retry_policy,
        )
        runner.run()
        print(f"Gauntlet run completed: {out_dir}")
        return 0
    model = load_model_config(repo_root / args.model)
    host = load_host_profile(repo_root / args.host)
    task_pack = load_task_pack(repo_root / args.task_pack)
    out_dir = repo_root / args.out
    runner = ProbeRunner(repo_root=repo_root, model=model, host=host, task_pack=task_pack, out_dir=out_dir)
    runner.run()
    print(f"Run completed: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
