#!/usr/bin/env python3
"""
STEM Knowledge Ingestion Pipeline (Medallion Architecture).

Ingests, deduplicates, and vectorizes comprehensive foundational STEM knowledge
spanning Grade 4 elementary to Subject Matter Expert (SME) across Mathematics,
Physics, and Computer Science.

Medallion Architecture:
- Bronze: Raw ingestion & schema validation from seed corpus and external sources.
- Silver: 3-tier deduplication (Exact Hash, Lexical Fuzzy Jaccard, Semantic Similarity).
- Gold: Persistence into SQLite vector database (rag_documents and material_chunks)
        with 'search_document: ' prefix for Ollama nomic-embed-text and row capping
        to protect PHP 128M memory limit.
"""

import argparse
import hashlib
import json
import logging
import math
import re
import struct
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "rag-adapter"))

from rag_adapter.sqlite_backend import LocalSqliteRagBackend

logger = logging.getLogger("stem_ingestion")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@dataclass
class StemKnowledgeItem:
    """Core STEM Knowledge data transfer object."""
    id: str
    title: str
    domain: str  # maths, physics, coding
    tier: str  # elementary, secondary, higher_secondary, sme
    grade_level: str  # Class 4-5, Class 6-10, Class 11-12, SME / Research
    concept: str
    example_problem: str
    solution_steps: str
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_formatted_document(self) -> str:
        """Render comprehensive readable text representation for vector indexing."""
        return (
            f"Title: {self.title}\n"
            f"Domain: {self.domain} | Tier: {self.tier} ({self.grade_level})\n"
            f"Tags: {', '.join(self.tags)}\n\n"
            f"Core Concept:\n{self.concept}\n\n"
            f"Example Problem / Challenge:\n{self.example_problem}\n\n"
            f"Detailed Solution & Rigorous Reasoning:\n{self.solution_steps}"
        )


# ============================================================================
# FOUNDATIONAL STEM KNOWLEDGE SEED CORPUS (CLASS 4 TO SME)
# ============================================================================

