import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_l1p1x2_candidate.py"
SPEC = importlib.util.spec_from_file_location("build_l1p1x2_candidate", SCRIPT)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class PackmolSeedTests(unittest.TestCase):
    def test_inserts_one_seed_after_generated_comment(self):
        result = builder.set_packmol_seed(
            "# created by fftool\ntolerance 2.0\nfiletype xyz\n", 240101
        )
        self.assertEqual(
            result,
            "# created by fftool\nseed 240101\ntolerance 2.0\nfiletype xyz\n",
        )

    def test_identical_existing_seed_is_canonicalized(self):
        result = builder.set_packmol_seed(
            "seed    240102\ntolerance 2.0\n", 240102
        )
        self.assertEqual(result, "seed 240102\ntolerance 2.0\n")

    def test_different_or_duplicate_existing_seed_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "seed mismatch"):
            builder.set_packmol_seed("seed 1\n", 2)
        with self.assertRaisesRegex(ValueError, "more than one"):
            builder.set_packmol_seed("seed 1\nseed 1\n", 1)

    def test_seed_range_is_fail_closed(self):
        for value in (0, -1, builder.PACKMOL_MAX_SEED + 1):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    builder.validate_packmol_seed(value)

    def test_observed_seed_parser_requires_exactly_one(self):
        log = "Seed for random number generator:      240103\n"
        self.assertEqual(builder.parse_packmol_observed_seed(log), 240103)
        with self.assertRaisesRegex(ValueError, "found 0"):
            builder.parse_packmol_observed_seed("no seed here")
        with self.assertRaisesRegex(ValueError, "found 2"):
            builder.parse_packmol_observed_seed(log + log)

    def test_packmol_completion_and_em_thread_policy_fail_closed(self):
        log = """Version 21.2.3
Success!
Maximum violation of target distance: 0.0000
Maximum violation of the constraints: .9000E-02
"""
        completion = builder.parse_packmol_completion(log)
        self.assertEqual(completion["version"], "21.2.3")
        self.assertLess(completion["final_constraint_violation"], 0.01)
        self.assertEqual(builder.require_em_threads(6), 6)
        with self.assertRaisesRegex(ValueError, "exactly --threads 6"):
            builder.require_em_threads(8)
        with self.assertRaisesRegex(ValueError, "exceed 0.01"):
            builder.parse_packmol_completion(log.replace(".9000E-02", ".1100E-01"))


if __name__ == "__main__":
    unittest.main()
