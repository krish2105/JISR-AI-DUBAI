"""
make_voice_notes.py — Create the SYNTHETIC demo voice notes with the operating system's text-to-speech (macOS `say`).

Why this file exists:
    The demo shows an Arabic voice note turning into a quote. We never use a real person's voice: the audio is
    synthesised from a written script, and the script is stored next to it in replay/voice/manifest.json, keyed by
    the audio's SHA-256. The fake / offline speech-to-text returns that script; with a real STT model (dev or prod
    profile) the same audio is transcribed for real, which also tests the STT.

Usage (macOS):  python3 scripts/make_voice_notes.py
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "replay" / "voice"
NOTES = {
    "ar_voice_lamps": ("Majed", "ar", "مرحبا، معكم شركة الواحة للهدايا في دبي. نحتاج ثلاثمئة مصباح نحاسي "
                                     "ومئتي مفرش طاولة قطني، الشحن إلى جبل علي، قبل نهاية الشهر. أرسلوا لنا السعر من فضلكم."),
    "en_voice_shawls": ("Aman", "en", "Hello, this is Marina Home Decor in Dubai. We need two hundred pashmina shawls "
                                      "and one hundred wooden jewellery boxes, CIF Jebel Ali, before the fifteenth of "
                                      "December. Please send your best price."),
}


def main() -> int:
    """Synthesise each note to M4A (AAC), record its hash and script."""
    if sys.platform != "darwin":
        print("This helper uses macOS `say`; the committed files can be used as they are.")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, (voice, lang, script) in NOTES.items():
        aiff, m4a = OUT / f"{name}.aiff", OUT / f"{name}.m4a"
        subprocess.run(["say", "-v", voice, "-o", str(aiff), script], check=True)
        subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", str(aiff), str(m4a)], check=True)
        aiff.unlink()
        sha = hashlib.sha256(m4a.read_bytes()).hexdigest()
        manifest[sha] = {"file": m4a.name, "voice": voice, "language": lang, "transcript": script,
                         "mime_type": "audio/mp4", "synthetic": True}
        print(f"{m4a.name}: {m4a.stat().st_size:,} bytes, sha256 {sha[:12]}")
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
