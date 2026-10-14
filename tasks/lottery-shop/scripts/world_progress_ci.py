#!/usr/bin/env python3
"""Export fixed WORLD samples; never logs, assertion text, XML, or a test verdict."""
import json
import re
from datetime import datetime
from pathlib import Path
import visual_candidate_ci as visual

LIMIT = 262144
MAX_RECORDS = 128
MAX_RECORD_BYTES = 4096
SCOPE = "WORLD_ROUTE_RAY_DIAGNOSTIC_NOT_TEST_PASS"
SOURCE = "artifacts/visual-regression-world/world-progress.jsonl"
DESTINATION = "world-progress.json"
ROUTE_PATTERN = 'WORLD_ROUTE_V1 segment=(?:ENTRY_TO_TICKET_RACK|TICKET_RACK_TO_TABLE|ENTRY_TO_INVENTORY|INVENTORY_TO_SHELF_AISLE|AISLE_TO_TOOL_SHELF|TOOL_SHELF_TO_DRAWER|TABLE_TO_PHONE_AISLE|AISLE_TO_PHONE|PHONE_TO_RETURN_AISLE|RETURN_AISLE_TO_TABLE) phase=(?:BEGIN|SAMPLE|REACHED|ABORTED) elapsed=-?[0-9]{1,6}\\.[0-9]{4} limit=45 frames=[0-9]{1,7} stationaryFrames=[0-9]{1,7} body=\\(-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4}\\) origin=\\(-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4}\\) destination=\\(-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4}\\) remaining=-?[0-9]{1,6}\\.[0-9]{4} minRemaining=-?[0-9]{1,6}\\.[0-9]{4} lastStep=-?[0-9]{1,6}\\.[0-9]{4} pathMeters=-?[0-9]{1,6}\\.[0-9]{4} maxFrameWall=-?[0-9]{1,6}\\.[0-9]{4} maxUnscaledDelta=-?[0-9]{1,6}\\.[0-9]{4} command=\\(-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4}\\) camera=\\(-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4}\\) cameraEuler=\\(-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4}\\) moveId=(?:-1|901) lookId=(?:-1|902) mode=[0-9]{1,2} focused=(?:True|False) awaitingRelease=(?:True|False) cameraWrite=(?:True|False)'
RAY_PATTERN = 'WORLD_RAY_V2 kind=(?:NONE|CHARACTER_CONTROLLER|WORLD_TARGET|UNTARGETED_COLLIDER) trigger=(?:True|False) ownBody=(?:True|False) environment=(?:True|False) hitDistance=-?[0-9]{1,6}\\.[0-9]{4} horizontalReach=-?[0-9]{1,6}\\.[0-9]{4} body=\\(-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4}\\) camera=\\(-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4}\\) target=\\(-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4}\\) pixel=\\(-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4}\\) rayOrigin=\\(-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4}\\) rayDirection=\\(-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4},-?[0-9]{1,6}\\.[0-9]{4}\\) foreignHits=[0-9]{1,7} foreignDistance=-?[0-9]{1,6}\\.[0-9]{4} foreignController=(?:True|False) foreignTarget=(?:True|False) foreignNearestTies=[0-9]{1,7}'
CASE_SEGMENTS = {'fe443afcbe561b898231f2330bc6d1840c843fd0415f94eeafc03d68ffae8d80': ['ENTRY_TO_TICKET_RACK', 'TICKET_RACK_TO_TABLE'], '3fb46e6d77cead8492b8b2b3f87b20cda9d74ce0fc1be6a62c65b9822f6296f1': ['ENTRY_TO_INVENTORY', 'INVENTORY_TO_SHELF_AISLE', 'AISLE_TO_TOOL_SHELF', 'TOOL_SHELF_TO_DRAWER'], 'a81f4076bd1a31b90e812478de29a90c4cfbbc52d2abb118b9a77f73984f8b32': ['TABLE_TO_PHONE_AISLE', 'AISLE_TO_PHONE', 'PHONE_TO_RETURN_AISLE', 'RETURN_AISLE_TO_TABLE']}
FIELDS = {"schemaVersion", "scope", "status", "sourceCommit", "reviewedCandidateCommit", "runId", "runAttempt", "sequence", "caseKey", "utc", "sample"}
require = visual.require


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "WORLD_DUPLICATE_FIELD")
        result[key] = value
    return result


