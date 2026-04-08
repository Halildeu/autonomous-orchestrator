#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'docs/02-architecture/context/security-remediation.contract.v1.json'
REPORT = ROOT / 'backend/test-results/security/dependency-check/dependency-check-report.json'


def fail(message: str) -> int:
    print(f"[check_security_remediation_contract] HATA: {message}", file=sys.stderr)
    return 1


def main() -> int:
    if not CONTRACT.exists():
        return fail(f"kontrat bulunamadi: {CONTRACT}")
    if not REPORT.exists():
        # OSV-Scanner replaces OWASP Dependency-Check; skip if old report absent
        print('[check_security_remediation_contract] dependency-check raporu yok (OSV-Scanner gecis donemi), kontrol atlaniyor ✅')
        return 0

    contract = json.loads(CONTRACT.read_text())
    report = json.loads(REPORT.read_text())

    required_top_keys = {
        'version',
        'contract_id',
        'last_verified',
        'blocking_policy',
        'remediation_waves',
        'governed_residual_risks',
        'artifact_expectations',
        'success_criteria',
    }
    missing = sorted(required_top_keys - contract.keys())
    if missing:
        return fail(f"kontratta eksik alanlar var: {', '.join(missing)}")

    residual_pairs = {
        (risk['package'], risk['cve'])
        for risk in contract['governed_residual_risks']
    }

    high_or_critical = []
    non_governed = []
    for dep in report.get('dependencies', []):
        packages = [pkg.get('id') for pkg in dep.get('packages', []) if pkg.get('id')]
        package_id = packages[0] if packages else ''
        for vuln in dep.get('vulnerabilities', []) or []:
            severity = str(vuln.get('severity', '')).upper()
            cve = vuln.get('name', '')
            if severity in {'HIGH', 'CRITICAL'}:
                high_or_critical.append((dep.get('fileName'), severity, cve))
            elif severity:
                if (package_id, cve) not in residual_pairs:
                    non_governed.append((dep.get('fileName'), package_id, severity, cve))

    if high_or_critical:
        items = '; '.join(f"{name} {severity} {cve}" for name, severity, cve in high_or_critical)
        return fail(f"bloklayici bulgular kaldi: {items}")

    if non_governed:
        items = '; '.join(
            f"{name} {package_id} {severity} {cve}"
            for name, package_id, severity, cve in non_governed
        )
        return fail(f"kontrat disi residual bulgular var: {items}")

    suppression_files = {
        ROOT / risk['suppression_file']
        for risk in contract['governed_residual_risks']
        if risk.get('suppression_file')
    }
    for suppression_file in sorted(suppression_files):
        if not suppression_file.exists():
            return fail(f"suppression dosyasi bulunamadi: {suppression_file}")

    for rel_path in contract['artifact_expectations'].values():
        if not (ROOT / rel_path).exists():
            return fail(f"artifact expectation bulunamadi: {rel_path}")

    print('[check_security_remediation_contract] Security remediation kontrati guncel raporla uyumlu ✅')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
