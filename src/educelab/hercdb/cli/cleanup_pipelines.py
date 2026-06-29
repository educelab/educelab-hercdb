"""Delete pipeline records from Neo4j by pipeline id (DB-admin tool).

Companion to the pipeline-recording write path in the acquisition-workflow
``submit_uber_pipeline.py``: while that path is being tested, every (dry-run or
real) submission writes a Pipeline node keyed by its ``uber_job_id``. This tool
lets a database administrator remove those test records again, straight against
Neo4j (no REST server needed).

Deleting a pipeline removes the Pipeline node, its Process nodes, and the output
dataset nodes (PGSProcessed/SpectralProcessed/Registered/WebProcessed) those
processes produced. Input/raw datasets (PGSRaw/SpectralRaw/...) are left
untouched.

Wired up as the ``el-hercdb-pipeline-cleanup`` shell command (see
``[project.scripts]`` in pyproject.toml). Usage:

    el-hercdb-pipeline-cleanup uber-1a2b3c4d [uber-...] [-y]
    uv run el-hercdb-pipeline-cleanup --list          # show what exists first
"""
import argparse
import sys

from educelab import hercdb
from educelab.hercdb import config


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Delete pipeline records (Pipeline + Process + output datasets) "
            "from Neo4j by pipeline id. Input/raw datasets are left untouched."
        )
    )
    parser.add_argument(
        "pipeline_ids", nargs="*",
        help="Pipeline id(s) to delete (the uber_job_id printed by "
             "submit_uber_pipeline.py).",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List all pipelines currently in the database and exit (no "
             "deletion). Useful for finding ids to clean up.",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip the confirmation prompt.",
    )
    args = parser.parse_args()

    if not args.list and not args.pipeline_ids:
        parser.error("provide one or more pipeline ids, or use --list.")

    config.request_required()
    db = hercdb.connect()
    if not db.verify_connection():
        print("Failed to connect to Neo4j.", file=sys.stderr)
        sys.exit(1)

    if args.list:
        pipelines = db.get_all_pipeline_summaries()
        if not pipelines:
            print("No pipelines in the database.")
            return
        print(f"{len(pipelines)} pipeline(s):")
        for p in pipelines:
            pid = p.get("pipeline_id", "?")
            uuid = p.get("artifact_uuid", "")
            print(f"  - {pid}" + (f"  (artifact {uuid})" if uuid else ""))
        return

    if not args.yes:
        print("About to delete the following pipeline(s):")
        for pid in args.pipeline_ids:
            print(f"  - {pid}")
        confirm = input("Proceed? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Aborted.")
            return

    failed = False
    for pid in args.pipeline_ids:
        result = db.delete_pipeline(pid)
        if result is None:
            print(f"{pid}: not found")
            failed = True
        else:
            print(
                f"{pid}: deleted "
                f"({result.get('processes_deleted', 0)} process(es), "
                f"{result.get('output_datasets_deleted', 0)} output dataset(s))"
            )

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
