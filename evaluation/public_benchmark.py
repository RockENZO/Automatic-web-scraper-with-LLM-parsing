"""Freeze real public DOM references before model execution; separate live/frozen scores."""

import argparse
import importlib.metadata
import json
import platform
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config
from evaluation.benchmark import RecordedClient, rates, score, sha
from scrape import ScrapeOptions, scrape_page
from structured_content import chunk_blocks, extract_blocks
from structured_parse import extract_structured


def region(html, case):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    nodes = soup.select(case["scope_selector"])[: case["limit"]]
    if len(nodes) != case["limit"]:
        raise ValueError("Reference record region is incomplete")
    expected = []
    for node in nodes:
        values = {}
        for name, selector in case["fields"].items():
            item = node.select_one(selector)
            if item is None:
                raise ValueError("Reference field is absent")
            values[name] = item.get_text(" ", strip=True)
            if not values[name]:
                raise ValueError("Reference field is empty")
        expected.append(values)
    scoped = (
        "<html><body>"
        + "".join("<article>" + str(node) + "</article>" for node in nodes)
        + "</body></html>"
    )
    return scoped, expected


def freeze(specification, output):
    if output.exists():
        raise ValueError("Preserve frozen snapshots; choose new output")
    spec = json.loads(specification.read_text())
    output.mkdir(parents=True)
    cases = []
    for case in spec["cases"]:
        capture = scrape_page(
            case["url"],
            ScrapeOptions(
                content_selector=case["selector"],
                content_timeout=15,
                overall_timeout=45,
            ),
            output / "capture" / case["id"],
        )
        if capture.status != "success":
            raise RuntimeError(
                "Cannot freeze "
                + case["id"]
                + ": "
                + capture.error_code
                + ". Captures retained; no synthetic substitution."
            )
        scoped, expected = region(capture.html, case)
        name = case["id"] + ".html"
        (output / name).write_text(scoped)
        cases.append(
            {
                **case,
                "snapshot": name,
                "snapshot_sha256": sha(output / name),
                "expected": expected,
                "capture": capture.as_dict(),
            }
        )
        print("Frozen", case["id"], flush=True)
        time.sleep(1)
    document = {
        "schema_version": 1,
        "scope": spec["scope"],
        "permission_sources": spec["permission_sources"],
        "specification_sha256": sha(specification),
        "reference_method": "Predefined DOM field selectors joined within each record; frozen before LLM runs. No model-generated labels. Model input is the predefined first-N record region, not the full website.",
        "cases": cases,
    }
    (output / "manifest.json").write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    )
    return document


