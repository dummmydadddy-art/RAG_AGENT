#!/usr/bin/env python3
"""
scripts/verify_retrieval_tiers.py

Verifies semantic vector search retrieval across all 4 tiers:
1. Class 4-5 Elementary Science
2. Class 10 Secondary Math
3. Class 12 Higher Secondary Physics
4. SME Analytical Mechanics & Mathematics
"""

import math
import sqlite3
import struct
import httpx
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "storage" / "vectors.sqlite"

queries = [
    ("Class 4 Elementary Science", "buoyancy floating ice cube density water archimedes"),
    ("Class 10 Secondary Math", "quadratic equation discriminant real roots parabola vertex"),
    ("Class 12 Higher Secondary Physics", "parallel plate capacitor dielectric gauss law capacitance"),
    ("SME Analytical Mechanics", "Hamiltonian least action Euler Lagrange symplectic leapfrog phase volume")
]

conn = sqlite3.connect(str(DB_PATH))
c = conn.cursor()
c.execute("SELECT id, title, content, embedding FROM material_chunks WHERE course_id = 'stem_curriculum'")
rows = c.fetchall()
print(f"Loaded {len(rows)} material chunks for stem_curriculum.\n")

for label, q in queries:
    url = "http://localhost:11434/api/embed"
    payload = {"model": "nomic-embed-text", "input": f"search_query: {q}"}
    res = httpx.post(url, json=payload, timeout=10.0).json()
    q_vec = res["embeddings"][0]

    best_score = -1.0
    best_row = None
    for r_id, title, content, blob in rows:
        if blob:
            vec = struct.unpack(f"{len(blob)//4}f", blob)
            dot = sum(a * b for a, b in zip(q_vec, vec))
            norm_a = math.sqrt(sum(a * a for a in q_vec)) or 1.0
            norm_b = math.sqrt(sum(b * b for b in vec)) or 1.0
            cos = dot / (norm_a * norm_b)
            if cos > best_score:
                best_score = cos
                best_row = (r_id, title, content)
    print(f"=== {label} ===")
    print("Query:", q)
    print("Top Match:", best_row[1] if best_row else "None", f"(cosine score: {round(best_score, 4)})")
    preview = best_row[2][:160].replace("\n", " ") if best_row else ""
    print(f"Content: {preview}...\n")
