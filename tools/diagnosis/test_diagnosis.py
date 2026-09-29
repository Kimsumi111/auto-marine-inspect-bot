"""Run with --reference-zip to compare all four supplied extractors, without training."""
import argparse
import ast
from pathlib import Path
import unittest
import zipfile

import numpy as np
import diagnose as target

ROOT = Path(__file__).resolve().parents[2]
REFERENCES = []


class DiagnosisTests(unittest.TestCase):
    def test_reference_feature_parity(self):
        self.assertEqual(len(REFERENCES), 4, "Supply the original XGBoost.zip")
        files = []
        for source, label in [("L-DSF-01", "정상"), ("L-DSF-01", "축정렬불량"),
                              ("L-SF-04", "베어링불량")]:
            files.append(next((ROOT / "data/vibration/2.2kW" / source / label).glob("*.csv")))
        for path in files:
            time, signal = target.load_vibration_csv(path)
            actual = target.extract_features_from_signal(time, signal)
            for reference in REFERENCES:
                expected = reference["extract_features_from_csv"](path)
                self.assertEqual(list(actual), list(expected))
                np.testing.assert_allclose(list(actual.values()), list(expected.values()), rtol=1e-12, atol=1e-12)

    def test_four_models_predict(self):
        path = next((ROOT / "data/vibration/2.2kW/L-DSF-01/정상").glob("*.csv"))
        result = target.diagnose(path, ROOT / "data")
        self.assertEqual(len(result["results"]), 4)
        for row in result["results"]:
            self.assertTrue(0 <= row["abnormalProbability"] <= 1)
            self.assertEqual(row["abnormal"], row["abnormalProbability"] >= 0.5)

    def test_outside_vibration_rejected(self):
        with self.assertRaises(ValueError):
            target.diagnose(__file__, ROOT / "data")

    def test_invalid_signal_rejected(self):
        with self.assertRaises(ValueError):
            target.extract_features_from_signal(np.zeros(100), np.arange(100.))
        with self.assertRaises(ValueError):
            target.extract_features_from_signal(np.arange(100.), np.zeros(100))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-zip", required=True)
    args, rest = parser.parse_known_args()
    with zipfile.ZipFile(args.reference_zip) as archive:
        tree = ast.parse(archive.read("XGBoost.py").decode("utf-8-sig"))
    names = {"load_vibration_csv", "calculate_sampling_frequency", "extract_features_from_signal", "extract_features_from_csv"}
    group = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            group.append(node)
            if len(group) == 4:
                scope = dict(vars(target))
                exec(compile(ast.Module(body=group, type_ignores=[]), "supplied-feature-functions", "exec"), scope)
                REFERENCES.append(scope)
                group = []
    unittest.main(argv=[__file__, *rest])
