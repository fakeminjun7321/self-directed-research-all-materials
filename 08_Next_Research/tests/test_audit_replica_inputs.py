import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_replica_inputs.py"
SPEC = importlib.util.spec_from_file_location("audit_replica_inputs", SCRIPT)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def chain(name, seed, coordinate, topology="top", em_mdp="em", density=1400.0):
    sources = {
        key: {"sha256": key}
        for key in (
            "input/Li.zmat",
            "input/c3c1pyrr.zmat",
            "input/fsi.zmat",
            "input/il.ff",
            "fftool",
        )
    }
    return {
        "chain_id": name,
        "packmol_seed": seed,
        "requested_density_kg_m3": density,
        "initial_density_kg_m3": 1400.03,
        "initial_gro": {"sha256": coordinate},
        "simbox_xyz": {"sha256": f"simbox-{coordinate}"},
        "topol_top": {"sha256": topology},
        "em_mdp": {"sha256": em_mdp},
        "packmol_completion": {"version": "21.2.3"},
        "source_evidence": sources,
    }


class ReplicaSetTests(unittest.TestCase):
    def setUp(self):
        self.chains = [
            chain("R1", 1, "coord1"),
            chain("R2", 2, "coord2"),
            chain("R3", 3, "coord3"),
        ]

    def test_distinct_comparable_set_passes(self):
        audit.validate_set(self.chains)

    def test_duplicate_seed_or_coordinates_fail(self):
        self.chains[2]["packmol_seed"] = 2
        with self.assertRaisesRegex(audit.AuditError, "seeds are not unique"):
            audit.validate_set(self.chains)
        self.chains[2]["packmol_seed"] = 3
        self.chains[2]["initial_gro"]["sha256"] = "coord2"
        with self.assertRaisesRegex(audit.AuditError, "coordinate hashes are not unique"):
            audit.validate_set(self.chains)

    def test_protocol_mismatch_fails(self):
        self.chains[2]["topol_top"]["sha256"] = "different"
        with self.assertRaisesRegex(audit.AuditError, "topology hashes differ"):
            audit.validate_set(self.chains)
        self.chains[2]["topol_top"]["sha256"] = "top"
        self.chains[2]["requested_density_kg_m3"] = 1399.0
        with self.assertRaisesRegex(audit.AuditError, "densities differ"):
            audit.validate_set(self.chains)


class SeedParserTests(unittest.TestCase):
    def test_input_and_log_seed_parsers_fail_closed(self):
        self.assertEqual(audit.parse_single_seed_line("seed 123\n", "x"), 123)
        self.assertEqual(
            audit.parse_single_observed_seed(
                "Seed for random number generator: 123\n", "x"
            ),
            123,
        )
        with self.assertRaises(audit.AuditError):
            audit.parse_single_seed_line("seed 1\nseed 2\n", "x")
        with self.assertRaises(audit.AuditError):
            audit.parse_single_observed_seed("no observed seed", "x")


if __name__ == "__main__":
    unittest.main()
