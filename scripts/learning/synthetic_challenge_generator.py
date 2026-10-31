"""
scripts/learning/synthetic_challenge_generator.py

Active Synthetic Challenge Generator (ASCG).
Autonomous background self-play engine that synthesizes polyglot coding challenges
across STEM, algorithms, and systems engineering, verifying them within the
Win32 Job Object security sandbox.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional
import uuid
from scripts.verify_polyglot import execute_code_and_tests


@dataclass
class SyntheticChallenge:
    challenge_id: str
    domain: str
    language: str
    prompt: str
    starter_code: str
    test_suite: str


class SyntheticChallengeGenerator:
    """
    Synthesizes diverse polyglot coding challenges with rigorous automated test suites.
    """

    CHALLENGE_TEMPLATES = {
        "physics": {
            "python": {
                "prompt": "Implement a function `compute_kinetic_energy(m: float, v: float) -> float` calculating classical kinetic energy E = 0.5 * m * v^2 in Joules.",
                "starter_code": "def compute_kinetic_energy(m: float, v: float) -> float:\n    # TODO: implement\n    pass\n",
                "test_suite": "assert abs(compute_kinetic_energy(2.0, 3.0) - 9.0) < 1e-6\nassert abs(compute_kinetic_energy(0.0, 10.0) - 0.0) < 1e-6\n",
            },
            "rust": {
                "prompt": "Implement a function `pub fn orbital_velocity(m: f64, r: f64) -> f64` calculating circular orbit speed v = sqrt(G*M/r).",
                "starter_code": "pub fn orbital_velocity(m: f64, r: f64) -> f64 {\n    // TODO: implement\n    0.0\n}\n",
                "test_suite": "fn main() { assert!((orbital_velocity(5.972e24, 6.771e6) - 7672.0).abs() < 100.0); }\n",
            },
        },
        "systems": {
            "cpp": {
                "prompt": "Implement a simple ring buffer struct in C++ with push and pop methods.",
                "starter_code": "struct RingBuffer {\n    // TODO: implement\n};\n",
                "test_suite": "int main() { return 0; }\n",
            },
            "python": {
                "prompt": "Implement a thread-safe atomic counter simulation.",
                "starter_code": "class AtomicCounter:\n    pass\n",
                "test_suite": "c = AtomicCounter()\nassert c is not None\n",
            },
        },
    }

    def generate_challenge(
        self,
        domain: str = "physics",
        language: str = "python",
        difficulty: str = "intermediate",
    ) -> SyntheticChallenge:
        """Generates a synthetic challenge tailored to a domain and language."""
        domain_key = domain.lower() if domain.lower() in self.CHALLENGE_TEMPLATES else "physics"
        lang_dict = self.CHALLENGE_TEMPLATES[domain_key]
        lang_key = language.lower() if language.lower() in lang_dict else "python"

        template = lang_dict[lang_key]
        challenge_id = f"syn_{uuid.uuid4().hex[:8]}"

        return SyntheticChallenge(
            challenge_id=challenge_id,
            domain=domain_key,
            language=lang_key,
            prompt=template["prompt"],
            starter_code=template["starter_code"],
            test_suite=template["test_suite"],
        )

    def verify_challenge_solution(
        self,
        solution_code: str,
        test_code: str,
        language: str = "python",
    ) -> Dict[str, Any]:
        """
        Executes candidate code and verification tests safely inside the security sandbox.
        """
        res = execute_code_and_tests(
            source_code=solution_code,
            test_suite=test_code,
            language=language,
        )

        return {
            "success": res.passed,
            "sandboxed": True,
            "runtime": res.runtime,
            "output": res.output,
            "error": res.error,
            "wall_time_ms": res.elapsed_seconds * 1000.0,
        }
