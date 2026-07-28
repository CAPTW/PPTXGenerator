from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from phase4_external_test_support import (
    load_external_execution_module,
    request_payload,
)


class Phase4ExternalExecutionRecordTests(unittest.TestCase):
    def _record(self, *, execution_id: str = "exec_0123456789abcdef0123"):
        contracts = load_external_execution_module("contracts")
        record_module = load_external_execution_module("record")
        payload = request_payload()
        payload["execution_id"] = execution_id
        request = contracts.build_external_execution_request(payload)
        request_bytes = contracts.canonical_request_bytes(request)
        record = record_module.build_blocked_execution_record(
            request,
            request_artifact_path="requests/request.json",
            request_bytes=request_bytes,
            created_at="2026-07-17T00:00:00+09:00",
        )
        return contracts, record_module, request, request_bytes, record

    def test_blocked_record_is_deeply_immutable_and_hash_bound(self) -> None:
        _, record_module, _, _, record = self._record()

        self.assertEqual(record.status, "blocked")
        self.assertFalse(record.transport_attempted)
        self.assertEqual(record.transport_call_count, 0)
        self.assertEqual(record.outputs, ())
        self.assertEqual(
            record.record_hash,
            record_module.compute_execution_record_hash(record),
        )
        with self.assertRaises(ValidationError):
            record.execution_id = "exec_ffffffffffffffffffff"  # type: ignore[misc]
        with self.assertRaises(ValidationError):
            record.request_artifact.hash.digest = "0" * 64  # type: ignore[misc]
        with self.assertRaises(ValidationError):
            record.input_artifacts[0].sha256 = "0" * 64  # type: ignore[misc]

    def test_writer_rejects_every_existing_final_target(self) -> None:
        _, record_module, _, _, record = self._record()
        _, _, _, _, different_record = self._record(
            execution_id="exec_ffffffffffffffffffff"
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "records").mkdir()
            path = record_module.write_execution_record(
                root, "records/execution-record.json", record
            )
            self.assertEqual(
                path.read_bytes(),
                record_module.canonical_execution_record_bytes(record),
            )
            with self.assertRaises(record_module.ExecutionRecordImmutableError):
                record_module.write_execution_record(
                    root, "records/execution-record.json", record
                )
            with self.assertRaises(record_module.ExecutionRecordImmutableError):
                record_module.write_execution_record(
                    root, "records/execution-record.json", different_record
                )

            empty = root / "records" / "empty.json"
            empty.touch()
            with self.assertRaises(record_module.ExecutionRecordImmutableError):
                record_module.write_execution_record(root, "records/empty.json", record)

            directory = root / "records" / "directory.json"
            directory.mkdir()
            with self.assertRaises(record_module.ExecutionRecordPathError):
                record_module.write_execution_record(
                    root, "records/directory.json", record
                )

    def test_writer_rejects_parent_symlink_and_target_symlink_when_supported(self) -> None:
        _, record_module, _, _, record = self._record()
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            root = base / "run"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            try:
                (root / "linked-parent").symlink_to(outside, target_is_directory=True)
                (root / "target-link.json").symlink_to(outside / "record.json")
            except OSError as exc:
                self.skipTest(f"Windows symlink creation unavailable: {exc}")

            with self.assertRaises(record_module.ExecutionRecordPathError):
                record_module.write_execution_record(
                    root, "linked-parent/record.json", record
                )
            with self.assertRaises(record_module.ExecutionRecordPathError):
                record_module.write_execution_record(root, "target-link.json", record)

    @unittest.skipUnless(os.name == "nt", "junction coverage is Windows-specific")
    def test_writer_rejects_parent_junction_when_supported(self) -> None:
        _, record_module, _, _, record = self._record()
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            root = base / "run"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            junction = root / "junction"
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                self.skipTest("Windows junction creation unavailable in this environment")
            with self.assertRaises(record_module.ExecutionRecordPathError):
                record_module.write_execution_record(
                    root, "junction/record.json", record
                )


if __name__ == "__main__":
    unittest.main()
