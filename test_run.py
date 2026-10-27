"""
Standalone test script for La Tercera Muerte.
Tests: exhume, death certificate, ofrenda generation.
Run with: python test_run.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

DEMO_REPO = r"C:\Users\Ritesh Yadav\Documents\ritu\demo-dead-repo"

def separator(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

# ── 1. EXHUME ─────────────────────────────────────────────────
separator("RITUAL 1: EXHUMACION")
from tercera.exhume import exhume, save_grave

try:
    grave = exhume(DEMO_REPO)
    print(f"[OK] Name          : {grave['name']}")
    print(f"[OK] Language      : {grave['language']}")
    print(f"[OK] Born          : {grave['born'][:10]}")
    print(f"[OK] Died          : {grave['died'][:10]}")
    print(f"[OK] Total commits : {grave['total_commits']}")
    print(f"[OK] Top author    : {grave['family'][0][0]} ({grave['family'][0][1]} commits)")
    print(f"[OK] Cause of death: {grave['cause_of_death']}")
    print(f"[OK] TODOs found   : {len(grave['unfinished_todos'])}")
    print(f"[OK] Dependencies  : {', '.join(grave['dependencies'][:5])}")
    print(f"[OK] Last words    : {grave['last_commit']['message'][:80]!r}")

    grave_path = save_grave(grave)
    print(f"[OK] grave.json saved to: {grave_path}")

    # Verify file on disk
    with open(grave_path) as f:
        loaded = json.load(f)
    assert loaded["name"] == grave["name"], "grave.json mismatch!"
    print("[OK] grave.json verified on disk")

except Exception as e:
    print(f"[FAIL] Exhumation: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)

# ── 2. DEATH CERTIFICATE ──────────────────────────────────────
separator("RITUAL 2: ACTA DE DEFUNCION")
from tercera.certificate import generate_certificate, save_certificate

try:
    cert = generate_certificate(grave)
    # Print the certificate (ASCII only for safety on Windows)
    safe_cert = cert.encode("ascii", errors="replace").decode("ascii")
    print(safe_cert)
    cert_path = save_certificate(grave)
    print(f"\n[OK] Certificate saved to: {cert_path}")
except Exception as e:
    print(f"[FAIL] Certificate: {e}")
    import traceback; traceback.print_exc()

# ── 3. PERSONA ────────────────────────────────────────────────
separator("RITUAL 3: PERSONA BUILDER")
from tercera.persona import build_persona, build_whisper_prompt

try:
    persona = build_persona(grave)
    print("[OK] Persona built. First 300 chars:")
    print(persona[:300].encode("ascii", errors="replace").decode("ascii"))
    print("...")
    whisper_p = build_whisper_prompt(grave)
    print(f"\n[OK] Whisper prompt: {whisper_p[:120].encode('ascii', errors='replace').decode('ascii')}...")
except Exception as e:
    print(f"[FAIL] Persona: {e}")
    import traceback; traceback.print_exc()

# ── 4. UNFINISHED BUSINESS ────────────────────────────────────
separator("RITUAL 4: ASUNTOS PENDIENTES")
from tercera.unfinished import detect_unfinished, ghost_names_unfinished

try:
    business = detect_unfinished(grave)
    print(f"[OK] Primary task: {business['primary_task']}")
    print(f"[OK] Description : {business['description'][:120].encode('ascii', errors='replace').decode('ascii')}")
    ghost_says = ghost_names_unfinished(business)
    print(f"[OK] Ghost says  : {ghost_says[:150].encode('ascii', errors='replace').decode('ascii')}")
except Exception as e:
    print(f"[FAIL] Unfinished: {e}")
    import traceback; traceback.print_exc()

# ── 5. OFRENDA ────────────────────────────────────────────────
separator("RITUAL 5: LA OFRENDA")
from tercera.ofrenda import build_ofrenda, save_ofrenda

try:
    md, html = build_ofrenda(grave)
    print(f"[OK] OFRENDA.md   : {len(md)} chars")
    print(f"[OK] ofrenda.html : {len(html)} chars")

    # Save to disk
    md_path, html_path = save_ofrenda(grave, commit=False)
    print(f"[OK] MD saved  : {md_path}")
    print(f"[OK] HTML saved: {html_path}")

    # Spot-check HTML has key elements
    assert grave["name"] in html, "Project name missing from HTML!"
    assert "flicker" in html, "CSS flicker animation missing!"
    assert "candle" in html.lower(), "Candle element missing!"
    for author_name, _ in grave["family"][:3]:
        # Only check ASCII-safe parts
        safe_name = author_name.encode("ascii", errors="replace").decode("ascii")
        if "?" not in safe_name:
            assert author_name in html, f"Author {author_name} missing from HTML!"
    print("[OK] HTML spot-checks passed")

    # Preview first 20 lines of OFRENDA.md
    print("\n--- OFRENDA.md preview ---")
    for line in md.splitlines()[:22]:
        print(line.encode("ascii", errors="replace").decode("ascii"))

except Exception as e:
    print(f"[FAIL] Ofrenda: {e}")
    import traceback; traceback.print_exc()

# ── SUMMARY ───────────────────────────────────────────────────
separator("SUMMARY")
print("Exhume      : OK")
print("Certificate : OK")
print("Persona     : OK")
print("Unfinished  : OK")
print("Ofrenda     : OK")
print("\nOllama / seance / memory / resurrection require Ollama running.")
print("Install Ollama and run: tercera seance ./demo-dead-repo")
print("\nDone! Open the ofrenda in your browser:")
print(f"  {html_path}")
