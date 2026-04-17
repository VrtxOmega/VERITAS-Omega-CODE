#!/usr/bin/env python3
"""
VERITAS Ω-CODE CLI Stub
A lightweight reference parser to load and hash a BuildClaim,
demonstrating the INTAKE gate of the deterministic protocol.
"""
import json
import hashlib
import sys
from datetime import datetime

def canonicalize(obj):
    if isinstance(obj, dict):
        return "{" + ",".join(f'"{k}":{canonicalize(v)}' for k, v in sorted(obj.items())) + "}"
    elif isinstance(obj, list):
        return "[" + ",".join(canonicalize(x) for x in obj) + "]"
    elif isinstance(obj, float):
        return f"{obj:.6f}".rstrip('0').rstrip('.') if '.' in f"{obj:.6f}" else str(obj)
    elif isinstance(obj, str):
        return f'"{obj}"'
    else:
        return str(obj).lower() if isinstance(obj, bool) else str(obj)

def parse_claim(filepath):
    try:
        with open(filepath, 'r') as f:
            claim_data = json.load(f)
    except FileNotFoundError:
        print(f"[FATAL] Claim file not found: {filepath}")
        sys.exit(1)
        
    print(f"[*] INTAKE GATE: Parsing BuildClaim '{filepath}'")
    
    # 1. Structural validation (Pseudo-Type Gate)
    required = ["project", "version", "commit", "primitives", "boundaries", "evidence"]
    missing = [req for req in required if req not in claim_data]
    if missing:
        print(f"[VIOLATION] Missing required fields: {missing}")
        return
        
    print(f"    Project: {claim_data['project']} v{claim_data['version']}")
    print(f"    Primitives: {len(claim_data['primitives'])}")
    print(f"    Evidence Items: {len(claim_data['evidence'])}")
    
    # Remove ClaimID if present to compute the canonical hash
    claim_id_provided = claim_data.pop("id", None)
    canonical_string = canonicalize(claim_data)
    computed_id = hashlib.sha256(canonical_string.encode('utf-8')).hexdigest()
    
    if claim_id_provided and claim_id_provided != computed_id:
        print(f"[VIOLATION] INTAKE_ID_MISMATCH")
        print(f"    Provided: {claim_id_provided}")
        print(f"    Computed: {computed_id}")
        return
        
    print(f"[*] TYPE GATE: Schema validation PASS")
    print(f"[*] INTAKE GATE: PASS")
    print(f"    ClaimID: {computed_id}")
    print("\n--- MOCK EXECUTION TRACE ---")
    print(f"[{datetime.utcnow().isoformat()}] Gate 2 EVIDENCE: INCONCLUSIVE (Mocked)")
    
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python veritas_stub.py <buildclaim.json>")
        sys.exit(1)
    parse_claim(sys.argv[1])