def decode_records(data, ident):
    require(isinstance(data, bytes) and len(data) <= LIMIT, "WORLD_SIZE_REJECTED")
    lines = data.split(b"\n")
    partial = bool(lines[-1])
    # A partial final append is never parsed or exported, even when valid JSON.
    # Every complete record must pass; malformed middle records are not skipped.
    lines = lines[:-1]
    require(1 <= len(lines) <= MAX_RECORDS, "WORLD_RECORD_COUNT_REJECTED")
    rows = []
    last_utc = None
    route_state = {}
    ray_count = {}
    for index, line in enumerate(lines):
        require(0 < len(line) + 1 <= MAX_RECORD_BYTES, "WORLD_RECORD_SIZE_REJECTED")
        try:
            row = json.loads(line.decode("utf-8"), object_pairs_hook=unique_object)
        except Exception:
            raise ValueError("WORLD_JSON_REJECTED") from None
        require(type(row) is dict and set(row) == FIELDS, "WORLD_FIELDS_REJECTED")
        require(type(row["schemaVersion"]) is int and row["schemaVersion"] == 1 and row["scope"] == SCOPE and row["status"] == "OBSERVATIONS_ONLY_NOT_TEST_PASS", "WORLD_SCOPE_REJECTED")
        require(all(row[k] == ident[k] for k in ("sourceCommit", "reviewedCandidateCommit", "runId", "runAttempt")), "WORLD_IDENTITY_REJECTED")
        require(type(row["sequence"]) is int and row["sequence"] == index + 1, "WORLD_SEQUENCE_REJECTED")
        require(type(row["caseKey"]) is str and row["caseKey"] in CASE_SEGMENTS, "WORLD_CASE_REJECTED")
        utc = row["utc"]
        require(type(utc) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,7})?(?:Z|\+00:00)", utc), "WORLD_UTC_REJECTED")
        try:
            now = datetime.fromisoformat(utc.replace("Z", "+00:00"))
        except Exception:
            raise ValueError("WORLD_UTC_REJECTED") from None
        require(last_utc is None or now >= last_utc, "WORLD_UTC_REJECTED")
        last_utc = now
        sample = row["sample"]
        require(type(sample) is str and len(sample) <= 2048, "WORLD_SAMPLE_REJECTED")
        if re.fullmatch(ROUTE_PATTERN, sample):
            values = dict(item.split("=", 1) for item in sample.split(" ")[1:])
            segment, phase = values["segment"], values["phase"]
            require(segment in CASE_SEGMENTS[row["caseKey"]], "WORLD_SEGMENT_CASE_REJECTED")
            previous, count, last_elapsed, last_frames = route_state.get(segment, (None, 0, -1, -1))
            require((previous is None and phase == "BEGIN") or (previous in ("BEGIN", "SAMPLE") and phase in ("SAMPLE", "REACHED", "ABORTED")), "WORLD_ROUTE_ORDER_REJECTED")
            elapsed, frames = float(values["elapsed"]), int(values["frames"])
            require(elapsed >= 0 and elapsed >= last_elapsed and frames >= last_frames and int(values["stationaryFrames"]) <= frames, "WORLD_ROUTE_CLOCK_REJECTED")
            count += phase == "SAMPLE"
            require(count <= 8, "WORLD_SAMPLE_COUNT_REJECTED")
            route_state[segment] = phase, count, elapsed, frames
        else:
            require(re.fullmatch(RAY_PATTERN, sample), "WORLD_SAMPLE_REJECTED")
            key = row["caseKey"];ray_count[key] = ray_count.get(key, 0) + 1
            require(ray_count[key] <= (3 if len(CASE_SEGMENTS[key]) == 4 and "ENTRY_TO_INVENTORY" in CASE_SEGMENTS[key] else 2), "WORLD_RAY_COUNT_REJECTED")
        rows.append(row)
    return dict(schemaVersion=1, scope=SCOPE, status="OBSERVATIONS_ONLY_NOT_TEST_PASS", partialFinalRecordDiscarded=partial, observations=rows, **{k: ident[k] for k in ("sourceCommit", "reviewedCandidateCommit", "runId", "runAttempt")})


def export(root):
    ident = visual.identity(root)
    source = root / visual.TASK / SOURCE
    destination = visual.outdir(root) / DESTINATION
    require(destination.parent.resolve() == destination.parent.absolute(), "WORLD_DESTINATION_REJECTED")
    if destination.exists() or destination.is_symlink():
        require(destination.is_file() or destination.is_symlink(), "WORLD_DESTINATION_REJECTED")
        destination.unlink()
    if not source.exists() and not source.is_symlink():
        # Export completed, but no native observation was obtained. Never a pass.
        value = dict(schemaVersion=1, scope=SCOPE, status="NOT_AVAILABLE", partialFinalRecordDiscarded=False, observations=[], **{k: ident[k] for k in ("sourceCommit", "reviewedCandidateCommit", "runId", "runAttempt")})
        visual.write(destination, value)
        return value
    require(source.is_file() and not source.is_symlink() and source.resolve() == source.absolute(), "WORLD_SOURCE_REJECTED")
    with source.open("rb") as stream:
        data = stream.read(LIMIT + 1)
    value = decode_records(data, ident)
    visual.write(destination, value)


if __name__ == "__main__":
    try:
        export(Path(__file__).resolve().parents[3])
    except Exception:
        # Fixed text only: malformed JSON may itself contain private input.
        print("WORLD_PROGRESS_EXPORT_REJECTED")
        raise SystemExit(1)