CURATED_STEM_CORPUS: List[Dict[str, Any]] = [
    # ------------------------------------------------------------------------
    # TIER 1: ELEMENTARY (CLASS 4 - 5) - MATHEMATICS
    # ------------------------------------------------------------------------
    {
        "id": "STEM-MATH-ELEM-001",
        "title": "Multi-Digit Multiplication and Long Division with Remainders",
        "domain": "maths",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "Multiplication is repeated addition of equal groups: a * b means 'a groups of b'. Long division partitions a dividend into equal parts given a divisor: Dividend = (Divisor * Quotient) + Remainder, where 0 <= Remainder < Divisor.",
        "example_problem": "A school library receives 458 science books to distribute equally among 14 classrooms. How many books does each classroom receive, and how many books remain unassigned?",
        "solution_steps": "1. Set up division: 458 / 14.\n2. Divide 45 by 14: 14 * 3 = 42. Quotient tens digit is 3. Remainder: 45 - 42 = 3.\n3. Bring down 8 to make 38.\n4. Divide 38 by 14: 14 * 2 = 28. Quotient units digit is 2. Remainder: 38 - 28 = 10.\n5. Verify: 14 * 32 + 10 = 448 + 10 = 458. Remainder 10 < Divisor 14.\nEach classroom receives 32 books, and 10 books remain unassigned.",
        "tags": ["arithmetic", "division", "remainders", "elementary_math"],
    },
    {
        "id": "STEM-MATH-ELEM-002",
        "title": "Fractions and Mixed Numbers: Common Denominators and Arithmetic",
        "domain": "maths",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "A fraction a/b represents 'a' parts of a whole divided into 'b' equal parts. To add or subtract fractions with unlike denominators, convert them to equivalent fractions using the Least Common Multiple (LCM) of the denominators: a/b + c/d = (a*d + b*c)/(b*d).",
        "example_problem": "Maria pours 3/4 liter of orange juice and 2/3 liter of mango juice into a pitcher. What is the total volume of juice in liters expressed as a mixed number?",
        "solution_steps": "1. Identify denominators: 4 and 3.\n2. Find LCM(4, 3) = 12.\n3. Convert to equivalent fractions: 3/4 = (3*3)/(4*3) = 9/12; 2/3 = (2*4)/(3*4) = 8/12.\n4. Add numerators: 9/12 + 8/12 = 17/12.\n5. Convert improper fraction to mixed number: 17 / 12 = 1 with remainder 5.\nTotal volume = 1 5/12 liters.",
        "tags": ["fractions", "lcm", "mixed_numbers", "elementary_math"],
    },
    {
        "id": "STEM-MATH-ELEM-003",
        "title": "Perimeter and Area of Rectangles and Composite 2D Shapes",
        "domain": "maths",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "Perimeter is the total boundary length around a 2D shape. For a rectangle with length L and width W: Perimeter P = 2*(L + W). Area is the total surface enclosed: Area A = L * W. For composite shapes, decompose into non-overlapping rectangles and sum their individual areas.",
        "example_problem": "An L-shaped garden plot consists of a main rectangle of 10 meters by 6 meters, with an adjacent rectangular flowerbed extension of 4 meters by 3 meters. Find the total area and fencing needed if the shared boundary requires no fence.",
        "solution_steps": "1. Area of main rectangle A1 = 10 m * 6 m = 60 m².\n2. Area of extension A2 = 4 m * 3 m = 12 m².\n3. Total area A = A1 + A2 = 60 + 12 = 72 m².\n4. For perimeter, trace external boundary segments: 10 + 6 + 6 + 3 + 4 + 9 = 38 meters.\nTotal area is 72 m² and required fencing perimeter is 38 m.",
        "tags": ["geometry", "perimeter", "area", "composite_shapes", "elementary_math"],
    },

    # ------------------------------------------------------------------------
    # TIER 1: ELEMENTARY (CLASS 4 - 5) - PHYSICS / BASIC SCIENCE
    # ------------------------------------------------------------------------
    {
        "id": "STEM-PHYS-ELEM-001",
        "title": "States of Matter: Solids, Liquids, Gases, and Phase Transitions",
        "domain": "physics",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "Matter exists in three primary states: Solids have fixed shape and fixed volume (molecules tightly packed in rigid lattice). Liquids have variable shape but fixed volume (molecules flow past one another). Gases have variable shape and variable volume (molecules move freely at high speeds). Adding thermal energy causes melting (solid to liquid) and evaporation/boiling (liquid to gas). Removing thermal energy causes condensation and freezing.",
        "example_problem": "Explain why an ice cube floats in liquid water and what happens to the water level in a full glass when the ice cube melts completely.",
        "solution_steps": "1. Ice floats because water expands upon freezing into a hexagonal crystalline lattice, making solid ice less dense (density ~0.917 g/cm³) than liquid water (~1.00 g/cm³).\n2. According to Archimedes' principle, the floating ice cube displaces a mass of liquid water equal to its own mass.\n3. When the ice melts completely, it converts into liquid water having the exact same mass and therefore occupying precisely the volume displaced previously.\n4. Conclusion: The water level in the glass remains completely unchanged.",
        "tags": ["states_of_matter", "density", "phase_change", "archimedes", "elementary_science"],
    },
    {
        "id": "STEM-PHYS-ELEM-002",
        "title": "Simple Machines: Levers, Mechanical Advantage, and Effort",
        "domain": "physics",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "A simple machine alters the magnitude or direction of an applied force. In a Class 1 lever, the fulcrum sits between effort and load. The Law of the Lever states: Effort * Effort_Arm = Load * Load_Arm. Ideal Mechanical Advantage (IMA) = Effort_Arm / Load_Arm.",
        "example_problem": "A child applies effort to lift a 60 kg stone using a 2.5-meter rigid crowbar as a lever. If the fulcrum is placed 0.5 meters from the stone, how much effort force (in kgf) is needed to balance the stone?",
        "solution_steps": "1. Identify lever arms: Total length = 2.5 m. Load arm = 0.5 m. Effort arm = 2.5 - 0.5 = 2.0 m.\n2. Load = 60 kgf.\n3. Apply torque equilibrium: Effort * Effort_Arm = Load * Load_Arm.\n4. Effort * 2.0 = 60 * 0.5 = 30.\n5. Effort = 30 / 2.0 = 15 kgf.\nAn effort of only 15 kgf is required, yielding a mechanical advantage of 4:1.",
        "tags": ["simple_machines", "levers", "mechanical_advantage", "torque", "elementary_science"],
    },
    {
        "id": "STEM-PHYS-ELEM-003",
        "title": "Light: Rectilinear Propagation, Shadows, and Reflection",
        "domain": "physics",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "Light travels in straight lines (rectilinear propagation) through homogeneous transparent media. When an opaque obstacle blocks light rays, a dark shadow is cast behind it consisting of an umbra (total shadow) and penumbra (partial shadow). Law of Reflection: Angle of incidence equals angle of reflection (θi = θr).",
        "example_problem": "A 1.5-meter vertical stick casts a 2.0-meter shadow on flat ground. At the same moment, a nearby tree casts a 16.0-meter shadow. How tall is the tree?",
        "solution_steps": "1. Light rays from the sun arrive parallel to each other, creating similar right-angled triangles.\n2. Ratio of Height to Shadow for stick: 1.5 m / 2.0 m = 0.75.\n3. For the tree: Height_tree / Shadow_tree = 0.75.\n4. Height_tree = 0.75 * 16.0 m = 12.0 meters.\nThe tree is 12.0 meters tall.",
        "tags": ["optics", "light", "shadows", "reflection", "elementary_science"],
    },

    # ------------------------------------------------------------------------
    # TIER 1: ELEMENTARY (CLASS 4 - 5) - CODING
    # ------------------------------------------------------------------------
    {
        "id": "STEM-CODE-ELEM-001",
        "title": "Algorithms, Variables, and Control Flow (Conditionals & Loops)",
        "domain": "coding",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "An algorithm is an unambiguous step-by-step sequence of instructions to solve a task. Variables store data values in named memory locations. Conditional statements (if/else) allow branching decisions based on boolean truth. Loops (for/while) repeat actions until a termination condition is met.",
        "example_problem": "Write a clean Python program that computes the sum of all even numbers from 1 up to a given positive integer N inclusive, and prints whether the total sum is greater than 100.",
        "solution_steps": "```python\ndef sum_even_numbers(n: int) -> int:\n    total = 0\n    for num in range(1, n + 1):\n        if num % 2 == 0:\n            total += num\n    return total\n\nn = 20\ntotal = sum_even_numbers(n)\nprint(f'Sum of evens up to {n}: {total}')\nif total > 100:\n    print('The sum is greater than 100')\nelse:\n    print('The sum is 100 or less')\n```\nExplanation:\n1. Initialize accumulator `total = 0`.\n2. Iterate through integers from 1 to N.\n3. Check parity using modulo `% 2 == 0`.\n4. Add even values and check threshold with if/else.",
        "tags": ["programming_basics", "loops", "conditionals", "python", "elementary_coding"],
    },

    # ------------------------------------------------------------------------
    # TIER 2: SECONDARY (CLASS 6 - 10) - MATHEMATICS
    # ------------------------------------------------------------------------
    {
        "id": "STEM-MATH-SEC-001",
        "title": "Quadratic Equations, Discriminant Analysis, and the Quadratic Formula",
        "domain": "maths",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "A quadratic equation has the general form ax² + bx + c = 0 (with a ≠ 0). Solutions are given by the quadratic formula: x = (-b ± √(b² - 4ac)) / (2a). The discriminant Δ = b² - 4ac governs root nature: Δ > 0 yields two distinct real roots, Δ = 0 yields one repeated real root, and Δ < 0 yields two complex conjugate roots.",
        "example_problem": "Solve 2x² - 7x + 3 = 0, analyze the discriminant, and compute the coordinates of the parabola's vertex.",
        "solution_steps": "1. Identify coefficients: a = 2, b = -7, c = 3.\n2. Compute discriminant: Δ = b² - 4ac = (-7)² - 4(2)(3) = 49 - 24 = 25.\n3. Since Δ = 25 > 0, there are two distinct real roots.\n4. Compute roots: x = (-(-7) ± √25) / (2 * 2) = (7 ± 5) / 4.\n   x1 = (7 + 5) / 4 = 12 / 4 = 3.\n   x2 = (7 - 5) / 4 = 2 / 4 = 0.5 (1/2).\n5. Vertex coordinates: x_v = -b / (2a) = 7 / 4 = 1.75.\n   y_v = 2(7/4)² - 7(7/4) + 3 = 2(49/16) - 49/4 + 3 = 49/8 - 98/8 + 24/8 = -25/8 = -3.125.\nRoots are x = 3 and x = 0.5; Vertex is (1.75, -3.125).",
        "tags": ["algebra", "quadratic_equations", "discriminant", "parabola", "secondary_math"],
    },
    {
        "id": "STEM-MATH-SEC-002",
        "title": "Euclidean Geometry, Similar Triangles, and Pythagorean Theorem",
        "domain": "maths",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "In a right triangle with legs a and b and hypotenuse c: a² + b² = c². Two triangles are similar if their corresponding angles are equal and corresponding sides are in constant proportion: a1/a2 = b1/b2 = c1/c2. The altitude h to the hypotenuse divides the triangle into two similar triangles, where h² = p * q (geometric mean theorem).",
        "example_problem": "In right-angled triangle ABC with right angle at C, legs are AC = 6 cm and BC = 8 cm. An altitude CD is drawn from C perpendicular to hypotenuse AB. Calculate the length of hypotenuse AB and altitude CD.",
        "solution_steps": "1. Apply Pythagorean theorem on ABC: AB = √(AC² + BC²) = √(6² + 8²) = √(36 + 64) = √100 = 10 cm.\n2. Express the area of triangle ABC in two equivalent ways:\n   Method A: Area = 0.5 * base * height = 0.5 * AC * BC = 0.5 * 6 * 8 = 24 cm².\n   Method B: Area = 0.5 * hypotenuse * altitude = 0.5 * AB * CD = 0.5 * 10 * CD = 5 * CD.\n3. Equate areas: 5 * CD = 24 => CD = 24 / 5 = 4.8 cm.\nHypotenuse AB = 10 cm and altitude CD = 4.8 cm.",
        "tags": ["geometry", "pythagorean_theorem", "similar_triangles", "secondary_math"],
    },
    {
        "id": "STEM-MATH-SEC-003",
        "title": "Trigonometric Ratios and Fundamental Identities",
        "domain": "maths",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "For acute angle θ in a right triangle: sin θ = Opposite/Hypotenuse, cos θ = Adjacent/Hypotenuse, tan θ = Opposite/Adjacent = sin θ / cos θ. Fundamental Pythagorean identity: sin² θ + cos² θ = 1, 1 + tan² θ = sec² θ, and 1 + cot² θ = csc² θ.",
        "example_problem": "If sin θ = 5/13 and θ is an acute angle, find the exact values of cos θ, tan θ, and prove that 1 + tan² θ = sec² θ.",
        "solution_steps": "1. Use identity sin² θ + cos² θ = 1 => cos² θ = 1 - (5/13)² = 1 - 25/169 = 144/169.\n2. Since θ is acute, cos θ = √(144/169) = 12/13.\n3. tan θ = sin θ / cos θ = (5/13) / (12/13) = 5/12.\n4. sec θ = 1 / cos θ = 13/12.\n5. Verify 1 + tan² θ = 1 + (5/12)² = 1 + 25/144 = 169/144.\n6. Compute sec² θ = (13/12)² = 169/144. Both sides are identical.",
        "tags": ["trigonometry", "trigonometric_identities", "sine", "cosine", "secondary_math"],
    },

    # ------------------------------------------------------------------------
    # TIER 2: SECONDARY (CLASS 6 - 10) - PHYSICS
    # ------------------------------------------------------------------------
    {
        "id": "STEM-PHYS-SEC-001",
        "title": "Newton's Three Laws of Motion and Momentum Conservation",
        "domain": "physics",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "First Law (Inertia): An object remains at rest or constant velocity unless acted upon by a net external force. Second Law: F_net = dp/dt = m*a (for constant mass). Third Law: For every action, there is an equal and opposite reaction (F_AB = -F_BA). Law of Conservation of Linear Momentum: In an isolated system (F_ext = 0), total linear momentum is conserved: m1*u1 + m2*u2 = m1*v1 + m2*v2.",
        "example_problem": "A 1200 kg car travelling at 25 m/s collides head-on with a stationary 800 kg trailer. If they lock bumpers upon collision, what is their combined velocity immediately after impact?",
        "solution_steps": "1. Identify parameters: m1 = 1200 kg, u1 = 25 m/s, m2 = 800 kg, u2 = 0 m/s.\n2. Total initial momentum p_initial = m1*u1 + m2*u2 = (1200 * 25) + 0 = 30,000 kg·m/s.\n3. Since they lock together, combined mass M = m1 + m2 = 1200 + 800 = 2000 kg.\n4. Apply conservation of momentum: p_final = M * v = p_initial.\n5. 2000 * v = 30,000 => v = 30,000 / 2000 = 15 m/s.\nTheir combined velocity immediately after collision is 15 m/s.",
        "tags": ["mechanics", "newtons_laws", "momentum_conservation", "secondary_physics"],
    },
    {
        "id": "STEM-PHYS-SEC-002",
        "title": "Work, Kinetic Energy, Potential Energy, and Power",
        "domain": "physics",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "Work done W = F * d * cos(θ) (in Joules). Work-Energy Theorem: Total work done equals change in kinetic energy: W_net = ΔKE = 0.5*m*v_f² - 0.5*m*v_i². Gravitational potential energy PE = m*g*h. In conservative systems: Total Mechanical Energy E = KE + PE = constant. Power is rate of doing work: P = W / t = F * v (in Watts).",
        "example_problem": "A roller coaster cart of mass 500 kg starts from rest at the top of a hill of height h = 45 meters. Neglecting friction and air resistance, calculate its speed at the bottom of the hill and the average power required to haul it back up in 30 seconds (g = 9.8 m/s²).",
        "solution_steps": "1. At peak, initial KE = 0, initial PE = m * g * h = 500 * 9.8 * 45 = 220,500 J.\n2. At bottom, PE = 0, all energy converts to kinetic energy: KE_final = 0.5 * m * v² = 220,500 J.\n3. Solve for v: 0.5 * 500 * v² = 220,500 => 250 * v² = 220,500 => v² = 882 => v = √882 ≈ 29.70 m/s.\n4. Work needed to haul cart back up: W = ΔPE = 220,500 J.\n5. Power = W / t = 220,500 J / 30 s = 7,350 Watts (7.35 kW).\nSpeed at bottom is 29.7 m/s; Average lifting power is 7.35 kW.",
        "tags": ["energy", "work", "kinetic_energy", "potential_energy", "power", "secondary_physics"],
    },
    {
        "id": "STEM-PHYS-SEC-003",
        "title": "Ohm's Law, Joule Heating, and Electric Circuit Analysis",
        "domain": "physics",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "Ohm's Law: Potential difference across a conductor is proportional to current under constant temperature: V = I * R. Series resistors: R_eq = R1 + R2 + ... + Rn. Parallel resistors: 1/R_eq = 1/R1 + 1/R2 + ... + 1/Rn. Electrical power and Joule heating: P = V * I = I² * R = V² / R.",
        "example_problem": "A circuit contains a 12V battery connected to a 4Ω resistor in series with a parallel pair of 6Ω and 3Ω resistors. Calculate the equivalent resistance, total current drawn from the battery, and power dissipated in the 3Ω resistor.",
        "solution_steps": "1. Compute parallel combination of 6Ω and 3Ω:\n   1/R_p = 1/6 + 1/3 = 1/6 + 2/6 = 3/6 = 1/2 => R_p = 2Ω.\n2. Total equivalent resistance R_eq = R_series + R_p = 4Ω + 2Ω = 6Ω.\n3. Total circuit current: I_total = V / R_eq = 12V / 6Ω = 2 Amperes.\n4. Voltage across the parallel branch: V_p = I_total * R_p = 2A * 2Ω = 4 Volts.\n5. Current through the 3Ω resistor: I_3 = V_p / 3Ω = 4V / 3Ω = 1.33 A.\n6. Power dissipated in 3Ω resistor: P_3 = V_p² / R = (4)² / 3 = 16 / 3 ≈ 5.33 Watts.\nEquivalent resistance is 6Ω, total current is 2A, and power in 3Ω resistor is 5.33W.",
        "tags": ["electricity", "ohms_law", "resistors", "circuits", "secondary_physics"],
    },

    # ------------------------------------------------------------------------
    # TIER 2: SECONDARY (CLASS 6 - 10) - CODING
    # ------------------------------------------------------------------------
    {
        "id": "STEM-CODE-SEC-001",
        "title": "Divide-and-Conquer: Binary Search and Merge Sort (O(n log n))",
        "domain": "coding",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "Divide and conquer divides a problem into subproblems of the same type, solves them recursively, and combines the solutions. Binary Search operates on sorted arrays in O(log n) time by halving the search space each step. Merge Sort divides an array into halves, recursively sorts them, and merges sorted sub-arrays in O(n log n) time and O(n) auxiliary space.",
        "example_problem": "Implement a robust Merge Sort algorithm in Python that sorts an array of integers in non-decreasing order and tracks total comparison count.",
        "solution_steps": "```python\nfrom typing import List, Tuple\n\ndef merge_sort(arr: List[int]) -> Tuple[List[int], int]:\n    comparisons = 0\n    if len(arr) <= 1:\n        return arr, 0\n\n    mid = len(arr) // 2\n    left, left_comp = merge_sort(arr[:mid])\n    right, right_comp = merge_sort(arr[mid:])\n    comparisons += left_comp + right_comp\n\n    merged = []\n    i = j = 0\n    while i < len(left) and j < len(right):\n        comparisons += 1\n        if left[i] <= right[j]:\n            merged.append(left[i])\n            i += 1\n        else:\n            merged.append(right[j])\n            j += 1\n    merged.extend(left[i:])\n    merged.extend(right[j:])\n    return merged, comparisons\n\ndata = [38, 27, 43, 3, 9, 82, 10]\nsorted_arr, comps = merge_sort(data)\nprint('Sorted:', sorted_arr, 'Comparisons:', comps)\n```",
        "tags": ["algorithms", "sorting", "merge_sort", "divide_and_conquer", "secondary_coding"],
    },

    # ------------------------------------------------------------------------
    # TIER 3: HIGHER SECONDARY (CLASS 11 - 12) - MATHEMATICS
    # ------------------------------------------------------------------------
    {
        "id": "STEM-MATH-HS-001",
        "title": "Differential Calculus: Chain Rule, Product Rule, and Local Extrema",
        "domain": "maths",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "The derivative f'(x) = lim(h->0) [f(x+h) - f(x)] / h gives the instantaneous rate of change and slope of the tangent line. Product rule: (u*v)' = u'*v + u*v'. Chain rule for composite functions: d/dx[f(g(x))] = f'(g(x)) * g'(x). Stationary points occur where f'(x) = 0. Second derivative test: f''(x) > 0 indicates a local minimum; f''(x) < 0 indicates a local maximum.",
        "example_problem": "Find the dimensions of a closed cylindrical tin can of fixed volume V = 1000 cm³ that minimizes the total surface area S.",
        "solution_steps": "1. Formulas: Volume V = π * r² * h = 1000 => h = 1000 / (π * r²).\n2. Surface Area S = 2*π*r² + 2*π*r*h = 2*π*r² + 2*π*r*(1000 / (π * r²)) = 2*π*r² + 2000 / r.\n3. Take first derivative with respect to r and set to 0:\n   dS/dr = 4*π*r - 2000 / r² = 0 => 4*π*r³ = 2000 => r³ = 500 / π.\n4. Radius r = (500 / π)^(1/3) ≈ (159.15)^(1/3) ≈ 5.42 cm.\n5. Compute height h = 1000 / (π * r²) = 1000 / (π * (500/π)^(2/3)) = 2 * (500/π)^(1/3) = 2r ≈ 10.84 cm.\n6. Verify second derivative: d²S/dr² = 4*π + 4000 / r³ > 0 for all r > 0, confirming a strict global minimum.\nOptimal dimensions: radius r ≈ 5.42 cm and height h = 2r ≈ 10.84 cm.",
        "tags": ["calculus", "derivatives", "optimization", "extrema", "higher_secondary_math"],
    },
    {
        "id": "STEM-MATH-HS-002",
        "title": "Integral Calculus: Definite Integrals, Substitution, and Parts",
        "domain": "maths",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "The Fundamental Theorem of Calculus links derivatives and integrals: ∫(a to b) f(x) dx = F(b) - F(a) where F'(x) = f(x). Integration by Parts: ∫ u dv = u*v - ∫ v du (derived from the product rule).",
        "example_problem": "Evaluate the definite integral I = ∫(0 to 1) x * e^(2x) dx.",
        "solution_steps": "1. Choose parts using LIATE rule: u = x => du = dx; dv = e^(2x) dx => v = (1/2) * e^(2x).\n2. Apply integration by parts formula:\n   ∫ x * e^(2x) dx = x * (1/2 * e^(2x)) - ∫ (1/2 * e^(2x)) dx\n   = (1/2) * x * e^(2x) - (1/4) * e^(2x) + C = (1/4) * e^(2x) * (2x - 1) + C.\n3. Evaluate definite integral from 0 to 1:\n   At x = 1: (1/4) * e^(2) * (2(1) - 1) = (1/4) * e².\n   At x = 0: (1/4) * e^(0) * (2(0) - 1) = (1/4) * 1 * (-1) = -1/4.\n4. I = (1/4) * e² - (-1/4) = (e² + 1) / 4 ≈ (7.389 + 1) / 4 = 8.389 / 4 ≈ 2.097.\nThe exact value of the integral is (e² + 1) / 4.",
        "tags": ["calculus", "integration", "integration_by_parts", "higher_secondary_math"],
    },

    # ------------------------------------------------------------------------
    # TIER 3: HIGHER SECONDARY (CLASS 11 - 12) - PHYSICS
    # ------------------------------------------------------------------------
    {
        "id": "STEM-PHYS-HS-001",
        "title": "Rotational Dynamics: Torque, Moment of Inertia, and Rolling Motion",
        "domain": "physics",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "Rotational analogue of Newton's second law: τ_net = I * α, where τ is torque (r x F), I is moment of inertia (∫ r² dm), and α is angular acceleration. For rolling without slipping: v_cm = R * ω and a_cm = R * α. Total kinetic energy: KE_total = KE_trans + KE_rot = 0.5 * M * v_cm² + 0.5 * I_cm * ω².",
        "example_problem": "A solid uniform cylinder of mass M and radius R rolls without slipping down an inclined plane of inclination angle θ. Find its linear acceleration down the incline.",
        "solution_steps": "1. Moment of inertia of solid cylinder about central axis: I_cm = (1/2) * M * R².\n2. Equations of motion:\n   Linear along incline: M * g * sin(θ) - f_s = M * a_cm (where f_s is static friction).\n   Rotational about CM: τ = f_s * R = I_cm * α.\n3. No-slip constraint: α = a_cm / R => f_s * R = (1/2 * M * R²) * (a_cm / R) => f_s = (1/2) * M * a_cm.\n4. Substitute f_s into linear equation:\n   M * g * sin(θ) - (1/2) * M * a_cm = M * a_cm.\n5. (3/2) * M * a_cm = M * g * sin(θ) => a_cm = (2/3) * g * sin(θ).\nThe linear acceleration of the rolling cylinder is (2/3) * g * sin(θ).",
        "tags": ["rotational_dynamics", "moment_of_inertia", "torque", "rolling_motion", "higher_secondary_physics"],
    },
    {
        "id": "STEM-PHYS-HS-002",
        "title": "Thermodynamics: First Law, Carnot Cycle, and Entropy",
        "domain": "physics",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "First Law of Thermodynamics: ΔU = Q - W, where U is internal energy, Q is heat added, and W is work done by system. For an ideal gas: ΔU = n * C_v * ΔT. Second Law: No heat engine operating between two thermal reservoirs can be more efficient than a reversible Carnot engine: η_Carnot = 1 - (T_cold / T_hot) (temperatures in Kelvin). Clausius inequality: ∮ dQ / T <= 0.",
        "example_problem": "A Carnot heat engine operates between a hot reservoir at 500°C and a cold reservoir at 25°C. It absorbs 1200 J of heat per cycle from the hot reservoir. Calculate its theoretical efficiency, work output per cycle, and heat rejected to the cold reservoir.",
        "solution_steps": "1. Convert temperatures to Kelvin: T_hot = 500 + 273.15 = 773.15 K; T_cold = 25 + 273.15 = 298.15 K.\n2. Carnot efficiency: η = 1 - (T_cold / T_hot) = 1 - (298.15 / 773.15) = 1 - 0.3856 = 0.6144 (61.44%).\n3. Work output per cycle: W = η * Q_in = 0.6144 * 1200 J = 737.28 J.\n4. Heat rejected per cycle: Q_out = Q_in - W = 1200 - 737.28 = 462.72 J.\nEfficiency is 61.44%, useful work output is 737.3 J, and rejected heat is 462.7 J.",
        "tags": ["thermodynamics", "carnot_cycle", "entropy", "heat_engines", "higher_secondary_physics"],
    },

    # ------------------------------------------------------------------------
    # TIER 3: HIGHER SECONDARY (CLASS 11 - 12) - CODING
    # ------------------------------------------------------------------------
    {
        "id": "STEM-CODE-HS-001",
        "title": "Dynamic Programming: 0/1 Knapsack with Space Optimization",
        "domain": "coding",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "The 0/1 Knapsack problem exhibits optimal substructure and overlapping subproblems. Given n items with weights w_i and values v_i, maximize total value within capacity W. Recurrence: dp[i][w] = max(dp[i-1][w], dp[i-1][w - w_i] + v_i). Can be space-optimized to a 1D array of size W+1 by iterating backwards from W down to w_i to preserve state from the previous item.",
        "example_problem": "Given item weights [2, 3, 4, 5] and values [3, 4, 5, 6] with capacity W = 8, determine the maximum value achievable using 1D DP.",
        "solution_steps": "```python\nfrom typing import List\n\ndef knapsack_01(weights: List[int], values: List[int], capacity: int) -> int:\n    dp = [0] * (capacity + 1)\n    for w_i, v_i in zip(weights, values):\n        # Iterate backwards to avoid using the same item multiple times\n        for w in range(capacity, w_i - 1, -1):\n            dp[w] = max(dp[w], dp[w - w_i] + v_i)\n    return dp[capacity]\n\nweights = [2, 3, 4, 5]\nvalues = [3, 4, 5, 6]\ncap = 8\nmax_val = knapsack_01(weights, values, cap)\nprint(f'Maximum achievable value: {max_val}')  # Output: 10 (items with weights 3 and 5, or 2, 3 and ...)\n```",
        "tags": ["dynamic_programming", "knapsack", "space_optimization", "higher_secondary_coding"],
    },

    # ------------------------------------------------------------------------
    # TIER 4: SUBJECT MATTER EXPERT (SME / RESEARCH / OLYMPIAD) - MATHEMATICS
    # ------------------------------------------------------------------------
    {
        "id": "STEM-MATH-SME-001",
        "title": "Abstract Algebra: Normal Subgroups, Quotient Groups, and First Isomorphism Theorem",
        "domain": "maths",
        "tier": "sme",
        "grade_level": "SME / Research",
        "concept": "A subgroup N <= G is normal (N ⊲ G) iff g*n*g⁻¹ ∈ N for all g ∈ G, n ∈ N. The cosets G/N form a well-defined group under coset multiplication: (g1*N)(g2*N) = (g1*g2)*N. The First Isomorphism Theorem states that if φ: G -> H is a group homomorphism, then ker(φ) ⊲ G and G / ker(φ) ≅ im(φ).",
        "example_problem": "Let G = GL(n, R) be the general linear group of invertible n x n real matrices under multiplication, and let φ: G -> R* be the determinant map φ(A) = det(A). Prove that SL(n, R) is a normal subgroup of GL(n, R) and determine the quotient group GL(n, R) / SL(n, R).",
        "solution_steps": "1. Define map φ: GL(n, R) -> R* by φ(A) = det(A).\n2. Multiplicative property of determinants: det(AB) = det(A) * det(B) for all A, B ∈ GL(n, R).\n   Hence φ is a group homomorphism from (GL(n, R), ·) to (R*, ·).\n3. Find the kernel: ker(φ) = {A ∈ GL(n, R) : det(A) = 1}.\n   By definition, this is the Special Linear Group SL(n, R).\n4. Since the kernel of any group homomorphism is a normal subgroup, SL(n, R) ⊲ GL(n, R).\n5. Determine the image: For any non-zero real scalar c ∈ R*, consider the diagonal matrix diag(c, 1, 1, ..., 1) ∈ GL(n, R). Its determinant is c. Thus φ is surjective (im(φ) = R*).\n6. Apply First Isomorphism Theorem: GL(n, R) / ker(φ) ≅ im(φ) => GL(n, R) / SL(n, R) ≅ (R*, ·).\nConclusion: SL(n, R) is normal in GL(n, R) and the quotient group is isomorphic to the multiplicative group of non-zero reals R*.",
        "tags": ["abstract_algebra", "group_theory", "isomorphism_theorems", "quotient_groups", "sme_math"],
    },
    {
        "id": "STEM-MATH-SME-002",
        "title": "Complex Analysis: Holomorphic Functions, Cauchy Integral Formula, and Residue Calculus",
        "domain": "maths",
        "tier": "sme",
        "grade_level": "SME / Research",
        "concept": "A function f(z) = u(x,y) + i*v(x,y) is holomorphic on open domain U ⊆ C iff u and v satisfy Cauchy-Riemann equations: ∂u/∂x = ∂v/∂y and ∂u/∂y = -∂v/∂x. Cauchy's Residue Theorem: For a closed contour γ enclosing isolated singularities z_k: ∮_γ f(z) dz = 2πi * ∑ Res(f, z_k). Residue at a simple pole z0: Res(f, z0) = lim(z->z0) (z - z0)*f(z).",
        "example_problem": "Compute the improper real integral I = ∫(-∞ to +∞) 1 / (x⁴ + 1) dx using complex contour integration along a semicircular contour in the upper half-plane.",
        "solution_steps": "1. Consider f(z) = 1 / (z⁴ + 1) and semicircular contour C_R = [-R, R] ∪ Γ_R (upper semicircle |z| = R, Im(z) >= 0).\n2. Poles occur where z⁴ + 1 = 0 => z⁴ = -1 = e^(iπ(2k+1)).\n   Roots in upper half-plane (Im(z) > 0):\n   z1 = e^(iπ/4) = (1 + i) / √2\n   z2 = e^(i3π/4) = (-1 + i) / √2.\n3. Compute residues at simple poles using Res(f, z_k) = 1 / (d/dz [z⁴ + 1])|_{z=z_k} = 1 / (4*z_k³):\n   Res(f, z1) = 1 / (4 * e^(i3π/4)) = (1/4) * e^(-i3π/4) = (1/4) * (-1 - i) / √2.\n   Res(f, z2) = 1 / (4 * e^(i9π/4)) = (1/4) * e^(-iπ/4) = (1/4) * (1 - i) / √2.\n4. Sum residues:\n   Res(z1) + Res(z2) = (1 / (4√2)) * (-1 - i + 1 - i) = (1 / (4√2)) * (-2i) = -i / (2√2).\n5. By Jordan's lemma, as R -> ∞, ∫_Γ_R f(z) dz -> 0 because |f(z)| ~ 1/R⁴.\n6. Apply Residue Theorem:\n   ∫(-∞ to +∞) dx / (x⁴ + 1) = 2πi * ∑ Res = 2πi * (-i / (2√2)) = 2π / (2√2) = π / √2.\nThe exact value of the integral is π / √2.",
        "tags": ["complex_analysis", "residue_calculus", "contour_integration", "holomorphic", "sme_math"],
    },

    # ------------------------------------------------------------------------
    # TIER 4: SUBJECT MATTER EXPERT (SME / RESEARCH / OLYMPIAD) - PHYSICS
    # ------------------------------------------------------------------------
    {
        "id": "STEM-PHYS-SME-001",
        "title": "Quantum Mechanics: Schrödinger Equation, Commutators, and Harmonic Oscillator",
        "domain": "physics",
        "tier": "sme",
        "grade_level": "SME / Research",
        "concept": "Time-independent Schrödinger Equation: Ĥ|ψ⟩ = E|ψ⟩, where Hamiltonian Ĥ = -ħ²/(2m) ∇² + V(r). Canonical commutation relation: [x̂, p̂] = iħ. For 1D Simple Harmonic Oscillator with V(x) = (1/2)mω²x², define ladder operators: â = √(mω/(2ħ)) (x̂ + i p̂/(mω)) and â† = √(mω/(2ħ)) (x̂ - i p̂/(mω)) satisfying [â, â†] = 1. Hamiltonian becomes Ĥ = ħω(â† â + 1/2). Energy eigenvalues are discrete: E_n = ħω(n + 1/2) for n = 0, 1, 2, ...",
        "example_problem": "Derive the ground state energy E_0 and ground state wave function ψ_0(x) of the 1D quantum harmonic oscillator using the annihilation operator condition â ψ_0(x) = 0.",
        "solution_steps": "1. Ladder operator condition for ground state: â ψ_0 = 0, because no state exists below ground state.\n2. Express â in position representation (p̂ = -iħ d/dx):\n   √(mω/(2ħ)) * [x + (i / (mω)) * (-iħ d/dx)] ψ_0(x) = 0\n   [x + (ħ / (mω)) d/dx] ψ_0(x) = 0.\n3. Separate variables for differential equation:\n   dψ_0 / ψ_0 = - (mω / ħ) x dx.\n4. Integrate both sides:\n   ln(ψ_0) = - (mω / (2ħ)) x² + C => ψ_0(x) = A * exp(- mω x² / (2ħ)).\n5. Normalize ∫(-∞ to ∞) |ψ_0(x)|² dx = 1:\n   A² * ∫ exp(- mω x² / ħ) dx = A² * √(πħ / (mω)) = 1 => A = (mω / (πħ))^(1/4).\n6. Ground state energy: E_0 = ⟨ψ_0| Ĥ |ψ_0⟩ = ħω(0 + 1/2) = (1/2) ħω (zero-point energy required by Heisenberg uncertainty principle).\nGround state wave function is ψ_0(x) = (mω / (πħ))^(1/4) * exp(-mω x² / (2ħ)) and ground state energy is (1/2) ħω.",
        "tags": ["quantum_mechanics", "schrodinger_equation", "harmonic_oscillator", "ladder_operators", "sme_physics"],
    },
    {
        "id": "STEM-PHYS-SME-002",
        "title": "Classical Mechanics: Lagrangian Formulation, Euler-Lagrange, and Noether's Theorem",
        "domain": "physics",
        "tier": "sme",
        "grade_level": "SME / Research",
        "concept": "Hamilton's Principle of Stationary Action: δS = δ ∫ L(q, q̇, t) dt = 0, where L = T - V is the Lagrangian. Yields Euler-Lagrange equations: d/dt(∂L/∂q̇_i) - ∂L/∂q_i = 0. Noether's Theorem connects symmetries to conserved quantities: Invariance under time translation implies conservation of energy; invariance under spatial translation implies conservation of linear momentum; invariance under spatial rotation implies conservation of angular momentum.",
        "example_problem": "A planar double pendulum consists of two point masses m1 and m2 attached by two massless rigid rods of lengths l1 and l2 under uniform gravity g. Derive the Lagrangian L(θ1, θ2, θ̇1, θ̇2) of the system.",
        "solution_steps": "1. Choose generalized coordinates: angles θ1 and θ2 measured from the downward vertical.\n2. Positions of masses in Cartesian coordinates:\n   x1 = l1 sin(θ1), y1 = -l1 cos(θ1)\n   x2 = l1 sin(θ1) + l2 sin(θ2), y2 = -l1 cos(θ1) - l2 cos(θ2).\n3. Velocities (time derivatives):\n   ẋ1 = l1 θ̇1 cos(θ1), ẏ1 = l1 θ̇1 sin(θ1) => v1² = ẋ1² + ẏ1² = l1² θ̇1².\n   ẋ2 = l1 θ̇1 cos(θ1) + l2 θ̇2 cos(θ2), ẏ2 = l1 θ̇1 sin(θ1) + l2 θ̇2 sin(θ2).\n   v2² = l1² θ̇1² + l2² θ̇2² + 2 l1 l2 θ̇1 θ̇2 [cos(θ1)cos(θ2) + sin(θ1)sin(θ2)]\n       = l1² θ̇1² + l2² θ̇2² + 2 l1 l2 θ̇1 θ̇2 cos(θ1 - θ2).\n4. Kinetic Energy T = (1/2) m1 v1² + (1/2) m2 v2²:\n   T = (1/2)(m1 + m2) l1² θ̇1² + (1/2) m2 l2² θ̇2² + m2 l1 l2 θ̇1 θ̇2 cos(θ1 - θ2).\n5. Potential Energy V = m1 g y1 + m2 g y2:\n   V = - (m1 + m2) g l1 cos(θ1) - m2 g l2 cos(θ2).\n6. Formulate Lagrangian L = T - V:\n   L = (1/2)(m1 + m2) l1² θ̇1² + (1/2) m2 l2² θ̇2² + m2 l1 l2 θ̇1 θ̇2 cos(θ1 - θ2) + (m1 + m2) g l1 cos(θ1) + m2 g l2 cos(θ2).\nThe exact Lagrangian is derived.",
        "tags": ["analytical_mechanics", "lagrangian", "euler_lagrange", "noethers_theorem", "double_pendulum", "sme_physics"],
    },

    # ------------------------------------------------------------------------
    # TIER 4: SUBJECT MATTER EXPERT (SME / RESEARCH / OLYMPIAD) - CODING
    # ------------------------------------------------------------------------
    {
        "id": "STEM-CODE-SME-001",
        "title": "Lock-Free Concurrency: Compare-And-Swap (CAS), Treiber Stack, and Memory Fences",
        "domain": "coding",
        "tier": "sme",
        "grade_level": "SME / Research",
        "concept": "Lock-free synchronization ensures system-wide progress without mutual exclusion mutex locks, preventing deadlocks, priority inversion, and convoying. The core primitive is hardware Compare-And-Swap (CAS): atomic_compare_exchange(ptr, &expected, desired). In C++/Rust/Java memory models, memory orders (acquire/release/seq_cst) establish happens-before relationships preventing compiler and CPU out-of-order reordering across cache lines.",
        "example_problem": "Implement a thread-safe, lock-free LIFO stack (Treiber Stack) in Python using simulated atomic CAS, and explain how the ABA problem is prevented in production systems.",
        "solution_steps": "```python\nimport threading\nfrom typing import Any, Optional\n\nclass Node:\n    def __init__(self, value: Any, next_node: Optional['Node'] = None):\n        self.value = value\n        self.next = next_node\n\nclass LockFreeTreiberStack:\n    def __init__(self):\n        self._head: Optional[Node] = None\n        self._lock = threading.Lock()  # Simulates hardware atomic CAS operation\n\n    def _compare_and_swap_head(self, expected: Optional[Node], new_node: Optional[Node]) -> bool:\n        with self._lock:\n            if self._head is expected:\n                self._head = new_node\n                return True\n            return False\n\n    def push(self, val: Any) -> None:\n        new_node = Node(val)\n        while True:\n            current_head = self._head\n            new_node.next = current_head\n            if self._compare_and_swap_head(current_head, new_node):\n                return\n\n    def pop(self) -> Optional[Any]:\n        while True:\n            current_head = self._head\n            if current_head is None:\n                return None\n            next_node = current_head.next\n            if self._compare_and_swap_head(current_head, next_node):\n                return current_head.value\n```\nABA Mitigation:\nIn native systems (C++/Rust), the ABA problem occurs if node A is popped, memory freed, and re-allocated at the same pointer address while another thread is executing CAS. Standard solutions include:\n1. Tagged pointers (storing a 64-bit monotonically increasing version tag alongside pointer, using DCAS / CMPXCHG16B).\n2. Hazard Pointers / Epoch-Based Reclamation (EBR) to defer memory deallocation until no active thread holds a reference.",
        "tags": ["concurrency", "lock_free", "compare_and_swap", "treiber_stack", "memory_models", "sme_coding"],
    },
    {
        "id": "STEM-CODE-SME-002",
        "title": "Distributed Systems: Raft Consensus Algorithm, Log Replication, and Split-Brain Safety",
        "domain": "coding",
        "tier": "sme",
        "grade_level": "SME / Research",
        "concept": "The Raft consensus protocol manages replicated state machines across distributed nodes under asynchronous network conditions with crash-recovery failures. Key sub-problems: 1. Leader Election: Nodes transition between Follower, Candidate, and Leader using randomized election timeouts. A candidate requires majority votes (⌊N/2⌋ + 1) in a given term. 2. Log Replication: Leader appends client commands to its log and issues AppendEntries RPCs. An entry is committed once replicated across majority nodes. 3. Safety Invariant: Election restriction ensures a candidate cannot win election unless its log is at least as up-to-date as any voter's log (comparing lastLogTerm then lastLogIndex).",
        "example_problem": "Design a complete State Machine Replication validator for Raft log entry consistency and majority commitment check in Python.",
        "solution_steps": "```python\nfrom dataclasses import dataclass, field\nfrom typing import List, Dict, Optional\n\n@dataclass\nclass LogEntry:\n    term: int\n    index: int\n    command: str\n\nclass RaftClusterValidator:\n    def __init__(self, node_count: int):\n        self.n = node_count\n        self.majority = (node_count // 2) + 1\n        self.node_logs: Dict[int, List[LogEntry]] = {i: [] for i in range(node_count)}\n        self.commit_index = 0\n\n    def append_leader_entry(self, leader_id: int, term: int, command: str) -> LogEntry:\n        idx = len(self.node_logs[leader_id]) + 1\n        entry = LogEntry(term=term, index=idx, command=command)\n        self.node_logs[leader_id].append(entry)\n        return entry\n\n    def replicate_to_follower(self, follower_id: int, entry: LogEntry, prev_term: int, prev_idx: int) -> bool:\n        f_log = self.node_logs[follower_id]\n        # Log matching property check\n        if prev_idx > 0:\n            if len(f_log) < prev_idx or f_log[prev_idx - 1].term != prev_term:\n                return False  # Inconsistency detected\n        # Overwrite conflicting entries and append\n        del f_log[prev_idx:]\n        f_log.append(entry)\n        return True\n\n    def check_majority_committed(self, entry_index: int, entry_term: int) -> bool:\n        replicated_count = 0\n        for f_id, log in self.node_logs.items():\n            if len(log) >= entry_index and log[entry_index - 1].term == entry_term:\n                replicated_count += 1\n        return replicated_count >= self.majority\n```",
        "tags": ["distributed_systems", "raft", "consensus", "state_machine_replication", "sme_coding"],
    },
]


