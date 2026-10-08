#!/usr/bin/env python3
"""Zet de profielen (godfred/profile.md, elsje/profile.md) in js/profiles.js,
zodat de pagina ze zonder server kan meesturen naar Claude.

Draai opnieuw na elke wijziging aan een profiel:  python3 scripts/sync-profiles.py
"""
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
profiles = {name: (root / name / 'profile.md').read_text(encoding='utf-8') for name in ['godfred', 'elsje']}
out = root / 'js' / 'profiles.js'
out.write_text(
    '// GEGENEREERD door scripts/sync-profiles.py uit godfred/profile.md en elsje/profile.md.\n'
    '// Niet met de hand aanpassen: wijzig het profiel en draai het script opnieuw.\n'
    'window.FC = window.FC || {};\n'
    f'FC.PROFILES = {json.dumps(profiles, ensure_ascii=False, indent=2)};\n',
    encoding='utf-8',
)
print(f'{out.relative_to(root)} bijgewerkt ({", ".join(profiles)})')
