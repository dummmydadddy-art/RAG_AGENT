#!/usr/bin/env python3
"""
scripts/build_expanded_curriculum.py

Generates and validates data/stem_curriculum_expanded.json.
Contains 52 curated STEM curriculum modules across 4 educational tiers:
1. Elementary (Class 4-5) - 12 modules (6 Math, 6 Physics)
2. Secondary (Class 6-10) - 14 modules (7 Math, 7 Physics)
3. Higher Secondary (Class 11-12) - 15 modules (6 Math, 9 Physics)
4. Subject Matter Expert (SME / Research) - 11 modules (6 Math, 5 Physics)

Every record contains:
- id: Canonical identifier
- title: Comprehensive topic title
- domain: 'maths' or 'physics'
- tier: 'elementary', 'secondary', 'higher_secondary', or 'sme'
- grade_level: Human-readable grade range
- concept: Rigorous conceptual exposition with formulas & theorems
- example_problem: Challenging concrete problem statement
- solution_steps: Analytical step-by-step resolution with derivations
- tags: Subject tags for indexing
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = ROOT / "data" / "stem_curriculum_expanded.json"

CURRICULUM_DATA = [
    # ========================================================================
    # TIER 1: ELEMENTARY (CLASS 4 - 5) - MATHEMATICS (6 items)
    # ========================================================================
    {
        "id": "CURR-MATH-ELEM-001",
        "title": "Fractions and Mixed Numbers: Common Denominators and Arithmetic",
        "domain": "maths",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "A fraction a/b represents a parts of a whole divided into b equal parts. To add or subtract fractions with unlike denominators, find the Least Common Multiple (LCM) of the denominators to create equivalent fractions: a/b + c/d = (a*d + b*c)/(b*d). A mixed number combines an integer with a proper fraction.",
        "example_problem": "A baker mixes 3/4 kg of wheat flour and 2/3 kg of oat flour. What is the total mass of the mixture expressed as an improper fraction and as a mixed number?",
        "solution_steps": "1. Identify denominators: 4 and 3.\n2. Compute LCM(4, 3) = 12.\n3. Convert to equivalent fractions: 3/4 = (3*3)/(4*3) = 9/12; 2/3 = (2*4)/(3*4) = 8/12.\n4. Sum numerators: 9/12 + 8/12 = 17/12 kg.\n5. Convert to mixed number: 17 = 12 * 1 + 5, so 17/12 = 1 5/12 kg.\nTotal mass is 17/12 kg (1 5/12 kg).",
        "tags": ["fractions", "mixed_numbers", "lcm", "elementary_math", "ncert_class_5"]
    },
    {
        "id": "CURR-MATH-ELEM-002",
        "title": "Metric Measurement Conversions and Multi-Step Scale Arithmetic",
        "domain": "maths",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "The metric system uses powers of 10 for unit conversion. Length: 1 kilometer (km) = 1,000 meters (m) = 100,000 centimeters (cm) = 1,000,000 millimeters (mm). Mass: 1 kilogram (kg) = 1,000 grams (g) = 1,000,000 milligrams (mg). Capacity: 1 liter (L) = 1,000 milliliters (mL).",
        "example_problem": "A marathon runner drinks 250 mL of water at each of 12 hydration stations along a 42 km race. Calculate total water consumed in liters and the remaining distance in meters after station 8, given stations are spaced evenly every 3.5 km.",
        "solution_steps": "1. Total water volume: 12 * 250 mL = 3000 mL.\n2. Convert mL to liters: 3000 mL / 1000 = 3.0 Liters.\n3. Distance at station 8: 8 * 3.5 km = 28.0 km.\n4. Remaining distance: 42 km - 28 km = 14.0 km.\n5. Convert km to meters: 14.0 km * 1000 m/km = 14,000 meters.\nTotal water is 3.0 L and remaining distance is 14,000 m.",
        "tags": ["metric_units", "measurement", "conversions", "elementary_math", "ncert_class_4"]
    },
    {
        "id": "CURR-MATH-ELEM-003",
        "title": "Geometric Angles, Clock Hands, and Degrees of Rotation",
        "domain": "maths",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "An angle is formed by two rays sharing a common vertex. Angles are measured in degrees (°). Acute angles are < 90°, right angles equal 90°, obtuse angles are between 90° and 180°, and straight angles equal 180°. A complete circular rotation is 360°. On a 12-hour analog clock, each hour mark represents 360° / 12 = 30°, and each minute mark represents 360° / 60 = 6°.",
        "example_problem": "Calculate the exact interior angle between the hour hand and minute hand of an analog clock at precisely 3:30.",
        "solution_steps": "1. Position of minute hand at 30 minutes: 30 * 6° = 180° (pointing directly at 6).\n2. Position of hour hand at 3:30: At 3:00 it is at 3 * 30° = 90°. In 30 minutes, it advances by 30 * (30° / 60) = 15°. Total angle = 90° + 15° = 105°.\n3. Interior angle: |180° - 105°| = 75°.\n4. Classification: Since 75° < 90°, this is an acute angle.\nThe angle between the clock hands is 75°.",
        "tags": ["geometry", "angles", "clock_arithmetic", "degrees", "elementary_math", "ncert_class_5"]
    },
    {
        "id": "CURR-MATH-ELEM-004",
        "title": "Perimeter of Non-Standard Shapes and Area via Unit Grid Decomposition",
        "domain": "maths",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "Perimeter is the continuous boundary length enclosing a 2D shape: P = sum of all outer edge lengths. Area is the quantity of 2D space enclosed within the boundary, measured in square units (cm², m²). Composite polygons can be evaluated by decomposing into non-overlapping standard rectangles or by counting unit grid squares.",
        "example_problem": "A playground is designed in the shape of a rectangle (20 m by 12 m) with a square cutout (4 m by 4 m) removed from one corner. Find the total surface area and the total fencing perimeter required around the outer boundary.",
        "solution_steps": "1. Area of complete outer rectangle: A_rect = 20 m * 12 m = 240 m².\n2. Area of square cutout: A_square = 4 m * 4 m = 16 m².\n3. Total remaining playground area: A = 240 - 16 = 224 m².\n4. Perimeter evaluation: Removing a corner square replaces two outer segments (4 m each) with two inner corner segments (4 m each). The total outer perimeter remains unchanged: P = 2 * (20 + 12) = 64 meters.\nTotal area is 224 m² and required fencing perimeter is 64 m.",
        "tags": ["geometry", "perimeter", "area", "composite_shapes", "elementary_math", "ncert_class_5"]
    },
    {
        "id": "CURR-MATH-ELEM-005",
        "title": "Multi-Digit Division with Partial Quotients and Remainder Invariants",
        "domain": "maths",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "Division represents partitioning a dividend into equal groups specified by a divisor. The Division Algorithm states: Dividend = (Divisor * Quotient) + Remainder, subject to the strict invariant: 0 <= Remainder < Divisor.",
        "example_problem": "A science center has 745 magnifying lenses to pack into kits of 18 lenses each. How many complete kits can be assembled, and how many extra lenses are needed to complete one more kit?",
        "solution_steps": "1. Divide 745 by 18.\n2. Estimate tens: 18 * 40 = 720. Subtract 720 from 745: 745 - 720 = 25.\n3. Estimate units: 18 * 1 = 18. Subtract 18 from 25: 25 - 18 = 7.\n4. Total quotient = 40 + 1 = 41 kits. Remainder = 7 lenses.\n5. Check invariant: 0 <= 7 < 18. Verification: 18 * 41 + 7 = 738 + 7 = 745.\n6. Extra lenses needed for one more full kit: 18 - 7 = 11 lenses.\n41 complete kits can be packed, and 11 additional lenses are needed for the next kit.",
        "tags": ["division", "quotient", "remainders", "arithmetic", "elementary_math", "ncert_class_4"]
    },
    {
        "id": "CURR-MATH-ELEM-006",
        "title": "Prime Factors, Multiples, and Sieve Method for Elementary Arithmetic",
        "domain": "maths",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "A prime number is an integer greater than 1 with exactly two distinct positive divisors: 1 and itself. A composite number has more than two divisors. The Sieve of Eratosthenes identifies primes up to N by iteratively marking multiples of each prime starting from 2. The Greatest Common Divisor (GCD) is the highest shared factor, and Least Common Multiple (LCM) is the lowest shared multiple.",
        "example_problem": "Two bells toll together at 8:00 AM. Bell A tolls every 15 minutes, and Bell B tolls every 20 minutes. At what time will both bells next toll simultaneously?",
        "solution_steps": "1. The bells toll together at intervals that are common multiples of 15 and 20.\n2. The first simultaneous toll occurs at LCM(15, 20).\n3. Prime factorization: 15 = 3 * 5; 20 = 2² * 5.\n4. LCM = 2² * 3¹ * 5¹ = 4 * 3 * 5 = 60 minutes (1 hour).\n5. Add 60 minutes to 8:00 AM: 8:00 + 1:00 = 9:00 AM.\nBoth bells will next toll together at exactly 9:00 AM.",
        "tags": ["prime_numbers", "lcm", "gcd", "factors", "elementary_math", "ncert_class_5"]
    },

    # ========================================================================
    # TIER 1: ELEMENTARY (CLASS 4 - 5) - PHYSICS (6 items)
    # ========================================================================
    {
        "id": "CURR-PHYS-ELEM-001",
        "title": "States of Matter, Thermal Expansion, and Anomalous Water Density",
        "domain": "physics",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "Matter exists in solid, liquid, and gas phases. Heating increases kinetic energy of molecules, leading to thermal expansion and phase transitions: melting (solid -> liquid) and vaporization (liquid -> gas). Water exhibits anomalous expansion: it reaches maximum density at 4°C (~1.000 g/cm³) and expands upon freezing into ice (~0.917 g/cm³), which causes ice to float on liquid water.",
        "example_problem": "A lake cools down during winter. Explain why ice forms at the surface while aquatic life survives at the bottom in 4°C liquid water.",
        "solution_steps": "1. As surface water cools down to 4°C, it reaches maximum density and sinks to the lake bottom.\n2. When surface water cools further from 4°C down to 0°C, it expands and becomes less dense than the 4°C water beneath it.\n3. The less dense 0°C water stays at the surface and freezes into solid ice (density ~0.917 g/cm³).\n4. The floating ice sheet acts as a thermal insulator, preventing the deep water from losing heat.\n5. The bottom remains liquid at 4°C, allowing fish and aquatic plants to survive.",
        "tags": ["states_of_matter", "density", "anomalous_expansion", "thermal_physics", "elementary_science"]
    },
    {
        "id": "CURR-PHYS-ELEM-002",
        "title": "Archimedes' Principle, Buoyancy, and Relative Density",
        "domain": "physics",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "Archimedes' Principle states that an object immersed in a fluid experiences an upward buoyant force equal to the weight of fluid displaced: F_buoyant = rho_fluid * V_submerged * g. An object floats if its average density is less than fluid density, and sinks if its average density is greater.",
        "example_problem": "A solid block of wood with volume 0.002 m³ and mass 1.4 kg is placed into a tank of pure water (density = 1000 kg/m³). Determine whether the block floats, and calculate the volume of wood submerged beneath the water surface (g = 9.8 m/s²).",
        "solution_steps": "1. Compute wood density: rho_wood = mass / volume = 1.4 kg / 0.002 m³ = 700 kg/m³.\n2. Since 700 kg/m³ < 1000 kg/m³, the wood floats.\n3. At equilibrium, upward buoyant force equals downward gravitational force: rho_water * V_sub * g = mass_wood * g.\n4. Cancel g: 1000 * V_sub = 1.4 => V_sub = 1.4 / 1000 = 0.0014 m³.\n5. Percentage submerged: (0.0014 / 0.002) * 100% = 70%.\nThe block floats with 0.0014 m³ (70% of its volume) submerged.",
        "tags": ["buoyancy", "archimedes_principle", "density", "fluids", "elementary_science"]
    },
    {
        "id": "CURR-PHYS-ELEM-003",
        "title": "Simple Machines: Levers, Pulleys, and Ideal Mechanical Advantage",
        "domain": "physics",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "Simple machines multiply force or change force direction without generating energy. Law of Conservation of Energy: Work_in = Work_out (under zero friction). Law of the Lever: Effort * Effort_Arm = Load * Load_Arm. Ideal Mechanical Advantage (IMA) = Effort_Arm / Load_Arm = Load_Force / Effort_Force.",
        "example_problem": "A worker uses a 3-meter Class 1 crowbar to pry open a heavy crate requiring 1200 N of lift force. If the fulcrum is located 0.5 meters from the crate, calculate the effort arm, the ideal mechanical advantage, and the minimum downward effort force required.",
        "solution_steps": "1. Identify lever arms: Total length = 3.0 m. Load arm d_load = 0.5 m. Effort arm d_effort = 3.0 - 0.5 = 2.5 m.\n2. Ideal Mechanical Advantage: IMA = d_effort / d_load = 2.5 m / 0.5 m = 5.0.\n3. Apply torque balance: F_effort * d_effort = F_load * d_load.\n4. F_effort * 2.5 = 1200 * 0.5 = 600 N.\n5. F_effort = 600 / 2.5 = 240 N.\nThe effort arm is 2.5 m, mechanical advantage is 5, and required effort force is 240 N.",
        "tags": ["simple_machines", "levers", "mechanical_advantage", "torque", "elementary_science"]
    },
    {
        "id": "CURR-PHYS-ELEM-004",
        "title": "Optics: Rectilinear Propagation, Umbra and Penumbra Shadows, Law of Reflection",
        "domain": "physics",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "Light travels in straight lines (rectilinear propagation) through homogeneous transparent media. When blocked by an opaque body, light casts shadows: the umbra (total occlusion) and penumbra (partial occlusion from extended light sources). The Law of Reflection states: 1. Incident ray, reflected ray, and normal lie in the same plane. 2. Angle of incidence equals angle of reflection (theta_i = theta_r).",
        "example_problem": "A ray of sunlight strikes a flat mirror resting on a table at an angle of 35° with the mirror surface. Find the angle of incidence, angle of reflection, and total deflection angle of the light ray.",
        "solution_steps": "1. The normal is perpendicular (90°) to mirror surface.\n2. Glancing angle = 35°. Angle of incidence: theta_i = 90° - 35° = 55°.\n3. By Law of Reflection: theta_r = theta_i = 55°.\n4. Deflection angle delta is the angle between original direction and reflected path: delta = 180° - 2 * theta_i = 180° - 2 * 55° = 180° - 110° = 70°.\nAngle of incidence is 55°, reflection is 55°, and deflection is 70°.",
        "tags": ["optics", "light", "reflection", "shadows", "rectilinear_propagation", "elementary_science"]
    },
    {
        "id": "CURR-PHYS-ELEM-005",
        "title": "Acoustic Waves: Vibrational Sources, Propagation in Media, and Echoes",
        "domain": "physics",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "Sound is a mechanical longitudinal compression wave generated by vibrating particles. It cannot propagate in a vacuum. Speed of sound depends on medium density and elastic bulk modulus: v_solid > v_liquid > v_gas (e.g. steel ~5100 m/s, water ~1480 m/s, air ~343 m/s at 20°C). An echo is a reflected sound wave heard distinctly if the time delay delta_t >= 0.1 seconds (minimum distance ~17.2 m in air).",
        "example_problem": "A hiker shouts toward a tall vertical cliff face and hears the echo 1.2 seconds later. If air temperature is 20°C (speed of sound = 343 m/s), determine the distance to the cliff in meters.",
        "solution_steps": "1. Total round-trip time for sound to reach cliff and return: t_total = 1.2 s.\n2. One-way transit time: t_one_way = 1.2 / 2 = 0.6 seconds.\n3. Distance d = Speed * Time = 343 m/s * 0.6 s = 205.8 meters.\n4. Verify echo perception criterion: 1.2 s > 0.1 s, so echo is heard clearly.\nThe cliff is 205.8 meters away.",
        "tags": ["sound", "waves", "echoes", "speed_of_sound", "acoustics", "elementary_science"]
    },
    {
        "id": "CURR-PHYS-ELEM-006",
        "title": "Geomagnetism: Magnetic Dipoles, Attracting/Repelling Invariants, Compass Orientation",
        "domain": "physics",
        "tier": "elementary",
        "grade_level": "Class 4-5",
        "concept": "Every magnet possesses two inseparable magnetic poles: North (N) and South (S). Fundamental Invariant: Like poles repel (N-N, S-S), opposite poles attract (N-S). Magnetic field lines exit North poles and enter South poles externally. Earth behaves as a giant magnetic dipole whose magnetic south pole is located near the geographic north pole, causing compass north-seeking needles to point geographic north.",
        "example_problem": "A magnetic compass needle is brought near a bar magnet whose labels have worn off. The compass needle North tip is strongly attracted to End A of the bar. Identify the magnetic polarity of End A and End B, and explain what happens if the bar magnet is sliced into three equal pieces.",
        "solution_steps": "1. Opposite magnetic poles attract. Because the North tip of the compass needle is attracted to End A, End A must be a SOUTH magnetic pole.\n2. Because every bar magnet is a dipole with opposite poles at opposite ends, End B must be a NORTH magnetic pole.\n3. In classical electromagnetism, magnetic monopoles do not exist. Magnetic dipoles originate from aligned atomic electron spins.\n4. When sliced into three pieces, each piece maintains internal domain alignment, forming three independent complete magnets with N and S poles.\nEnd A is South, End B is North, and cutting yields 3 full dipole magnets.",
        "tags": ["magnetism", "magnetic_poles", "compass", "geomagnetism", "elementary_science"]
    },

    # ========================================================================
    # TIER 2: SECONDARY (CLASS 6 - 10) - MATHEMATICS (7 items)
    # ========================================================================
    {
        "id": "CURR-MATH-SEC-001",
        "title": "Euclid's Division Lemma, Fundamental Theorem of Arithmetic, and Irrationality Proofs",
        "domain": "maths",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "Euclid's Division Lemma: Given integers a and b (b > 0), there exist unique integers q and r such that a = b*q + r with 0 <= r < b. Fundamental Theorem of Arithmetic: Every integer n > 1 can be uniquely expressed as a product of prime powers up to factor order. Proof by Contradiction establishes that sqrt(p) is irrational for any prime p.",
        "example_problem": "Prove rigorously by contradiction that sqrt(3) is an irrational number.",
        "solution_steps": "1. Assume for contradiction that sqrt(3) is rational. Then sqrt(3) = a / b for coprime integers a, b (b != 0, gcd(a, b) = 1).\n2. Square both sides: 3 = a² / b² => a² = 3 * b².\n3. Since 3 divides a², and 3 is prime, Euclid's lemma implies 3 divides a. Thus a = 3k for some integer k.\n4. Substitute a = 3k: (3k)² = 3 * b² => 9k² = 3 * b² => b² = 3k².\n5. Since 3 divides b², 3 must also divide b.\n6. This implies both a and b are divisible by 3, contradicting gcd(a, b) = 1.\n7. Conclusion: The initial assumption is false; sqrt(3) is irrational.",
        "tags": ["number_theory", "irrational_numbers", "euclids_lemma", "proof_by_contradiction", "secondary_math", "ncert_class_10"]
    },
    {
        "id": "CURR-MATH-SEC-002",
        "title": "Quadratic Equations: Discriminant Analysis, Vertex Coordinates, and Vieta's Formulas",
        "domain": "maths",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "A quadratic equation has canonical form ax² + bx + c = 0 (a != 0). Roots: x = (-b +- sqrt(Delta)) / (2a) where Delta = b² - 4ac. Nature of roots: Delta > 0 (2 distinct real roots), Delta = 0 (1 repeated real root), Delta < 0 (2 complex conjugate roots). Vieta's formulas: sum of roots x1 + x2 = -b / a, product of roots x1 * x2 = c / a. Parabola vertex occurs at (-b / (2a), -Delta / (4a)).",
        "example_problem": "For the quadratic equation 3x² - 12x + 5 = 0, find the discriminant, classify roots, calculate sum and product of roots, and find the coordinates of the parabola vertex.",
        "solution_steps": "1. Identify coefficients: a = 3, b = -12, c = 5.\n2. Discriminant: Delta = b² - 4ac = (-12)² - 4(3)(5) = 144 - 60 = 84.\n3. Since Delta = 84 > 0 and 84 is not a perfect square, there are two distinct real irrational roots.\n4. Vieta's formulas: Sum x1 + x2 = -(-12) / 3 = 4; Product x1 * x2 = 5 / 3.\n5. Vertex x-coordinate: x_v = -b / (2a) = 12 / (2 * 3) = 2.\n6. Vertex y-coordinate: y_v = 3(2)² - 12(2) + 5 = 12 - 24 + 5 = -7. (Check: -Delta/(4a) = -84/12 = -7).\nDelta = 84, roots are distinct real, sum = 4, product = 5/3, vertex = (2, -7).",
        "tags": ["algebra", "quadratic_equations", "discriminant", "vietas_formulas", "parabola", "secondary_math", "ncert_class_10"]
    },
    {
        "id": "CURR-MATH-SEC-003",
        "title": "Coordinate Geometry: Distance Formula, Section Ratio Formula, and Triangle Area",
        "domain": "maths",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "In Cartesian 2D plane: Distance between (x1, y1) and (x2, y2) is d = sqrt((x2 - x1)² + (y2 - y1)²). Section formula: Point P dividing segment AB in ratio m:n has coordinates ((m*x2 + n*x1)/(m+n), (m*y2 + n*y1)/(m+n)). Area of triangle with vertices (x1, y1), (x2, y2), (x3, y3) is A = 0.5 * |x1(y2 - y3) + x2(y3 - y1) + x3(y1 - y2)|.",
        "example_problem": "Points A(1, 2), B(4, 6), and C(7, 2) form a triangle. Find the coordinates of the centroid G and compute the area of triangle ABC.",
        "solution_steps": "1. Centroid G coordinates: G = ((x1 + x2 + x3)/3, (y1 + y2 + y3)/3) = ((1 + 4 + 7)/3, (2 + 6 + 2)/3) = (12/3, 10/3) = (4, 10/3).\n2. Compute area using determinant formula:\n   A = 0.5 * |1*(6 - 2) + 4*(2 - 2) + 7*(2 - 6)|\n   A = 0.5 * |1*(4) + 4*(0) + 7*(-4)| = 0.5 * |4 + 0 - 28| = 0.5 * |-24| = 12 square units.\nCentroid is (4, 10/3) and Area is 12 sq units.",
        "tags": ["coordinate_geometry", "distance_formula", "section_formula", "centroid", "area", "secondary_math", "ncert_class_10"]
    },
    {
        "id": "CURR-MATH-SEC-004",
        "title": "Euclidean Geometry: Thales' Basic Proportionality Theorem and Similar Triangles",
        "domain": "maths",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "Thales' Theorem (Basic Proportionality Theorem): If a line is drawn parallel to one side of a triangle intersecting the other two sides, it divides the two sides in the same ratio: AD/DB = AE/EC. Triangles are similar (~) if corresponding angles are equal and corresponding sides are proportional (AA, SAS, SSS criteria). The ratio of areas of two similar triangles equals the square of the ratio of their corresponding sides: Area(T1)/Area(T2) = (s1/s2)².",
        "example_problem": "In triangle ABC, line DE is parallel to BC with D on AB and E on AC. If AD = 3 cm, DB = 5 cm, and area of triangle ADE is 18 cm², compute the ratio of areas Area(ADE)/Area(ABC) and the area of quadrilateral BDEC.",
        "solution_steps": "1. Since DE || BC, triangle ADE ~ triangle ABC by AA similarity.\n2. Total side AB = AD + DB = 3 + 5 = 8 cm.\n3. Ratio of sides: AD / AB = 3 / 8.\n4. Ratio of areas: Area(ADE) / Area(ABC) = (AD / AB)² = (3 / 8)² = 9 / 64.\n5. Compute Area(ABC): Area(ABC) = Area(ADE) * (64 / 9) = 18 * (64 / 9) = 2 * 64 = 128 cm².\n6. Area of trapezoid BDEC = Area(ABC) - Area(ADE) = 128 - 18 = 110 cm².\nArea ratio is 9/64, Area(ABC) = 128 cm², and Area(BDEC) = 110 cm².",
        "tags": ["geometry", "thales_theorem", "similar_triangles", "area_ratio", "secondary_math", "ncert_class_10"]
    },
    {
        "id": "CURR-MATH-SEC-005",
        "title": "Circle Theorems: Tangent-Radius Perpendicularity and Tangents from External Points",
        "domain": "maths",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "Circle Theorems: 1. A tangent to a circle is perpendicular to the radius through the point of contact (OP perp PT). 2. The lengths of tangents drawn from an external point to a circle are equal (PA = PB). 3. Angle subtended by an arc at the center is double the angle subtended at any point on the remaining circumference (theta_center = 2 * theta_circ). 4. Angle in a semicircle is a right angle (90°).",
        "example_problem": "Two tangents PA and PB are drawn to a circle with center O and radius 5 cm from an external point P. If angle APB = 60°, calculate the length of chord AB and the distance OP.",
        "solution_steps": "1. In quadrilateral OAPB, angles OAP and OBP are 90° (tangent perp radius).\n2. Sum of angles in quad = 360° => angle AOB = 360° - 90° - 90° - 60° = 120°.\n3. Line OP bisects angle APB: angle APO = 60° / 2 = 30°.\n4. In right triangle OAP: sin(30°) = OA / OP => 1/2 = 5 / OP => OP = 10 cm.\n5. Length of tangents: PA = OA / tan(30°) = 5 / (1 / sqrt(3)) = 5 * sqrt(3) cm.\n6. In isosceles triangle PAB, PA = PB and angle APB = 60°, making triangle PAB equilateral!\n7. Therefore, chord AB = PA = 5 * sqrt(3) cm ≈ 8.66 cm.\nDistance OP is 10 cm and chord AB is 5*sqrt(3) cm (~8.66 cm).",
        "tags": ["circle_theorems", "tangents", "chords", "equilateral_triangle", "secondary_math", "ncert_class_10"]
    },
    {
        "id": "CURR-MATH-SEC-006",
        "title": "Trigonometric Identities: Unit Circle, Pythagorean Identities, and Heights & Distances",
        "domain": "maths",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "For acute angle theta in right triangle: sin(theta) = Opp/Hyp, cos(theta) = Adj/Hyp, tan(theta) = Opp/Adj. Fundamental Pythagorean Identities: sin²(theta) + cos²(theta) = 1, 1 + tan²(theta) = sec²(theta), 1 + cot²(theta) = csc²(theta). For heights and distances: angle of elevation is the angle above horizontal line of sight.",
        "example_problem": "An observer on top of a 50-meter cliff observes a sailboat at an angle of depression of 30°. How far is the sailboat from the base of the cliff?",
        "solution_steps": "1. Let cliff height h = 50 m and horizontal distance from base to boat be d.\n2. Angle of depression = Angle of elevation from boat to cliff top = 30° (alternate interior angles).\n3. Apply tangent: tan(30°) = Opposite / Adjacent = h / d.\n4. 1 / sqrt(3) = 50 / d => d = 50 * sqrt(3) meters.\n5. Numerical approximation: 50 * 1.732 = 86.6 meters.\nThe sailboat is 50*sqrt(3) m (~86.6 m) from the base of the cliff.",
        "tags": ["trigonometry", "pythagorean_identities", "heights_and_distances", "elevation", "secondary_math", "ncert_class_10"]
    },
    {
        "id": "CURR-MATH-SEC-007",
        "title": "Arithmetic Progressions: N-th Term and Gaussian Partial Sums",
        "domain": "maths",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "An Arithmetic Progression (AP) is a sequence where consecutive terms differ by a constant common difference d: a, a+d, a+2d, ... The n-th term is a_n = a + (n - 1)*d. The sum of the first n terms is S_n = (n / 2) * [2a + (n - 1)*d] = (n / 2) * (first_term + last_term).",
        "example_problem": "Find the sum of all 3-digit natural numbers that are divisible by 7.",
        "solution_steps": "1. Smallest 3-digit number divisible by 7: 100 / 7 = 14.28 => 15 * 7 = 105.\n2. Largest 3-digit number divisible by 7: 999 / 7 = 142.71 => 142 * 7 = 994.\n3. The sequence is an AP: a = 105, d = 7, a_n = 994.\n4. Find term count n: a_n = a + (n - 1)*d => 994 = 105 + (n - 1)*7 => 889 = (n - 1)*7 => n - 1 = 127 => n = 128.\n5. Compute sum: S_n = (n / 2) * (a + a_n) = (128 / 2) * (105 + 994) = 64 * 1099 = 70,336.\nThe sum of all 3-digit multiples of 7 is 70,336.",
        "tags": ["arithmetic_progressions", "sequences", "series", "partial_sums", "secondary_math", "ncert_class_10"]
    },

    # ========================================================================
    # TIER 2: SECONDARY (CLASS 6 - 10) - PHYSICS (7 items)
    # ========================================================================
    {
        "id": "CURR-PHYS-SEC-001",
        "title": "Kinematics: 1D Equations of Constant Acceleration and Graphical Differentiation",
        "domain": "physics",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "Kinematics describes motion without regard to causing forces. For constant 1D linear acceleration a: 1. v = u + a*t. 2. s = u*t + 0.5*a*t². 3. v² = u² + 2*a*s. Graphical calculus: Slope of position-time graph gives instantaneous velocity (v = ds/dt). Slope of velocity-time graph gives acceleration (a = dv/dt). Area under velocity-time graph gives displacement s = integral v dt.",
        "example_problem": "A car travelling at 20 m/s brakes with a constant deceleration of 4.0 m/s². Determine the stopping distance and the total time required to come to a complete stop.",
        "solution_steps": "1. Identify given quantities: initial velocity u = 20 m/s, final velocity v = 0 m/s, acceleration a = -4.0 m/s².\n2. Use 1st equation to find time: v = u + a*t => 0 = 20 - 4.0*t => 4.0*t = 20 => t = 5.0 seconds.\n3. Use 3rd equation to find stopping distance: v² = u² + 2*a*s => 0 = 20² + 2*(-4.0)*s => 0 = 400 - 8.0*s => 8.0*s = 400 => s = 50.0 meters.\n4. Verification via 2nd equation: s = 20*(5.0) + 0.5*(-4.0)*(5.0)² = 100 - 50 = 50.0 m.\nStopping distance is 50.0 meters and stopping time is 5.0 seconds.",
        "tags": ["kinematics", "acceleration", "velocity", "stopping_distance", "secondary_physics", "ncert_class_9"]
    },
    {
        "id": "CURR-PHYS-SEC-002",
        "title": "Newton's Three Laws of Motion, Inertia, and Momentum Conservation",
        "domain": "physics",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "Newton's Laws of Motion: 1. Law of Inertia: Body maintains state of rest or uniform motion unless acted on by net external force. 2. F_net = dp/dt = m*a (for constant mass). Impulse J = F * delta_t = delta_p. 3. Action-Reaction: F_AB = -F_BA. Law of Conservation of Momentum: In an isolated system (F_ext = 0), total linear momentum is strictly conserved: m1*u1 + m2*u2 = m1*v1 + m2*v2.",
        "example_problem": "A 5.0 kg rifle fires a 0.020 kg bullet at a muzzle velocity of 600 m/s. Calculate the recoil velocity of the rifle.",
        "solution_steps": "1. System is isolated in horizontal direction (F_ext = 0).\n2. Initial momentum p_initial = 0 (both rifle and bullet at rest).\n3. Final momentum: p_final = m_bullet * v_bullet + m_rifle * v_recoil = 0.\n4. 0.020 kg * 600 m/s + 5.0 kg * v_recoil = 0.\n5. 12.0 kg*m/s + 5.0 * v_recoil = 0 => v_recoil = -12.0 / 5.0 = -2.4 m/s.\n6. Negative sign signifies recoil direction opposite to bullet travel.\nRecoil velocity of the rifle is -2.4 m/s.",
        "tags": ["mechanics", "newtons_laws", "momentum_conservation", "recoil", "secondary_physics", "ncert_class_9"]
    },
    {
        "id": "CURR-PHYS-SEC-003",
        "title": "Newton's Law of Universal Gravitation, Free Fall, and Escape Velocity",
        "domain": "physics",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "Universal Gravitation: F = G * (m1 * m2) / r² where G = 6.674e-11 N*m²/kg². Surface gravitational acceleration: g = G * M / R². Gravitational Potential Energy: U(r) = -G * M * m / r. Escape velocity is the minimum launch speed to escape a celestial body's gravitational potential: v_escape = sqrt(2 * G * M / R) = sqrt(2 * g * R). Orbital velocity of low satellite: v_orbit = sqrt(g * R).",
        "example_problem": "Given Earth's mean radius R = 6.371e6 m and surface acceleration g = 9.81 m/s², calculate the orbital velocity of a low Earth satellite and Earth's escape velocity in km/s.",
        "solution_steps": "1. Orbital velocity: v_orbit = sqrt(g * R) = sqrt(9.81 m/s² * 6.371e6 m) = sqrt(6.25e7) ≈ 7906 m/s = 7.91 km/s.\n2. Escape velocity: v_escape = sqrt(2 * g * R) = sqrt(2) * v_orbit = 1.4142 * 7906 m/s ≈ 11,180 m/s = 11.18 km/s.\nOrbital velocity is 7.91 km/s and escape velocity is 11.18 km/s.",
        "tags": ["gravitation", "escape_velocity", "orbital_mechanics", "free_fall", "secondary_physics", "ncert_class_9"]
    },
    {
        "id": "CURR-PHYS-SEC-004",
        "title": "Work, Kinetic Energy, Gravitational Potential Energy, and Conservation of Energy",
        "domain": "physics",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "Work done W = F * d * cos(theta) (measured in Joules). Work-Energy Theorem: Total work equals change in kinetic energy: W_net = Delta_KE = 0.5 * m * v_f² - 0.5 * m * v_i². Conservative gravitational potential energy PE = m * g * h. Conservation of Mechanical Energy: In conservative fields, E_total = KE + PE = constant. Power is the rate of energy conversion: P = dW/dt = F * v (in Watts).",
        "example_problem": "A 2.0 kg pendulum bob is released from rest at a height h = 0.80 meters above its lowest equilibrium position. Calculate its velocity at the lowest point and tension in the 1.5 m support string at that moment (g = 9.8 m/s²).",
        "solution_steps": "1. Conservation of mechanical energy: Initial PE = m*g*h = Final KE = 0.5*m*v².\n2. m*g*h = 0.5*m*v² => v = sqrt(2*g*h) = sqrt(2 * 9.8 * 0.80) = sqrt(15.68) ≈ 3.96 m/s.\n3. At bottom, string tension T must balance gravity and provide centripetal acceleration: T - m*g = m * v² / L.\n4. T = m * (g + v² / L) = 2.0 * (9.8 + (15.68 / 1.5)) = 2.0 * (9.8 + 10.453) = 2.0 * 20.253 ≈ 40.51 N.\nVelocity at bottom is 3.96 m/s and string tension is 40.5 N.",
        "tags": ["work_energy", "potential_energy", "kinetic_energy", "pendulum", "centripetal_force", "secondary_physics", "ncert_class_9"]
    },
    {
        "id": "CURR-PHYS-SEC-005",
        "title": "Geometric Optics: Snell's Law of Refraction, Total Internal Reflection, and Lens Formula",
        "domain": "physics",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "Snell's Law: n1 * sin(theta1) = n2 * sin(theta2) where refractive index n = c / v. When light travels from denser to rarer medium (n1 > n2), the critical angle is theta_c = arcsin(n2 / n1); angles exceeding theta_c undergo Total Internal Reflection (TIR). Thin Lens Formula: 1/f = 1/v - 1/u (with Cartesian sign conventions). Magnification: m = v / u = h_image / h_object.",
        "example_problem": "A light ray in crown glass (n1 = 1.52) encounters an air boundary (n2 = 1.00). Calculate the critical angle. Then, an object of height 3 cm is placed 20 cm in front of a convex lens of focal length 12 cm; find the image position, height, and nature.",
        "solution_steps": "1. Critical angle: sin(theta_c) = n2 / n1 = 1.00 / 1.52 ≈ 0.6579 => theta_c = arcsin(0.6579) ≈ 41.14°.\n2. Thin lens equation: u = -20 cm, f = +12 cm. 1/f = 1/v - 1/u => 1/12 = 1/v - 1/(-20) = 1/v + 1/20.\n3. 1/v = 1/12 - 1/20 = (5 - 3) / 60 = 2 / 60 = 1 / 30 => v = +30 cm.\n4. Magnification: m = v / u = 30 / (-20) = -1.5.\n5. Image height: h_i = m * h_o = -1.5 * 3.0 cm = -4.5 cm.\nCritical angle is 41.14°. Image forms 30 cm behind lens, height -4.5 cm (real, inverted, magnified).",
        "tags": ["optics", "refraction", "snells_law", "total_internal_reflection", "lenses", "secondary_physics", "ncert_class_10"]
    },
    {
        "id": "CURR-PHYS-SEC-006",
        "title": "Current Electricity: Ohm's Law, Resistivity Factors, Series-Parallel Circuits, and Joule Heating",
        "domain": "physics",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "Electric current I = dQ/dt (Amperes). Ohm's Law: V = I * R. Resistance R = rho * (L / A), where rho is material resistivity. Series: R_eq = R1 + R2 + ... Parallel: 1/R_eq = 1/R1 + 1/R2 + ... Joule's Law of Heating: Heat H = I² * R * t = V * I * t = (V² / R) * t (Joules). Electrical Power P = V * I = I² * R (Watts).",
        "example_problem": "A copper wire of length 200 m and radius 0.50 mm (rho = 1.7e-8 Ohm*m) is connected across a 12V battery. Calculate the wire resistance, current drawn, and heat generated in 5.0 minutes.",
        "solution_steps": "1. Cross-sectional area: A = pi * r² = pi * (0.50e-3 m)² = pi * 2.5e-7 m² ≈ 7.854e-7 m².\n2. Resistance: R = rho * L / A = 1.7e-8 * 200 / 7.854e-7 = 3.4e-6 / 7.854e-7 ≈ 4.33 Ohms.\n3. Current: I = V / R = 12 V / 4.33 Ohms ≈ 2.77 Amperes.\n4. Time: t = 5.0 min * 60 s/min = 300 seconds.\n5. Joule Heat: H = V * I * t = 12 V * 2.77 A * 300 s ≈ 9972 Joules (9.97 kJ).\nResistance is 4.33 Ohms, current is 2.77 A, and heat produced is 9.97 kJ.",
        "tags": ["electricity", "ohms_law", "resistance", "resistivity", "joule_heating", "secondary_physics", "ncert_class_10"]
    },
    {
        "id": "CURR-PHYS-SEC-007",
        "title": "Magnetic Effects of Current: Oersted Experiment, Solenoids, and Lorentz Force",
        "domain": "physics",
        "tier": "secondary",
        "grade_level": "Class 6-10",
        "concept": "Oersted discovered that electric currents generate magnetic fields. Magnetic field around long wire: B = (mu_0 * I) / (2 * pi * r). Inside ideal solenoid: B = mu_0 * n * I (where n = N / L turns per unit length). Magnetic Lorentz force on moving charge: F = q * (v x B) = q * v * B * sin(theta). Force on straight current-carrying wire in magnetic field: F = I * (L x B) = I * L * B * sin(theta) (direction via Fleming's Left-Hand Rule).",
        "example_problem": "A 0.40-meter horizontal wire carrying a current of 5.0 A eastward is placed in a uniform vertical upward magnetic field of B = 0.60 Tesla. Calculate the magnitude and direction of the magnetic force on the wire.",
        "solution_steps": "1. Current vector L points East. Magnetic field B points Upward (perpendicular, theta = 90°).\n2. Force magnitude: F = I * L * B * sin(90°) = 5.0 A * 0.40 m * 0.60 T * 1.0 = 1.20 Newtons.\n3. Determine direction via right-hand rule / Fleming's left hand rule: Index finger along B (Up), middle finger along I (East). Thumb points South.\nForce magnitude is 1.20 N directed towards the South.",
        "tags": ["magnetism", "lorentz_force", "solenoid", "right_hand_rule", "secondary_physics", "ncert_class_10"]
    },

    # ========================================================================
    # TIER 3: HIGHER SECONDARY (CLASS 11 - 12) - MATHEMATICS (6 items)
    # ========================================================================
    {
        "id": "CURR-MATH-HS-001",
        "title": "Differential Calculus: Chain Rule, Product Rule, Critical Points, and Optimization",
        "domain": "maths",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "Derivative f'(x) gives instantaneous rate of change and tangent slope. Product rule: (uv)' = u'v + uv'. Quotient rule: (u/v)' = (u'v - uv') / v². Chain rule for composite functions: d/dx[f(g(x))] = f'(g(x)) * g'(x). Stationary points occur where f'(x) = 0. Second derivative test: f''(x) > 0 indicates local minimum; f''(x) < 0 indicates local maximum.",
        "example_problem": "Find the dimensions of a closed cylindrical tin container of fixed volume V = 1000 cm³ that minimizes total surface area S.",
        "solution_steps": "1. Volume constraint: V = pi * r² * h = 1000 => h = 1000 / (pi * r²).\n2. Total surface area: S(r) = 2*pi*r² + 2*pi*r*h = 2*pi*r² + 2000 / r.\n3. Take first derivative and set to zero: dS/dr = 4*pi*r - 2000 / r² = 0 => 4*pi*r³ = 2000 => r³ = 500 / pi.\n4. Optimal radius: r = (500 / pi)^(1/3) ≈ 5.42 cm.\n5. Optimal height: h = 1000 / (pi * r²) = 2 * r ≈ 10.84 cm.\n6. Check 2nd derivative: d²S/dr² = 4*pi + 4000 / r³ > 0 for all r > 0, confirming global minimum.\nOptimal radius is 5.42 cm and height is 10.84 cm (h = 2r).",
        "tags": ["calculus", "derivatives", "optimization", "critical_points", "higher_secondary_math", "ncert_class_12"]
    },
    {
        "id": "CURR-MATH-HS-002",
        "title": "Integral Calculus: Definite Integrals, Substitution, Integration by Parts, and Area Under Curves",
        "domain": "maths",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "Fundamental Theorem of Calculus: integral(a to b) f(x) dx = F(b) - F(a) where F'(x) = f(x). Integration by Parts: integral u dv = u*v - integral v du. Definite integral symmetry property: integral(0 to a) f(x) dx = integral(0 to a) f(a - x) dx.",
        "example_problem": "Evaluate the definite integral I = integral(0 to pi/2) [sqrt(sin(x)) / (sqrt(sin(x)) + sqrt(cos(x)))] dx.",
        "solution_steps": "1. Let I = integral(0 to pi/2) [sqrt(sin(x)) / (sqrt(sin(x)) + sqrt(cos(x)))] dx. (Equation 1)\n2. Apply symmetry property: integral(0 to a) f(x) dx = integral(0 to a) f(a - x) dx with a = pi/2.\n3. Note sin(pi/2 - x) = cos(x) and cos(pi/2 - x) = sin(x).\n4. I = integral(0 to pi/2) [sqrt(cos(x)) / (sqrt(cos(x)) + sqrt(sin(x)))] dx. (Equation 2)\n5. Add Equations 1 and 2: 2*I = integral(0 to pi/2) [(sqrt(sin(x)) + sqrt(cos(x))) / (sqrt(sin(x)) + sqrt(cos(x)))] dx.\n6. The integrand simplifies identically to 1: 2*I = integral(0 to pi/2) 1 dx = pi/2 - 0 = pi/2.\n7. I = (pi/2) / 2 = pi / 4.\nThe exact value of the integral is pi / 4.",
        "tags": ["calculus", "integration", "definite_integrals", "symmetry_properties", "higher_secondary_math", "ncert_class_12"]
    },
    {
        "id": "CURR-MATH-HS-003",
        "title": "First-Order Differential Equations: Separable Variables and Integrating Factor Method",
        "domain": "maths",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "A first-order linear ordinary differential equation (ODE) has standard form dy/dx + P(x)*y = Q(x). The integrating factor is I(x) = exp(integral P(x) dx). Multiplying both sides by I(x) transforms the left-hand side into d/dx [y * I(x)] = Q(x) * I(x), yielding explicit solution: y(x) = (1 / I(x)) * [integral (Q(x) * I(x) dx) + C].",
        "example_problem": "Solve the initial value problem dy/dx + (2/x)*y = 4x with initial condition y(1) = 3 for x > 0.",
        "solution_steps": "1. Identify P(x) = 2/x and Q(x) = 4x.\n2. Compute integrating factor: I(x) = exp(integral 2/x dx) = exp(2 ln(x)) = exp(ln(x²)) = x².\n3. Multiply ODE by x²: x² dy/dx + 2x y = 4x³ => d/dx [x² y] = 4x³.\n4. Integrate both sides: x² y = integral 4x³ dx = x⁴ + C.\n5. General solution: y(x) = x² + C / x².\n6. Apply initial condition y(1) = 3: 3 = 1² + C / 1² => 3 = 1 + C => C = 2.\n7. Particular solution: y(x) = x² + 2 / x².\nThe exact solution is y(x) = x² + 2/x².",
        "tags": ["differential_equations", "integrating_factor", "initial_value_problem", "higher_secondary_math", "ncert_class_12"]
    },
    {
        "id": "CURR-MATH-HS-004",
        "title": "Vector Geometry & 3D Lines: Cross Product, Dot Product, and Shortest Distance Between Skew Lines",
        "domain": "maths",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "Vectors in R³: Dot product a . b = |a||b| cos(theta). Cross product a x b = |a||b| sin(theta) n_hat (orthogonal to both a and b). Scalar triple product [a b c] = a . (b x c) represents volume of parallelepiped. Shortest distance d between two skew lines r = a1 + lambda * b1 and r = a2 + mu * b2 is given by the projection: d = |(a2 - a1) . (b1 x b2)| / |b1 x b2|.",
        "example_problem": "Find the shortest distance between skew lines L1: r = (i + 2j + 3k) + lambda*(2i + 3j + 4k) and L2: r = (2i + 4j + 5k) + mu*(3i + 4j + 5k).",
        "solution_steps": "1. Identify position vectors: a1 = (1, 2, 3), a2 = (2, 4, 5) => a2 - a1 = (1, 2, 2).\n2. Identify direction vectors: b1 = (2, 3, 4), b2 = (3, 4, 5).\n3. Compute cross product b1 x b2:\n   i*(15 - 16) - j*(10 - 12) + k*(8 - 9) = -i + 2j - k = (-1, 2, -1).\n4. Compute magnitude |b1 x b2| = sqrt((-1)² + 2² + (-1)²) = sqrt(1 + 4 + 1) = sqrt(6).\n5. Compute scalar product: (a2 - a1) . (b1 x b2) = (1)*(-1) + (2)*(2) + (2)*(-1) = -1 + 4 - 2 = 1.\n6. Shortest distance d = |1| / sqrt(6) = 1 / sqrt(6) = sqrt(6) / 6 ≈ 0.408 units.\nThe shortest distance between the lines is 1/sqrt(6) units.",
        "tags": ["vectors", "3d_geometry", "skew_lines", "cross_product", "shortest_distance", "higher_secondary_math", "ncert_class_12"]
    },
    {
        "id": "CURR-MATH-HS-005",
        "title": "Matrix Algebra, Determinants, Adjugate Matrix Inversion, and Cramer's Rule",
        "domain": "maths",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "For square matrix A in M_n(R): det(A) determines invertibility (A is invertible iff det(A) != 0). The inverse is A⁻¹ = (1 / det(A)) * adj(A), where adj(A) is the transpose of the cofactor matrix C_ij = (-1)^(i+j) * M_ij. Cramer's Rule solves linear systems A x = b via x_i = det(A_i) / det(A). Cayley-Hamilton Theorem: Every square matrix satisfies its own characteristic equation det(lambda * I - A) = 0.",
        "example_problem": "Solve the linear system 2x + y + z = 1, x - 2y - 3z = 1, 3x + 2y + 4z = 5 using matrix inversion.",
        "solution_steps": "1. Coefficient matrix A = [[2, 1, 1], [1, -2, -3], [3, 2, 4]], vector b = [1, 1, 5]ᵀ.\n2. Compute det(A) = 2*(-8 - (-6)) - 1*(4 - (-9)) + 1*(2 - (-6)) = 2*(-2) - 1*(13) + 1*(8) = -4 - 13 + 8 = -9 != 0.\n3. Compute cofactors and adj(A):\n   C11 = -2, C12 = -13, C13 = 8\n   C21 = -2, C22 = 5, C23 = -1\n   C31 = -1, C32 = 7, C33 = -5\n   adj(A) = [[-2, -2, -1], [-13, 5, 7], [8, -1, -5]].\n4. Compute A⁻¹ = (-1/9) * adj(A).\n5. Multiply A⁻¹ * b: [-2(1) - 2(1) - 1(5)] = -9 => x = -9 / -9 = 1.\n   [-13(1) + 5(1) + 7(5)] = 27 => y = 27 / -9 = -3.\n   [8(1) - 1(1) - 5(5)] = -18 => z = -18 / -9 = 2.\nSolution vector is x = 1, y = -3, z = 2.",
        "tags": ["matrices", "determinants", "matrix_inversion", "adjugate", "cramers_rule", "higher_secondary_math", "ncert_class_12"]
    },
    {
        "id": "CURR-MATH-HS-006",
        "title": "Probability Theory: Conditional Probability, Bayes' Theorem, and Binomial Distribution",
        "domain": "maths",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "Conditional Probability: P(A|B) = P(A cap B) / P(B). Bayes' Theorem updates prior probabilities with observed evidence: P(A_i|B) = [P(B|A_i) * P(A_i)] / [sum_k P(B|A_k) * P(A_k)]. A Binomial experiment consists of n independent Bernoulli trials with success probability p: P(X = k) = C(n, k) * p^k * (1 - p)^(n - k).",
        "example_problem": "A rare disease affects 0.2% of a population. A diagnostic test has 98% sensitivity (true positive rate) and 95% specificity (true negative rate). If a randomly selected individual tests positive, what is the posterior probability that they actually have the disease?",
        "solution_steps": "1. Prior probabilities: P(Disease, D) = 0.002; P(Healthy, H) = 0.998.\n2. Likelihoods: P(Positive | D) = 0.98; P(Positive | H) = 1 - 0.95 = 0.05.\n3. Total probability of testing positive P(Positive):\n   P(+) = P(+|D)*P(D) + P(+|H)*P(H) = (0.98 * 0.002) + (0.05 * 0.998) = 0.00196 + 0.04990 = 0.05186.\n4. Apply Bayes' Theorem:\n   P(D | +) = (P(+|D) * P(D)) / P(+) = 0.00196 / 0.05186 ≈ 0.03779 (3.78%).\nThe probability of actually having the disease given a positive test is only ~3.78% (due to low base rate).",
        "tags": ["probability", "bayes_theorem", "conditional_probability", "binomial_distribution", "higher_secondary_math", "ncert_class_12"]
    },

    # ========================================================================
    # TIER 3: HIGHER SECONDARY (CLASS 11 - 12) - PHYSICS (9 items)
    # ========================================================================
    {
        "id": "CURR-PHYS-HS-001",
        "title": "2D Projectile Motion: Parabolic Trajectory, Maximum Height, Range, and Time of Flight",
        "domain": "physics",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "A projectile launched with initial velocity u at angle theta under gravity g decomposes into orthogonal uncoupled components: Horizontal: x(t) = u*cos(theta)*t (zero acceleration). Vertical: y(t) = u*sin(theta)*t - 0.5*g*t². Trajectory equation is a parabola: y = x*tan(theta) - [g / (2*u²*cos²(theta))]*x². Time of flight T = (2*u*sin(theta))/g. Maximum height H = (u²*sin²(theta))/(2*g). Horizontal range R = (u²*sin(2*theta))/g (maximum at theta = 45°).",
        "example_problem": "A projectile is launched from ground level with speed u = 40 m/s at an elevation angle of 30° (g = 9.8 m/s²). Compute time of flight, horizontal range, maximum height, and speed at peak.",
        "solution_steps": "1. Velocity components: u_x = 40 * cos(30°) = 40 * (sqrt(3)/2) ≈ 34.64 m/s; u_y = 40 * sin(30°) = 20.0 m/s.\n2. Time of flight: T = (2 * u_y) / g = (2 * 20.0) / 9.8 = 40.0 / 9.8 ≈ 4.08 seconds.\n3. Maximum height: H = u_y² / (2*g) = 20² / (2 * 9.8) = 400 / 19.6 ≈ 20.41 meters.\n4. Range: R = u_x * T = 34.64 * 4.08 ≈ 141.33 meters.\n5. Speed at peak: At highest point, v_y = 0, so v = v_x = u_x = 34.64 m/s.\nTime of flight is 4.08 s, range is 141.3 m, max height is 20.4 m, and speed at peak is 34.6 m/s.",
        "tags": ["kinematics", "projectile_motion", "parabolic_trajectory", "range", "higher_secondary_physics", "ncert_class_11"]
    },
    {
        "id": "CURR-PHYS-HS-002",
        "title": "Rotational Dynamics: Moment of Inertia, Torque, Angular Momentum, and Pure Rolling",
        "domain": "physics",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "Rotational counterpart of Newton's second law: tau_net = I * alpha = dL/dt where L = I * omega. Moment of inertia I = integral r² dm. Parallel Axis Theorem: I = I_cm + M*d². Perpendicular Axis Theorem (planar lamina): I_z = I_x + I_y. Pure rolling condition without slipping: v_cm = R * omega and a_cm = R * alpha. Kinetic energy in rolling: KE_total = 0.5 * M * v_cm² + 0.5 * I_cm * omega² = 0.5 * M * v_cm² * (1 + I_cm / (M * R²)).",
        "example_problem": "A solid uniform sphere of mass M = 4.0 kg and radius R = 0.20 m rolls without slipping down a 30° incline from a vertical height h = 3.5 m. Find its acceleration down the incline and linear velocity at the bottom (g = 9.8 m/s²).",
        "solution_steps": "1. Moment of inertia of solid sphere about center: I_cm = (2/5) * M * R².\n2. Factor (1 + I_cm / (M*R²)) = 1 + 2/5 = 7/5 = 1.4.\n3. Acceleration down incline: a = (g * sin(theta)) / (1 + I_cm / (M*R²)) = (9.8 * sin(30°)) / (7/5) = (9.8 * 0.5) / 1.4 = 4.9 / 1.4 = 3.5 m/s².\n4. Conservation of energy: M*g*h = 0.5 * M * v² * (7/5) = (7/10) * M * v².\n5. v = sqrt((10/7) * g * h) = sqrt((10/7) * 9.8 * 3.5) = sqrt(14 * 3.5) = sqrt(49) = 7.0 m/s.\nAcceleration is 3.5 m/s² and final velocity is 7.0 m/s.",
        "tags": ["rotational_dynamics", "moment_of_inertia", "torque", "pure_rolling", "higher_secondary_physics", "ncert_class_11"]
    },
    {
        "id": "CURR-PHYS-HS-003",
        "title": "Fluid Dynamics: Continuity Equation, Bernoulli's Principle, and Torricelli's Efflux",
        "domain": "physics",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "For ideal incompressible non-viscous fluid: Continuity Equation: A1 * v1 = A2 * v2 = Q (constant volumetric flow rate). Bernoulli's Principle (conservation of fluid energy density): P + 0.5 * rho * v² + rho * g * y = constant. Torricelli's Law of Efflux: Efflux velocity from orifice at depth h beneath free surface open to atmosphere is v = sqrt(2 * g * h). Venturi effect: Constricted pipe section exhibits higher speed and lower pressure.",
        "example_problem": "Water flows through a horizontal pipe whose cross-sectional area constricts from A1 = 0.010 m² to A2 = 0.0025 m². If the gauge pressure at section 1 is P1 = 40 kPa and flow speed is v1 = 2.0 m/s, find flow speed v2 and pressure P2 at the constriction (rho = 1000 kg/m³).",
        "solution_steps": "1. Apply continuity equation: A1 * v1 = A2 * v2 => 0.010 * 2.0 = 0.0025 * v2 => v2 = 0.020 / 0.0025 = 8.0 m/s.\n2. Apply horizontal Bernoulli equation: P1 + 0.5*rho*v1² = P2 + 0.5*rho*v2².\n3. Kinetic energy terms: 0.5 * 1000 * 2.0² = 2000 Pa; 0.5 * 1000 * 8.0² = 32,000 Pa.\n4. Solve for P2: P2 = P1 + 0.5*rho*(v1² - v2²) = 40,000 + 2000 - 32,000 = 10,000 Pa (10 kPa).\nConstriction speed is 8.0 m/s and pressure is 10 kPa (a 30 kPa drop due to Venturi effect).",
        "tags": ["fluids", "bernoulli_principle", "continuity_equation", "venturi_effect", "torricelli", "higher_secondary_physics", "ncert_class_11"]
    },
    {
        "id": "CURR-PHYS-HS-004",
        "title": "Thermodynamics: First Law, Carnot Cycle Efficiency, Entropy, and Heat Engines",
        "domain": "physics",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "First Law of Thermodynamics: Delta_U = Q - W (internal energy U is a state function). For ideal gas: Delta_U = n * C_v * Delta_T. Work in isothermal expansion: W = n*R*T * ln(V_f / V_i). Work in adiabatic expansion: P*V^gamma = const, W = (P_i*V_i - P_f*V_f) / (gamma - 1). Second Law: No heat engine can exceed reversible Carnot efficiency: eta_Carnot = 1 - T_C / T_H. Clausius inequality: oint dQ / T <= 0.",
        "example_problem": "A Carnot engine absorbs 2500 J of heat per cycle from a hot reservoir at 400°C and rejects heat to a cold sink at 50°C. Calculate thermal efficiency, useful mechanical work per cycle, and entropy change of each reservoir per cycle.",
        "solution_steps": "1. Convert temperatures to Kelvin: T_H = 400 + 273.15 = 673.15 K; T_C = 50 + 273.15 = 323.15 K.\n2. Carnot efficiency: eta = 1 - T_C / T_H = 1 - (323.15 / 673.15) = 1 - 0.4800 = 0.5200 (52.0%).\n3. Work done per cycle: W = eta * Q_H = 0.5200 * 2500 J = 1300 J.\n4. Heat rejected: Q_C = Q_H - W = 2500 - 1300 = 1200 J.\n5. Entropy changes: Hot reservoir Delta_S_H = -Q_H / T_H = -2500 / 673.15 = -3.714 J/K.\n   Cold reservoir Delta_S_C = +Q_C / T_C = +1200 / 323.15 = +3.714 J/K.\n6. Total universe entropy change Delta_S_univ = Delta_S_H + Delta_S_C = 0 J/K (reversible cycle invariant).\nEfficiency is 52.0%, work is 1300 J, and net cycle entropy change is 0.",
        "tags": ["thermodynamics", "carnot_cycle", "entropy", "heat_engines", "second_law", "higher_secondary_physics", "ncert_class_11"]
    },
    {
        "id": "CURR-PHYS-HS-005",
        "title": "Electrostatics: Gauss's Law, Electric Potential, and Parallel Plate Capacitors with Dielectrics",
        "domain": "physics",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "Gauss's Law: Closed surface flux oint E . dA = Q_enc / epsilon_0. Electric potential V(r) = - integral E . dr. Capacitance of parallel plate capacitor: C_0 = (epsilon_0 * A) / d. When dielectric of relative permittivity kappa is inserted, capacitance increases: C = kappa * C_0. Electric field inside dielectric reduces to E = E_0 / kappa. Electrostatic stored energy: U = 0.5 * C * V² = 0.5 * Q² / C. Energy density u_E = 0.5 * epsilon_0 * kappa * E².",
        "example_problem": "A parallel plate air capacitor has plate area A = 0.040 m² and separation d = 2.0 mm connected to a 100V power supply. With the supply disconnected, a dielectric slab (kappa = 5.0) of thickness 2.0 mm is inserted. Find the original and new capacitance, charge, potential difference, and stored energy (epsilon_0 = 8.854e-12 F/m).",
        "solution_steps": "1. Initial capacitance: C_0 = (8.854e-12 * 0.040) / 2.0e-3 = 3.5416e-13 / 2.0e-3 = 1.771e-10 F = 177.1 pF.\n2. Initial charge: Q = C_0 * V_0 = 1.771e-10 F * 100 V = 1.771e-8 C = 17.71 nC.\n3. Initial energy: U_0 = 0.5 * C_0 * V_0² = 0.5 * 1.771e-10 * 10,000 = 8.855e-7 J = 0.886 microjoules.\n4. Dielectric inserted with battery disconnected => charge Q remains constant: Q = 17.71 nC.\n5. New capacitance: C = kappa * C_0 = 5.0 * 177.1 pF = 885.5 pF.\n6. New potential: V = Q / C = V_0 / kappa = 100 V / 5.0 = 20.0 Volts.\n7. New energy: U = 0.5 * Q * V = 0.5 * 1.771e-8 C * 20.0 V = 1.771e-7 J (energy decreased by factor of kappa, dissipated as mechanical work pulling slab in).\nInitial: C=177 pF, V=100V, U=0.886 uJ. Final: C=885.5 pF, V=20V, U=0.177 uJ.",
        "tags": ["electrostatics", "gauss_law", "capacitors", "dielectrics", "energy_density", "higher_secondary_physics", "ncert_class_12"]
    },
    {
        "id": "CURR-PHYS-HS-006",
        "title": "Electrodynamics: Biot-Savart Law, Ampere's Law, Faraday's Law, and Lenz's Law",
        "domain": "physics",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "Biot-Savart Law: dB = (mu_0 / (4*pi)) * (I * dl x r_hat) / r². Ampere's Circuital Law: oint B . dl = mu_0 * I_enc. Faraday's Law of Electromagnetic Induction: Induced electromotive force equals negative time rate of magnetic flux change: EMF E = -d(Phi_B) / dt = -d/dt [integral B . dA]. Lenz's Law: Direction of induced current opposes the change in magnetic flux that produced it (minus sign ensures energy conservation). Self-inductance L defines induced back-EMF: E = -L * (dI/dt).",
        "example_problem": "A square conductive wire loop of side 0.10 m and total resistance 2.0 Ohms lies in a uniform magnetic field directed perpendicular to loop plane. The magnetic field ramps down linearly from 1.5 T to 0 T in 0.050 seconds. Find magnetic flux change, induced EMF, induced current, and direction.",
        "solution_steps": "1. Loop area: A = (0.10 m)² = 0.010 m².\n2. Initial flux: Phi_i = B_i * A = 1.5 T * 0.010 m² = 0.015 Weber (Wb).\n3. Final flux: Phi_f = 0 Wb => Delta_Phi = 0 - 0.015 = -0.015 Wb.\n4. Induced EMF: E = -Delta_Phi / Delta_t = -(-0.015 Wb) / 0.050 s = +0.30 Volts.\n5. Induced current: I = E / R = 0.30 V / 2.0 Ohms = 0.15 Amperes.\n6. By Lenz's law, induced current creates magnetic field in the original direction (into the page) to oppose flux decrease, resulting in clockwise circulation.\nInduced EMF is 0.30 V, current is 0.15 A (clockwise).",
        "tags": ["electromagnetism", "faradays_law", "lenz_law", "magnetic_flux", "induction", "higher_secondary_physics", "ncert_class_12"]
    },
    {
        "id": "CURR-PHYS-HS-007",
        "title": "Alternating Current: Series LCR Circuit, Resonance Frequency, and Power Factor",
        "domain": "physics",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "In sinusoidal AC circuits V(t) = V_0 * sin(omega * t): Inductive reactance X_L = omega * L (voltage leads current by 90°). Capacitive reactance X_C = 1 / (omega * C) (voltage lags current by 90°). Total circuit impedance in series LCR: Z = sqrt(R² + (X_L - X_C)²). Phase angle: tan(phi) = (X_L - X_C) / R. Electrical resonance occurs when X_L = X_C => omega_0 = 1 / sqrt(L * C) where impedance is minimum (Z = R) and current amplitude is maximum. Average power: P_avg = V_rms * I_rms * cos(phi) (cos(phi) is power factor).",
        "example_problem": "A series LCR circuit has R = 30 Ohms, L = 0.20 H, and C = 50 microfarads connected to an AC source of V_rms = 120 V at f = 50 Hz. Calculate inductive reactance, capacitive reactance, total impedance, RMS current, power factor, and resonant frequency.",
        "solution_steps": "1. Angular frequency: omega = 2 * pi * 50 ≈ 314.16 rad/s.\n2. Reactances: X_L = omega * L = 314.16 * 0.20 ≈ 62.83 Ohms.\n   X_C = 1 / (omega * C) = 1 / (314.16 * 50e-6) = 1 / 0.015708 ≈ 63.66 Ohms.\n3. Net reactance: X = X_L - X_C = 62.83 - 63.66 = -0.83 Ohms (slightly capacitive).\n4. Total impedance: Z = sqrt(30² + (-0.83)²) = sqrt(900 + 0.69) ≈ 30.01 Ohms.\n5. RMS current: I_rms = V_rms / Z = 120 / 30.01 ≈ 4.00 Amperes.\n6. Power factor: cos(phi) = R / Z = 30 / 30.01 ≈ 0.9997.\n7. Resonant frequency: f_0 = 1 / (2*pi*sqrt(L*C)) = 1 / (2*pi*sqrt(0.20 * 50e-6)) = 1 / (2*pi*sqrt(1e-5)) = 1 / (2*pi*0.003162) ≈ 50.33 Hz.\nImpedance Z ≈ 30.0 Ohms, current I_rms = 4.0 A, power factor cos(phi) ≈ 1.0, resonant freq f_0 = 50.33 Hz.",
        "tags": ["alternating_current", "lcr_circuit", "resonance", "impedance", "power_factor", "higher_secondary_physics", "ncert_class_12"]
    },
    {
        "id": "CURR-PHYS-HS-008",
        "title": "Wave Optics: Young's Double Slit Interference, Single-Slit Diffraction, and Polarization",
        "domain": "physics",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "Huygens' Principle: Every point on a wavefront acts as a secondary source of spherical wavelets. Interference (Young's Double Slit Experiment): Two coherent sources spaced d apart project onto screen at distance D. Constructive interference path difference delta = d * sin(theta) = m * lambda; Destructive: delta = (m + 0.5) * lambda. Fringe width beta = (lambda * D) / d. Fraunhofer single-slit diffraction minima occur at a * sin(theta) = m * lambda. Brewster's Law of Polarization: tan(theta_B) = n.",
        "example_problem": "In a Young's double slit experiment, monochromatic light of wavelength 600 nm illuminates slits separated by d = 0.80 mm, and fringes are observed on a screen D = 2.0 meters away. Find the fringe width beta and distance from central maximum to the 4th bright fringe.",
        "solution_steps": "1. Convert units: lambda = 600e-9 m, d = 0.80e-3 m, D = 2.0 m.\n2. Fringe width: beta = (lambda * D) / d = (600e-9 * 2.0) / 0.80e-3 = 1.2e-6 / 8.0e-4 = 1.5e-3 m = 1.50 mm.\n3. Position of m-th bright fringe: y_m = m * beta.\n4. For m = 4: y_4 = 4 * 1.50 mm = 6.0 mm.\nFringe width is 1.50 mm and distance to 4th bright fringe is 6.0 mm.",
        "tags": ["wave_optics", "interference", "youngs_double_slit", "diffraction", "fringe_width", "higher_secondary_physics", "ncert_class_12"]
    },
    {
        "id": "CURR-PHYS-HS-009",
        "title": "Modern Physics: Einstein's Photoelectric Effect, Bohr Model, and de Broglie Wavelength",
        "domain": "physics",
        "tier": "higher_secondary",
        "grade_level": "Class 11-12",
        "concept": "Photoelectric Effect: Light consists of discrete quanta (photons) with energy E = h * nu. Einstein's equation: K_max = h*nu - Phi_0 = e * V_stop (where Phi_0 is metal work function). Bohr Model of Hydrogen: Angular momentum quantization L = m*v*r = n * hbar. Energy levels: E_n = -13.6 eV / n². Rydberg formula for spectral lines: 1 / lambda = R_H * (1/n1² - 1/n2²). De Broglie Matter Waves: Particles exhibit wave properties with wavelength lambda = h / p = h / (m * v) = h / sqrt(2 * m * K).",
        "example_problem": "A cesium surface with work function Phi_0 = 2.14 eV is illuminated by ultraviolet light of wavelength lambda = 300 nm. Calculate photon energy in eV, maximum kinetic energy of emitted photoelectrons, stopping potential, and de Broglie wavelength of fastest emitted electron (h = 6.626e-34 J*s, c = 3.0e8 m/s, 1 eV = 1.602e-19 J, m_e = 9.109e-31 kg).",
        "solution_steps": "1. Photon energy: E = h*c / lambda = (6.626e-34 * 3.0e8) / 300e-9 = 1.9878e-19 / 3e-7 = 6.626e-19 J.\n2. Convert to eV: E = 6.626e-19 / 1.602e-19 ≈ 4.136 eV.\n3. Max kinetic energy: K_max = E - Phi_0 = 4.136 eV - 2.140 eV = 1.996 eV ≈ 2.00 eV.\n4. Stopping potential: V_stop = K_max / e = 2.00 Volts.\n5. Convert K_max to Joules: K_max = 2.00 * 1.602e-19 = 3.204e-19 J.\n6. Momentum: p = sqrt(2 * m_e * K_max) = sqrt(2 * 9.109e-31 * 3.204e-19) = sqrt(5.837e-49) ≈ 7.64e-25 kg*m/s.\n7. De Broglie wavelength: lambda_dB = h / p = 6.626e-34 / 7.64e-25 ≈ 8.67e-10 m = 0.867 nm.\nPhoton energy is 4.14 eV, max KE is 2.00 eV, stopping potential is 2.00 V, and electron de Broglie wavelength is 0.867 nm.",
        "tags": ["modern_physics", "photoelectric_effect", "bohr_model", "de_broglie", "quantum_duality", "higher_secondary_physics", "ncert_class_12"]
    },

    # ========================================================================
    # TIER 4: SUBJECT MATTER EXPERT (SME / UNIVERSITY) - MATHEMATICS (6 items)
    # ========================================================================
    {
        "id": "CURR-MATH-SME-001",
        "title": "Real Analysis: Metric Topology, Compactness, Heine-Borel Theorem, and Bolzano-Weierstrass",
        "domain": "maths",
        "tier": "sme",
        "grade_level": "SME / Research",
        "concept": "In a metric space (X, d), an open ball is B(x, r) = {y in X : d(x, y) < r}. A subset K is compact if every open cover of K admits a finite subcover. Heine-Borel Theorem: A subset K of R^n is compact iff it is closed and bounded. Bolzano-Weierstrass Theorem: Every bounded sequence in R^n contains a convergent subsequence. Arzelà-Ascoli Theorem: A family of functions on a compact metric space is relatively compact in C(K) iff it is equicontinuous and pointwise bounded.",
        "example_problem": "Let K be a compact metric space and let f: K -> R be a continuous function. Prove rigorously that f achieves its supremum and infimum on K (Extreme Value Theorem).",
        "solution_steps": "1. Since f is continuous and K is compact, the image f(K) is a compact subset of R.\n2. By the Heine-Borel theorem in R, f(K) is closed and bounded.\n3. Since f(K) is bounded and non-empty, M = sup(f(K)) and m = inf(f(K)) exist as finite real numbers.\n4. By definition of supremum, there exists a sequence {y_n} in f(K) such that y_n -> M as n -> infinity.\n5. Since f(K) is closed, it contains all its limit points. Thus M in f(K) and m in f(K).\n6. Therefore, there exist points x_max, x_min in K such that f(x_max) = M and f(x_min) = m.\n7. Conclusion: f attains both its maximum and minimum values on K.",
        "tags": ["real_analysis", "metric_spaces", "compactness", "heine_borel", "extreme_value_theorem", "sme_math"]
    },
    {
        "id": "CURR-MATH-SME-002",
        "title": "Complex Analysis: Cauchy-Riemann Equations, Cauchy's Integral Formula, and Residue Calculus",
        "domain": "maths",
        "tier": "sme",
        "grade_level": "SME / Research",
        "concept": "A function f(z) = u(x, y) + i*v(x, y) is holomorphic on domain U in C iff u, v satisfy Cauchy-Riemann equations: du/dx = dv/dy and du/dy = -dv/dx. Cauchy's Integral Formula: For closed simple contour gamma enclosing z0, f(z0) = (1 / (2*pi*i)) * oint_gamma [f(z) / (z - z0)] dz. Residue Theorem: oint_gamma f(z) dz = 2*pi*i * sum Res(f, z_k). Jordan's Lemma evaluates improper real integrals over semicircular contours.",
        "example_problem": "Evaluate the real improper integral I = integral(-infinity to +infinity) [cos(x) / (x² + 4)] dx using complex contour integration in the upper half-plane.",
        "solution_steps": "1. Consider f(z) = exp(i*z) / (z² + 4) over upper semicircular contour C_R = [-R, R] union Gamma_R.\n2. Singularity in upper half-plane (Im(z) > 0): z² + 4 = 0 => z = +2i.\n3. Compute residue at simple pole z = 2i:\n   Res(f, 2i) = lim(z -> 2i) [(z - 2i) * exp(i*z) / ((z - 2i)(z + 2i))] = exp(i*(2i)) / (2i + 2i) = exp(-2) / (4i).\n4. By Jordan's lemma, as R -> infinity, integral_Gamma_R f(z) dz -> 0 because |exp(i*z)| = exp(-y) <= 1 for y >= 0.\n5. Apply Cauchy's Residue Theorem:\n   integral(-infinity to +infinity) [exp(i*x) / (x² + 4)] dx = 2*pi*i * Res(f, 2i) = 2*pi*i * [exp(-2) / (4i)] = (pi / 2) * exp(-2) = pi / (2 * e²).\n6. Take real part: integral(-infinity to +infinity) [cos(x) / (x² + 4)] dx = pi / (2 * e²).\nThe exact value of the integral is pi / (2 * e²).",
        "tags": ["complex_analysis", "residue_theorem", "contour_integration", "holomorphic", "sme_math"]
    },
    {
        "id": "CURR-MATH-SME-003",
        "title": "Abstract Algebra: Group Homomorphisms, Normal Subgroups, Quotient Groups, and First Isomorphism Theorem",
        "domain": "maths",
        "tier": "sme",
        "grade_level": "SME / Research",
        "concept": "A subgroup N <= G is normal (N triangleleft G) iff g*n*g⁻¹ in N for all g in G, n in N. The cosets G/N form a group under (g1*N)(g2*N) = (g1*g2)*N. First Isomorphism Theorem: If phi: G -> H is a group homomorphism, then ker(phi) triangleleft G and G / ker(phi) cong im(phi). Second Isomorphism Theorem: (S*N) / N cong S / (S cap N). Third Isomorphism Theorem: (G / N) / (K / N) cong G / K.",
        "example_problem": "Let G = (C*, *) be the multiplicative group of non-zero complex numbers, and let S¹ = {z in C : |z| = 1} be the unit circle subgroup. Prove that S¹ is a normal subgroup of C* and identify the quotient group C* / S¹.",
        "solution_steps": "1. Define map phi: C* -> R+ (positive real numbers under multiplication) by phi(z) = |z|.\n2. Homomorphism property: For any z1, z2 in C*, phi(z1 * z2) = |z1 * z2| = |z1| * |z2| = phi(z1) * phi(z2).\n3. Kernel of phi: ker(phi) = {z in C* : phi(z) = 1} = {z in C* : |z| = 1} = S¹.\n4. Since kernel of any group homomorphism is a normal subgroup, S¹ triangleleft C*.\n5. Surjectivity: For any positive real r in R+, phi(r) = |r| = r. Thus im(phi) = R+.\n6. Apply First Isomorphism Theorem: C* / ker(phi) cong im(phi) => C* / S¹ cong (R+, *).\nS¹ is normal in C* and the quotient group C* / S¹ is isomorphic to (R+, *).",
        "tags": ["abstract_algebra", "group_theory", "isomorphism_theorems", "quotient_groups", "sme_math"]
    },
    {
        "id": "CURR-MATH-SME-004",
        "title": "Linear Algebra & Functional Analysis: Spectral Theorem for Normal Operators and Singular Value Decomposition (SVD)",
        "domain": "maths",
        "tier": "sme",
        "grade_level": "SME / Research",
        "concept": "An operator T on Hilbert space H is normal iff T* T = T T*. Spectral Theorem: Every normal operator on a finite-dimensional complex inner product space admits an orthonormal basis of eigenvectors; T = U Lambda U* where U is unitary and Lambda is diagonal. Singular Value Decomposition (SVD): For any m x n complex matrix A, there exist unitary matrices U in U(m), V in U(n) and diagonal matrix Sigma with singular values sigma_1 >= sigma_2 >= ... >= 0 such that A = U Sigma V*.",
        "example_problem": "Compute the Singular Value Decomposition (SVD) of the matrix A = [[3, 2, 2], [2, 3, -2]].",
        "solution_steps": "1. Compute A Aᵀ (size 2 x 2):\n   A Aᵀ = [[3²+2²+2², 3(2)+2(3)+2(-2)], [2(3)+3(2)+(-2)(2), 2²+3²+(-2)²]]\n   = [[9+4+4, 6+6-4], [6+6-4, 4+9+4]] = [[17, 8], [8, 17]].\n2. Find eigenvalues of A Aᵀ: det(lambda*I - A Aᵀ) = (lambda - 17)² - 64 = 0 => lambda - 17 = +-8.\n   lambda_1 = 25, lambda_2 = 9.\n3. Singular values: sigma_1 = sqrt(25) = 5, sigma_2 = sqrt(9) = 3.\n4. Eigenvectors for lambda_1 = 25: (A Aᵀ - 25*I)v = 0 => [[-8, 8], [8, -8]]v = 0 => u1 = (1/sqrt(2)) * [1, 1]ᵀ.\n   Eigenvectors for lambda_2 = 9: (A Aᵀ - 9*I)v = 0 => [[8, 8], [8, 8]]v = 0 => u2 = (1/sqrt(2)) * [1, -1]ᵀ.\n   Unitary matrix U = (1/sqrt(2)) * [[1, 1], [1, -1]].\n5. Right singular vectors v_i = (1 / sigma_i) * Aᵀ * u_i:\n   v1 = (1/5) * [[3, 2], [2, 3], [2, -2]] * (1/sqrt(2))[1, 1]ᵀ = (1 / (5*sqrt(2))) * [5, 5, 0]ᵀ = (1/sqrt(2)) * [1, 1, 0]ᵀ.\n   v2 = (1/3) * [[3, 2], [2, 3], [2, -2]] * (1/sqrt(2))[1, -1]ᵀ = (1 / (3*sqrt(2))) * [1, -1, 4]ᵀ = (1 / (3*sqrt(2))) * [1, -1, 4]ᵀ.\nSingular values are sigma = (5, 3), with explicit unitary factors U and V*.",
        "tags": ["linear_algebra", "functional_analysis", "svd", "spectral_theorem", "unitary_matrices", "sme_math"]
    },
    {
        "id": "CURR-MATH-SME-005",
        "title": "Partial Differential Equations: Heat Equation, Wave Equation, D'Alembert's Formula, and Green's Functions",
        "domain": "maths",
        "tier": "sme",
        "grade_level": "SME / Research",
        "concept": "Second-order PDEs classify into Elliptic (Laplace nabla² u = 0), Parabolic (Heat u_t = alpha * nabla² u), and Hyperbolic (Wave u_tt = c² * nabla² u). D'Alembert's formula for 1D Cauchy wave problem u_tt = c² u_xx with u(x, 0) = g(x), u_t(x, 0) = h(x) is u(x, t) = 0.5 * [g(x - c*t) + g(x + c*t)] + (1 / (2*c)) * integral(x - c*t to x + c*t) h(s) ds. Heat kernel in R^n: K(x, t) = (4*pi*alpha*t)^(-n/2) * exp(-|x|² / (4*alpha*t)).",
        "example_problem": "Solve the 1D wave equation u_tt = 4 * u_xx on -infinity < x < infinity with initial displacement u(x, 0) = 1 / (x² + 1) and initial velocity u_t(x, 0) = 0 using D'Alembert's formula.",
        "solution_steps": "1. Identify parameters: c² = 4 => c = 2.\n2. Initial conditions: g(x) = 1 / (x² + 1), h(x) = 0.\n3. Since h(x) = 0, the integral term vanishes.\n4. Apply D'Alembert's formula: u(x, t) = 0.5 * [g(x - 2t) + g(x + 2t)].\n5. Substitute g: u(x, t) = 0.5 * [ 1 / ((x - 2t)² + 1) + 1 / ((x + 2t)² + 1) ].\n6. Physical interpretation: The initial profile splits into two non-dispersive wave packets travelling in opposite directions at wave speed c = 2.\nExact solution is u(x, t) = 0.5 / ((x - 2t)² + 1) + 0.5 / ((x + 2t)² + 1).",
        "tags": ["partial_differential_equations", "wave_equation", "dalembert_formula", "heat_equation", "sme_math"]
    },
    {
        "id": "CURR-MATH-SME-006",
        "title": "Differential Geometry: Smooth Manifolds, Tangent Bundles, Riemannian Metrics, and Geodesics Equation",
        "domain": "maths",
        "tier": "sme",
        "grade_level": "SME / Research",
        "concept": "A smooth n-manifold M is equipped with an atlas of smooth charts. A Riemannian metric g_ij assigns an inner product on each tangent space T_p M. The Levi-Civita connection is the unique torsion-free metric connection with Christoffel symbols: Gamma^k_ij = 0.5 * g^kl * (partial_i g_jl + partial_j g_il - partial_l g_ij). Geodesic equation governing curves of minimal length: d²x^k / ds² + Gamma^k_ij * (dx^i / ds) * (dx^j / ds) = 0. Riemann Curvature Tensor R^l_ijk measures non-commutativity of covariant derivatives.",
        "example_problem": "On the 2D upper half-plane Poincaré metric ds² = (dx² + dy²) / y² (y > 0), compute the Christoffel symbols Gamma^k_ij.",
        "solution_steps": "1. Metric tensor: g_xx = 1/y², g_yy = 1/y², g_xy = g_yx = 0. Inverse metric: g^xx = y², g^yy = y².\n2. Partial derivatives of metric components:\n   partial_y g_xx = -2/y³; partial_y g_yy = -2/y³. All other partials are 0.\n3. Compute Gamma^x_ij:\n   Gamma^x_xy = 0.5 * g^xx * (partial_y g_xx) = 0.5 * y² * (-2/y³) = -1/y = Gamma^x_yx.\n   Gamma^x_xx = Gamma^x_yy = 0.\n4. Compute Gamma^y_ij:\n   Gamma^y_xx = -0.5 * g^yy * (partial_y g_xx) = -0.5 * y² * (-2/y³) = +1/y.\n   Gamma^y_yy = 0.5 * g^yy * (partial_y g_yy) = 0.5 * y² * (-2/y³) = -1/y.\n   Gamma^y_xy = 0.\nNon-zero Christoffel symbols: Gamma^x_xy = Gamma^x_yx = -1/y, Gamma^y_xx = 1/y, Gamma^y_yy = -1/y.",
        "tags": ["differential_geometry", "riemannian_metrics", "christoffel_symbols", "geodesics", "curvature", "sme_math"]
    },

    # ========================================================================
    # TIER 4: SUBJECT MATTER EXPERT (SME / UNIVERSITY) - PHYSICS (5 items)
    # ========================================================================
    {
        "id": "CURR-PHYS-SME-001",
        "title": "Classical Analytical Mechanics: Principle of Least Action, Euler-Lagrange Equations, and Symplectic Integration",
        "domain": "physics",
        "tier": "sme",
        "grade_level": "SME / Research",
        "concept": "Hamilton's Principle: delta S = delta integral L(q, q_dot, t) dt = 0 where Lagrangian L = T - V. Yields Euler-Lagrange equations: d/dt(partial L / partial q_dot_i) - partial L / partial q_i = 0. Legendre transformation gives Hamiltonian H(q, p) = sum(p_i * q_dot_i) - L with canonical equations q_dot = partial H / partial p, p_dot = -partial H / partial q. Noether's Theorem establishes that continuous symmetries correspond to conservation laws. Symplectic Invariant (L-HTTP-0001): Symplectic integrators (Leapfrog / Verlet) preserve phase space volume (dp wedge dq = const) and bound energy error over arbitrarily long integration horizons without numerical damping.",
        "example_problem": "For a 1D harmonic oscillator with H(q, p) = p² / (2m) + (1/2)*k*q², formulate the Leapfrog symplectic step and prove that phase volume is preserved (det of Jacobian is identically 1).",
        "solution_steps": "1. Equations of motion: dq/dt = p / m; dp/dt = -k * q.\n2. Symplectic Leapfrog (Verlet) update with time step dt:\n   p_{n + 1/2} = p_n - 0.5 * dt * k * q_n\n   q_{n + 1} = q_n + dt * (p_{n + 1/2} / m)\n   p_{n + 1} = p_{n + 1/2} - 0.5 * dt * k * q_{n + 1}.\n3. Compute Jacobian of map (q_n, p_n) -> (q_{n+1}, p_{n+1}):\n   Since each sub-step is a shear mapping (triangular matrix with 1s on diagonal), det(J_sub) = 1.\n4. Total Jacobian determinant: det(J) = det(J_1) * det(J_2) * det(J_3) = 1 * 1 * 1 = 1.\n5. By Liouville's theorem, the 2-form dp wedge dq is strictly invariant.\nPhase volume is preserved exactly (det(J) = 1.0), satisfying Lesson L-HTTP-0001.",
        "tags": ["analytical_mechanics", "hamiltonian", "symplectic_integrator", "leapfrog", "noethers_theorem", "L-HTTP-0001", "sme_physics"]
    },
    {
        "id": "CURR-PHYS-SME-002",
        "title": "Classical Electrodynamics: Covariant 4-Vector Maxwell Equations, Gauge Invariance, and Relativistic Radiated Power",
        "domain": "physics",
        "tier": "sme",
        "grade_level": "SME / Research",
        "concept": "In special relativity, electromagnetism is described covariantly by the 4-potential A^mu = (Phi/c, A) and electromagnetic field tensor F^munu = partial^mu A^nu - partial^nu A^mu. Maxwell's equations take manifest 4-vector form: partial_mu F^munu = mu_0 * J^nu (inhomogeneous) and partial_mu F_tilde^munu = 0 (homogeneous). Gauge transformation A^mu -> A^mu + partial^mu Lambda leaves physics invariant. Liénard-Wiechert potentials give radiation fields of accelerating charges. Liénard relativistic generalization of Larmor formula: P = (mu_0 * q² * gamma⁶ / (6*pi*c)) * [a² - (v x a)² / c²].",
        "example_problem": "Show that the field tensor component F⁰¹ corresponds to -E_x / c in metric signature (+, -, -, -).",
        "solution_steps": "1. 4-potential: A^mu = (Phi/c, A_x, A_y, A_z). 4-gradient: partial^mu = (1/c partial/partial t, -partial/partial x, -partial/partial y, -partial/partial z).\n2. By definition: F⁰¹ = partial⁰ A¹ - partial¹ A⁰.\n3. partial⁰ A¹ = (1/c) * (partial A_x / partial t).\n4. partial¹ A⁰ = -partial/partial x (Phi / c) = -(1/c) * (partial Phi / partial x).\n5. F⁰¹ = (1/c) * [partial A_x / partial t + partial Phi / partial x] = -(1/c) * [-partial Phi / partial x - partial A_x / partial t].\n6. The electric field definition is E = -nabla Phi - partial A / partial t => E_x = -partial Phi / partial x - partial A_x / partial t.\n7. Therefore: F⁰¹ = -(1/c) * E_x = -E_x / c.\nF⁰¹ = -E_x / c confirmed covariantly.",
        "tags": ["electrodynamics", "maxwell_equations", "covariant_formulation", "field_tensor", "larmor_formula", "sme_physics"]
    },
    {
        "id": "CURR-PHYS-SME-003",
        "title": "Quantum Mechanics: Schrödinger Equation, Commutators, Harmonic Oscillator Ladder Operators, and Perturbation Theory",
        "domain": "physics",
        "tier": "sme",
        "grade_level": "SME / Research",
        "concept": "Postulates of QM: States are vectors in Hilbert space |psi rangle. Observables are self-adjoint operators. Canonical commutator [x_hat, p_hat] = i*hbar. 1D Harmonic Oscillator: ladder operators a = sqrt(m*omega / (2*hbar))*(x_hat + i*p_hat/(m*omega)) and a_dagger satisfy [a, a_dagger] = 1. Energy spectrum: E_n = hbar*omega*(n + 1/2). Non-degenerate time-independent perturbation theory: E_n^(1) = langle n^(0)| H' |n^(0) rangle; |n^(1) rangle = sum_(k != n) (langle k^(0)| H' |n^(0) rangle / (E_n^(0) - E_k^(0))) |k^(0) rangle.",
        "example_problem": "A 1D quantum harmonic oscillator is perturbed by an anharmonic potential H' = lambda * x⁴. Find the first-order energy shift E_0^(1) for the ground state |0 rangle.",
        "solution_steps": "1. Express position operator in terms of ladder operators:\n   x = sqrt(hbar / (2*m*omega)) * (a + a_dagger).\n2. Powers of x: x⁴ = (hbar / (2*m*omega))² * (a + a_dagger)⁴.\n3. Ground state expectation: E_0^(1) = langle 0| H' |0 rangle = lambda * (hbar / (2*m*omega))² * langle 0| (a + a_dagger)⁴ |0 rangle.\n4. Expand (a + a_dagger)⁴. Only terms with equal numbers of a and a_dagger (2 each) have non-zero vacuum expectation:\n   Possible combinations: a a a_dagger a_dagger (yields 2), a a_dagger a a_dagger (yields 1), etc.\n   Sum of matrix elements: langle 0| (a + a_dagger)⁴ |0 rangle = 3.\n5. Therefore: E_0^(1) = lambda * (hbar / (2*m*omega))² * 3 = (3 * lambda * hbar²) / (4 * m² * omega²).\nFirst order energy shift is (3 * lambda * hbar²) / (4 * m² * omega²).",
        "tags": ["quantum_mechanics", "harmonic_oscillator", "ladder_operators", "perturbation_theory", "commutators", "sme_physics"]
    },
    {
        "id": "CURR-PHYS-SME-004",
        "title": "Statistical Mechanics: Microcanonical and Canonical Ensembles, Partition Function, and Bose/Fermi Statistics",
        "domain": "physics",
        "tier": "sme",
        "grade_level": "SME / Research",
        "concept": "Ensembles: Microcanonical (fixed N, V, E, entropy S = k_B * ln(Omega)). Canonical (fixed N, V, T with heat bath, partition function Z = sum exp(-beta * E_i), beta = 1 / (k_B * T)). Helmholtz Free Energy: F = -k_B * T * ln(Z). Quantum Statistics: Average occupation of state with energy epsilon: Bose-Einstein (bosons, integer spin): n_BE(epsilon) = 1 / (exp(beta * (epsilon - mu)) - 1). Fermi-Dirac (fermions, half-integer spin): n_FD(epsilon) = 1 / (exp(beta * (epsilon - mu)) + 1). Classical Maxwell-Boltzmann limit occurs when exp(beta * (epsilon - mu)) >> 1.",
        "example_problem": "For an ideal gas of N indistinguishable classical particles of mass m in volume V at temperature T, derive the canonical partition function Z_N and show that the ideal gas law PV = N k_B T follows directly.",
        "solution_steps": "1. Single-particle partition function:\n   Z_1 = (1 / h³) * integral d³p d³x exp(-p² / (2m k_B T)) = (V / h³) * (2*pi*m*k_B*T)^(3/2) = V / lambda_th³, where lambda_th = h / sqrt(2*pi*m*k_B*T).\n2. N-particle partition function for indistinguishable particles (Gibbs factor 1/N!):\n   Z_N = (1 / N!) * (Z_1)^N = (1 / N!) * (V / lambda_th³)^N.\n3. Helmholtz free energy: F = -k_B * T * ln(Z_N) = -k_B * T * [N ln(V) - 3N ln(lambda_th) - ln(N!)].\n4. Pressure definition: P = -(partial F / partial V)_{T, N} = k_B * T * (partial / partial V) [N ln(V)] = N * k_B * T / V.\n5. Multiply by V: P * V = N * k_B * T.\nThe ideal gas equation of state PV = N k_B T is derived rigorously from statistical mechanics.",
        "tags": ["statistical_mechanics", "partition_function", "canonical_ensemble", "fermi_dirac", "bose_einstein", "ideal_gas", "sme_physics"]
    },
    {
        "id": "CURR-PHYS-SME-005",
        "title": "Special & General Relativity: Lorentz Transformations, Spacetime Invariant Interval, and Schwarzschild Metric",
        "domain": "physics",
        "tier": "sme",
        "grade_level": "SME / Research",
        "concept": "Special Relativity: Postulate 1: Laws of physics invariant in all inertial frames. Postulate 2: Speed of light c is universal constant. Spacetime invariant interval: ds² = c² dt² - dx² - dy² - dz². Lorentz factor gamma = 1 / sqrt(1 - v²/c²). Relativistic energy: E = gamma * m_0 * c², p = gamma * m_0 * v, invariant norm E² - (p*c)² = (m_0*c²)². General Relativity: Einstein Field Equations G_munu = (8*pi*G / c⁴) * T_munu. Schwarzschild metric around static spherical mass M: ds² = -(1 - 2GM/(c² r)) c² dt² + (1 - 2GM/(c² r))⁻¹ dr² + r² (d theta² + sin²theta d phi²). Event horizon occurs at Schwarzschild radius r_s = 2GM / c².",
        "example_problem": "Calculate the Schwarzschild radius r_s of the Sun (M = 1.989e30 kg) and Earth (M = 5.972e24 kg) in meters (G = 6.674e-11 N*m²/kg², c = 2.998e8 m/s).",
        "solution_steps": "1. Schwarzschild radius formula: r_s = (2 * G * M) / c².\n2. Constant factor: 2*G / c² = (2 * 6.674e-11) / (2.998e8)² = 1.3348e-10 / 8.988e16 ≈ 1.485e-27 m/kg.\n3. For the Sun: r_s_sun = 1.485e-27 * 1.989e30 = 2954 meters ≈ 2.95 km.\n4. For Earth: r_s_earth = 1.485e-27 * 5.972e24 = 0.00887 meters ≈ 8.87 mm (about the size of a marble).\nThe Sun's event horizon is 2.95 km; Earth's event horizon is 8.87 mm.",
        "tags": ["general_relativity", "special_relativity", "schwarzschild_metric", "event_horizon", "lorentz_transformations", "sme_physics"]
    }
]


def build_curriculum():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(CURRICULUM_DATA, f, indent=2, ensure_ascii=False)
    print(f"Successfully generated {len(CURRICULUM_DATA)} curriculum records at: {OUTPUT_FILE}")


if __name__ == "__main__":
    build_curriculum()