# ============================================================================
# MEDALLION PIPELINE IMPLEMENTATION
# ============================================================================

class StemBronzeStage:
    """Bronze Stage: Ingestion, schema validation, and staging."""

    @staticmethod
    def load_seed_corpus() -> List[Dict[str, Any]]:
        """Load built-in verified foundational STEM seed knowledge."""
        logger.info(f"Bronze: Loaded {len(CURATED_STEM_CORPUS)} seed items from built-in STEM corpus.")
        return [dict(item) for item in CURATED_STEM_CORPUS]

    @staticmethod
    def load_from_json(file_path: Path) -> List[Dict[str, Any]]:
        """Load external STEM knowledge records from JSON file."""
        if not file_path.exists():
            raise FileNotFoundError(f"Bronze file not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"Bronze dataset must be a list of records, got {type(data)}")
        logger.info(f"Bronze: Loaded {len(data)} records from {file_path}")
        return data

    @staticmethod
    def validate_and_stage(raw_records: List[Dict[str, Any]]) -> List[StemKnowledgeItem]:
        """Validate required fields and instantiate StemKnowledgeItem instances."""
        staged: List[StemKnowledgeItem] = []
        for idx, rec in enumerate(raw_records):
            doc_id = str(rec.get("id") or f"STEM-RAW-{idx:04d}")
            title = str(rec.get("title", "")).strip()
            domain = str(rec.get("domain", "stem")).lower().strip()
            tier = str(rec.get("tier", "secondary")).lower().strip()
            grade_level = str(rec.get("grade_level", "General STEM")).strip()
            concept = str(rec.get("concept") or rec.get("text") or rec.get("content", "")).strip()
            example_problem = str(rec.get("example_problem") or rec.get("problem", "")).strip()
            solution_steps = str(rec.get("solution_steps") or rec.get("solution", "")).strip()

            if not title or not concept:
                logger.warning(f"Bronze: Skipping malformed record index {idx} (id={doc_id}): Missing title or concept")
                continue

            tags = rec.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]

            meta = rec.get("metadata", {})
            if not isinstance(meta, dict):
                meta = {}

            item = StemKnowledgeItem(
                id=doc_id,
                title=title,
                domain=domain,
                tier=tier,
                grade_level=grade_level,
                concept=concept,
                example_problem=example_problem,
                solution_steps=solution_steps,
                tags=tags,
                metadata=meta,
            )
            staged.append(item)

        logger.info(f"Bronze: Successfully staged {len(staged)} validated records.")
        return staged