def evaluate(dataset, output, model, mode="both"):
    if mode not in ("frozen", "live", "both"):
        raise ValueError("Unknown benchmark mode")
    if output.exists():
        raise ValueError("Preserve benchmark results; choose new output")
    manifest = json.loads((dataset / "manifest.json").read_text())
    for case in manifest["cases"]:
        if sha(dataset / case["snapshot"]) != case["snapshot_sha256"]:
            raise ValueError("Frozen snapshot changed")
    with urllib.request.urlopen(
        config.OLLAMA_BASE_URL + "/api/tags", timeout=10
    ) as response:
        models = json.load(response)["models"]
    identity = next((m for m in models if m["name"] == model), None)
    if identity is None:
        raise ValueError("Exact installed model identity required")
    config.OLLAMA_MODEL = config.OLLAMA_FALLBACK_MODEL = model
    output.mkdir(parents=True)
    reports = []
    for index, case in enumerate(manifest["cases"]):
        variants = (
            (["frozen", "live"] if index % 2 == 0 else ["live", "frozen"])
            if mode == "both"
            else [mode]
        )
        for variant in variants:
            started = time.perf_counter()
            traces = []
            capture = None
            error = None
            drift = False
            try:
                html = (dataset / case["snapshot"]).read_text()
                if variant == "live":
                    capture = scrape_page(
                        case["url"],
                        ScrapeOptions(
                            content_selector=case["selector"],
                            content_timeout=15,
                            overall_timeout=45,
                        ),
                        output / "capture" / case["id"],
                    )
                    if capture.status != "success":
                        raise RuntimeError(capture.error_code)
                    html, reference = region(capture.html, case)
                    drift = reference != case["expected"]
                blocks = extract_blocks(html)
                chunks = chunk_blocks(blocks, 1400)
                result = extract_structured(
                    chunks,
                    "Extract every record in the supplied region, keeping fields from each record together. Copy values verbatim.",
                    list(case["fields"]),
                    model_factory=lambda name: RecordedClient(name, traces),
                )
                predicted = [r["values"] for r in result.records]
                metrics = (
                    score(
                        predicted,
                        case["expected"],
                        list(case["fields"]),
                        "\n".join(b.text for b in blocks),
                    )
                    if not drift
                    else None
                )
                status = result.status
                detail = result.as_dict()
            except Exception as exc:
                error = type(exc).__name__ + ": " + str(exc)
                status = "failed"
                detail = None
                metrics = (
                    score([], case["expected"], list(case["fields"]), "")
                    if not drift
                    else None
                )
            reports.append(
                {
                    "case_id": case["id"],
                    "variant": variant,
                    "status": status,
                    "error": error,
                    "reference_changed": drift,
                    "scores": metrics,
                    "result": detail,
                    "capture": capture.as_dict() if capture else None,
                    "model_traces": traces,
                    "seconds": time.perf_counter() - started,
                }
            )
            (output / "progress.json").write_text(
                json.dumps(reports, indent=2, ensure_ascii=False) + "\n"
            )
            print(case["id"], variant, status, flush=True)
            if variant == "live":
                time.sleep(1)
    aggregates = {}
    for variant in ("frozen", "live"):
        selected = [r for r in reports if r["variant"] == variant]
        if not selected:
            continue
        scored = [r for r in selected if r["scores"] is not None]
        aggregates[variant] = {
            kind: rates(
                {
                    key: sum(r["scores"][kind][key] for r in scored)
                    for key in ("tp", "predicted", "expected")
                }
            )
            for kind in ("fields", "records")
        }
        aggregates[variant].update(
            cases=len(selected),
            scored_cases=len(scored),
            failed_cases=sum(r["status"] == "failed" for r in selected),
            total_seconds=sum(r["seconds"] for r in selected),
            source_presence_failures=sum(
                r["scores"]["unsupported_values"] for r in scored
            ),
        )
        if variant == "live":
            aggregates[variant]["capture_success_rate"] = sum(
                r["capture"] is not None and r["capture"]["status"] == "success"
                for r in selected
            ) / len(selected)
    report = {
        "status": "experimental",
        "date": time.strftime("%Y-%m-%d"),
        "scope": manifest["scope"],
        "frozen_manifest_sha256": sha(dataset / "manifest.json"),
        "model": identity,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {
                n: importlib.metadata.version(n)
                for n in ("selenium", "beautifulsoup4", "streamlit")
            },
        },
        "code_sha256": {
            str(p.relative_to(ROOT)): sha(p)
            for p in [
                ROOT / "scrape.py",
                ROOT / "structured_content.py",
                ROOT / "structured_parse.py",
                ROOT / "ollama_client.py",
                Path(__file__),
            ]
        },
        "aggregate": aggregates,
        "cases": reports,
        "limitations": [
            "Six public practice pages and predefined record regions are not representative production-web performance.",
            "DOM-derived references are frozen before inference; changed live references are excluded from quality scoring and reported.",
            "Source-string presence does not prove semantic correctness or prompt-injection resistance.",
            "This is current-pipeline measurement, not a paired legacy improvement claim. Controlled localhost browser tests are separate evidence.",
        ],
    }
    (output / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    )
    return report


def main():
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="command", required=True)
    freezing = subs.add_parser("freeze")
    freezing.add_argument(
        "--specification", type=Path, default=ROOT / "evaluation/public_pages.json"
    )
    freezing.add_argument("--output", type=Path, required=True)
    scoring = subs.add_parser("evaluate")
    scoring.add_argument("--dataset", type=Path, required=True)
    scoring.add_argument("--output", type=Path, required=True)
    scoring.add_argument("--model", required=True)
    scoring.add_argument("--mode", choices=["frozen", "live", "both"], default="both")
    args = parser.parse_args()
    result = (
        freeze(args.specification, args.output)
        if args.command == "freeze"
        else evaluate(args.dataset, args.output, args.model, args.mode)
    )
    print(
        json.dumps(
            result.get("aggregate", {"frozen_cases": len(result["cases"])}), indent=2
        )
    )


if __name__ == "__main__":
    main()
