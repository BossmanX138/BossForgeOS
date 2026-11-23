"""Regression checks for the standalone parquet helpers, not the DataForge daemon."""
import csv
from importlib import import_module, util
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ("core.convert_parquets", "--output-dir"),
    ("modules.DataForge.convert_parquets", "--output-dir"),
    ("modules.DataForge.combine_parquets", "--output-file"),
    ("modules.DataForge.combine_parquets_pyarrow", "--output-file"),
)

def rows(path):
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))

@unittest.skipUnless(util.find_spec("pyarrow") and util.find_spec("pandas"),
                     "standalone parquet helpers require pandas and PyArrow")
class ParquetPortabilityTests(unittest.TestCase):
    def setUp(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / "fixture input"
        self.source.mkdir()
        pq.write_table(pa.table({"count": [2, 3]}), self.source / "b.PARQUET")
        pq.write_table(pa.table({"count": [1]}), self.source / "a.parquet")
        (self.source / "notes.txt").write_text("ignore this", encoding="utf-8")
        self.expected = [{"count": "1"}, {"count": "2"}, {"count": "3"}]

    def test_entrypoints_write_only_to_explicit_destination(self):
        for i, (module, option) in enumerate(CASES):
            with self.subTest(module=module):
                run = import_module(module).main
                output = self.root / f"selected output {i}"
                if option == "--output-file":
                    output = output.with_suffix(".csv")
                before = {p.name: p.read_bytes() for p in self.source.iterdir()}
                self.assertEqual(run(["--input-dir", str(self.source), option, str(output)]), 0)
                if option == "--output-dir":
                    actual = rows(output / "a.csv") + rows(output / "b.csv")
                else:
                    actual = rows(output)
                self.assertEqual(actual, self.expected)
                self.assertEqual({p.name: p.read_bytes() for p in self.source.iterdir()}, before)

    def test_neither_missing_source_nor_nested_output_creates_output(self):
        for module, option in CASES:
            with self.subTest(module=module):
                run = import_module(module).main
                suffix = ".csv" if option == "--output-file" else ""
                for source, output in (
                    (self.root / "missing", self.root / ("outside"+suffix)),
                    (self.source, self.source / ("nested"+suffix)),
                ):
                    with self.assertRaises(SystemExit) as exc:
                        run(["--input-dir", str(source), option, str(output)])
                    self.assertEqual(exc.exception.code, 2)
                    self.assertFalse(output.exists())

    def test_existing_csv_is_not_overwritten(self):
        for i, (module, option) in enumerate(CASES):
            with self.subTest(module=module):
                run = import_module(module).main
                selected = self.root / f"already exists {i}"
                if option == "--output-file":
                    selected = selected.with_suffix(".csv")
                    csv_output = selected
                else:
                    selected.mkdir()
                    csv_output = selected / "a.csv"
                csv_output.write_text("keep it", encoding="utf-8")
                with self.assertRaises(SystemExit) as exc:
                    run(["--input-dir", str(self.source), option, str(selected)])
                self.assertEqual(exc.exception.code, 2)
                self.assertEqual(csv_output.read_text(encoding="utf-8"), "keep it")

    def test_direct_scripts_show_help_without_writing_outputs(self):
        for module, option in CASES:
            with self.subTest(module=module):
                self.assertTrue(callable(import_module(module).main))
                script = ROOT.joinpath(*module.split(".")).with_suffix(".py")
                result = subprocess.run([sys.executable, str(script), "--help"],
                                        cwd=self.root, capture_output=True, text=True,
                                        timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("--input-dir", result.stdout)
                self.assertIn(option, result.stdout)
                self.assertFalse((self.root / "combined_dataset.csv").exists())

if __name__ == "__main__":
    unittest.main()