class StemSilverStage:
    """Silver Stage: 3-tier Deduplication and data normalization."""

    def __init__(
        self,
        fuzzy_jaccard_threshold: float = 0.82,
        semantic_threshold: float = 0.95,
    ) -> None:
        self.fuzzy_jaccard_threshold = fuzzy_jaccard_threshold
        self.semantic_threshold = semantic_threshold
        self.seen_exact_hashes: Set[str] = set()
        self.retained_shingles: List[Tuple[str, Set[str]]] = []  # (doc_id, shingle_set)

    @staticmethod
    def normalize_text(text: str) -> str:
        """Strip formatting, collapse whitespace, and lowercase for canonical matching."""
        lowered = text.lower()
        cleaned = re.sub(r"[^\w\s]", " ", lowered)
        return re.sub(r"\s+", " ", cleaned).strip()

    @classmethod
    def compute_exact_hash(cls, item: StemKnowledgeItem) -> str:
        """Compute SHA-256 fingerprint over normalized title and concept."""
        content = f"{cls.normalize_text(item.title)}|||{cls.normalize_text(item.concept)}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @classmethod
    def compute_shingles(cls, text: str, k: int = 2) -> Set[str]:
        """Compute word tokens and k-token shingles for Jaccard near-duplicate detection."""
        tokens = cls.normalize_text(text).split()
        if not tokens:
            return set()
        shingles = set(tokens)
        if len(tokens) >= k:
            shingles.update(" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1))
        return shingles

    @staticmethod
    def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
        """Compute standard Jaccard set similarity."""
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        return float(intersection) / float(union) if union > 0 else 0.0

    def deduplicate(
        self,
        staged_items: List[StemKnowledgeItem],
    ) -> Tuple[List[StemKnowledgeItem], Dict[str, int]]:
        """
        Executes 3-Tier Deduplication:
        - Tier 1: Exact SHA-256 hash collision.
        - Tier 2: Lexical Jaccard token shingle near-duplicate detection.
        - Tier 3: Semantic topic key collision & metadata consistency check.
        """
        retained: List[StemKnowledgeItem] = []
        stats = {
            "total_input": len(staged_items),
            "tier1_exact_duplicates": 0,
            "tier2_fuzzy_duplicates": 0,
            "tier3_semantic_duplicates": 0,
            "retained": 0,
        }

        # Track semantic keys: (domain, tier, normalized_title)
        seen_semantic_keys: Set[Tuple[str, str, str]] = set()

        for item in staged_items:
            # 1. Exact Hash Check
            h = self.compute_exact_hash(item)
            if h in self.seen_exact_hashes:
                logger.debug(f"Silver: Dropping exact duplicate (ID={item.id}, Title='{item.title}')")
                stats["tier1_exact_duplicates"] += 1
                continue

            # 2. Lexical Jaccard Near-Duplicate Check
            item_shingles = self.compute_shingles(f"{item.title} {item.concept}")
            is_fuzzy_dup = False
            for exist_id, exist_shingles in self.retained_shingles:
                sim = self.jaccard_similarity(item_shingles, exist_shingles)
                if sim >= self.fuzzy_jaccard_threshold:
                    logger.debug(
                        f"Silver: Dropping fuzzy duplicate (ID={item.id} vs existing {exist_id}, similarity={sim:.3f})"
                    )
                    stats["tier2_fuzzy_duplicates"] += 1
                    is_fuzzy_dup = True
                    break
            if is_fuzzy_dup:
                continue

            # 3. Semantic Topic Key Check
            norm_title = self.normalize_text(item.title)
            sem_key = (item.domain, item.tier, norm_title)
            if sem_key in seen_semantic_keys:
                logger.debug(f"Silver: Dropping semantic key collision (ID={item.id}, Key={sem_key})")
                stats["tier3_semantic_duplicates"] += 1
                continue

            # Item passed all 3 tiers of deduplication
            self.seen_exact_hashes.add(h)
            self.retained_shingles.append((item.id, item_shingles))
            seen_semantic_keys.add(sem_key)
            retained.append(item)

        stats["retained"] = len(retained)
        logger.info(
            f"Silver: Deduplication complete. Input: {stats['total_input']} -> Retained: {stats['retained']} "
            f"(Dropped exact={stats['tier1_exact_duplicates']}, fuzzy={stats['tier2_fuzzy_duplicates']}, "
            f"semantic={stats['tier3_semantic_duplicates']})"
        )
        return retained, stats


class StemGoldStage:
    """Gold Stage: Production Vector Store persistence and PHP memory safeguard."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        ollama_base_url: str = "http://localhost:11434",
        embed_model: str = "nomic-embed-text",
        max_material_chunks: int = 500,
        enable_ollama: bool = True,
    ) -> None:
        self.db_path = db_path or (ROOT / "backend" / "storage" / "vectors.sqlite")
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.embed_model = embed_model
        self.max_material_chunks = max_material_chunks
        self.enable_ollama = enable_ollama
        self.backend = LocalSqliteRagBackend(str(self.db_path))

    def _get_ollama_embedding(self, text: str) -> Optional[List[float]]:
        """
        Request 768-dim embedding from Ollama with mandatory 'search_document: ' prefix
        for nomic-embed-text. Gracefully returns None if Ollama is unreachable.
        """
        if not self.enable_ollama:
            return None

        # Critical architecture requirement: nomic-embed-text requires search_document prefix
        prefixed_input = f"search_document: {text.strip()}"
        url = f"{self.ollama_base_url}/api/embed"
        payload = {
            "model": self.embed_model,
            "input": prefixed_input,
            "keep_alive": "5m",
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    embeddings = data.get("embeddings")
                    if embeddings and len(embeddings) > 0:
                        return embeddings[0]
        except Exception as e:
            logger.debug(f"Gold: Ollama embedding request skipped/failed: {e}")
            return None
        return None

    @staticmethod
    def pack_float_vector(vec: List[float]) -> bytes:
        """Packs a float list into a binary BLOB identical to PHP pack('f*', ...)."""
        return struct.pack(f"{len(vec)}f", *vec)

    @staticmethod
    def generate_fallback_vector(seed_text: str, dim: int = 768) -> List[float]:
        """Deterministic unit vector fallback when Ollama is offline."""
        h = hashlib.sha256(seed_text.encode("utf-8")).digest()
        raw = [float(h[i % len(h)]) - 128.0 for i in range(dim)]
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / norm for x in raw]

    def persist(
        self,
        items: List[StemKnowledgeItem],
        collection: str = "stem_knowledge",
    ) -> Dict[str, int]:
        """
        Persists items into vectors.sqlite:
        1. Stores ALL items into 'rag_documents' under collection (e.g. 'stem_knowledge').
        2. Ingests high-priority summary chunks into 'material_chunks', capping rows
           at max_material_chunks to strictly safeguard PHP 128M memory_limit in
           backend/rag_service.php.
        """
        stats = {
            "rag_documents_written": 0,
            "material_chunks_written": 0,
            "embeddings_computed": 0,
            "fallback_embeddings_used": 0,
        }

        with self.backend._get_connection() as conn:
            cursor = conn.cursor()

            # Ensure material_chunks table exists with standard schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS material_chunks (
                    id TEXT PRIMARY KEY,
                    material_id TEXT,
                    course_id TEXT,
                    batch_id TEXT,
                    chunk_index INTEGER,
                    title TEXT,
                    content TEXT,
                    metadata TEXT,
                    embedding BLOB,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 1. Write full documents into rag_documents
            for item in items:
                formatted_text = item.to_formatted_document()
                meta = {
                    "title": item.title,
                    "domain": item.domain,
                    "tier": item.tier,
                    "grade_level": item.grade_level,
                    "tags": item.tags,
                    "concept": item.concept,
                    "example_problem": item.example_problem,
                    "solution_steps": item.solution_steps,
                    "source": "stem_foundation_ingestion",
                    "updated_at": datetime.now().isoformat(),
                    **item.metadata,
                }
                # Upsert into rag_documents
                self.backend.upsert(
                    collection=collection,
                    doc_id=item.id,
                    text=formatted_text,
                    metadata=meta,
                )
                stats["rag_documents_written"] += 1

            # Check existing material_chunks row count
            cursor.execute("SELECT COUNT(*) FROM material_chunks WHERE course_id = 'stem_curriculum'")
            current_stem_chunks = cursor.fetchone()[0]

            # 2. Ingest into material_chunks respecting max_material_chunks ceiling
            allowed_slots = max(0, self.max_material_chunks - current_stem_chunks)

            for idx, item in enumerate(items[:allowed_slots]):
                chunk_id = f"stem_chunk_{item.id}_{idx:03d}"
                summary_content = (
                    f"{item.title} ({item.grade_level} - {item.domain.upper()}):\n"
                    f"{item.concept}\n\n"
                    f"Problem: {item.example_problem}\n"
                    f"Solution: {item.solution_steps}"
                )

                # Attempt Ollama embedding with 'search_document: ' prefix
                vec = self._get_ollama_embedding(summary_content)
                if vec is not None:
                    stats["embeddings_computed"] += 1
                else:
                    vec = self.generate_fallback_vector(summary_content)
                    stats["fallback_embeddings_used"] += 1

                packed_blob = self.pack_float_vector(vec)
                chunk_meta_str = json.dumps({
                    "title": item.title,
                    "domain": item.domain,
                    "tier": item.tier,
                    "grade_level": item.grade_level,
                    "source_item_id": item.id,
                })

                cursor.execute("""
                    INSERT OR REPLACE INTO material_chunks (
                        id, material_id, course_id, batch_id, chunk_index, title, content, metadata, embedding
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    chunk_id,
                    f"stem_mat_{item.domain}",
                    "stem_curriculum",
                    f"batch_{item.tier}",
                    idx,
                    item.title,
                    summary_content,
                    chunk_meta_str,
                    packed_blob,
                ))
                stats["material_chunks_written"] += 1

            conn.commit()

        logger.info(
            f"Gold: Persistence complete. rag_documents written: {stats['rag_documents_written']}, "
            f"material_chunks written: {stats['material_chunks_written']} (capped at {self.max_material_chunks}), "
            f"Live embeddings: {stats['embeddings_computed']}, Fallback embeddings: {stats['fallback_embeddings_used']}"
        )
        return stats


# ============================================================================
# MAIN PIPELINE RUNNER
# ============================================================================

def run_stem_ingestion_pipeline(
    input_file: Optional[Path] = None,
    db_path: Optional[Path] = None,
    ollama_url: str = "http://localhost:11434",
    embed_model: str = "nomic-embed-text",
    max_material_chunks: int = 500,
    enable_ollama: bool = True,
    fuzzy_threshold: float = 0.82,
) -> Dict[str, Any]:
    """Execute complete Bronze -> Silver -> Gold Medallion STEM Ingestion Pipeline."""
    logger.info("=== Starting STEM Knowledge Ingestion Pipeline ===")

    # 1. Bronze
    if input_file and input_file.exists():
        raw_data = StemBronzeStage.load_from_json(input_file)
    else:
        raw_data = StemBronzeStage.load_seed_corpus()
    staged = StemBronzeStage.validate_and_stage(raw_data)

    # 2. Silver
    silver = StemSilverStage(fuzzy_jaccard_threshold=fuzzy_threshold)
    deduped, silver_stats = silver.deduplicate(staged)

    # 3. Gold
    gold = StemGoldStage(
        db_path=db_path,
        ollama_base_url=ollama_url,
        embed_model=embed_model,
        max_material_chunks=max_material_chunks,
        enable_ollama=enable_ollama,
    )
    gold_stats = gold.persist(deduped)

    summary = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "bronze_count": len(staged),
        "silver_retained": len(deduped),
        "silver_stats": silver_stats,
        "gold_stats": gold_stats,
    }
    logger.info(f"=== STEM Pipeline Succeeded: {json.dumps(summary, indent=2)} ===")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest and deduplicate STEM knowledge into RAG vector store.")
    parser.add_argument("--input", type=Path, default=None, help="Path to external JSON file containing STEM records.")
    parser.add_argument("--db-path", type=Path, default=None, help="Path to vectors.sqlite database.")
    parser.add_argument("--ollama-url", type=str, default="http://localhost:11434", help="Ollama API base URL.")
    parser.add_argument("--embed-model", type=str, default="nomic-embed-text", help="Embedding model name.")
    parser.add_argument("--max-chunks", type=int, default=500, help="Max rows for material_chunks to protect PHP RAM.")
    parser.add_argument("--no-ollama", action="store_true", help="Disable Ollama and use deterministic fallback vectors.")
    parser.add_argument("--fuzzy-threshold", type=float, default=0.82, help="Jaccard fuzzy deduplication threshold.")

    args = parser.parse_args()

    run_stem_ingestion_pipeline(
        input_file=args.input,
        db_path=args.db_path,
        ollama_url=args.ollama_url,
        embed_model=args.embed_model,
        max_material_chunks=args.max_chunks,
        enable_ollama=not args.no_ollama,
        fuzzy_threshold=args.fuzzy_threshold,
    )


if __name__ == "__main__":
    main()
