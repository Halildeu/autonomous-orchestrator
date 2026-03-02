# Proje Yönetimi 3-Faz Runner (v10)

## 1) Aşama haritası

- `--phase 1`: `extension-registry`, `extension-help`
- `--phase 2`: `doc-nav-check`, `work-intake-check` (+ phase 1)
- `--phase 3`: `policy-check`, `script-budget`, `smoke` (+ phase 2)
- Tüm fazlarda ek olarak: `system-status`

Kritik/WARN filtreleri her çalıştırmada `extension_issue_summary` altında üretilir.

## 2) Tek satır başlatıcı (onboarding + phase all + kritik filtre)

```bash
./scripts/onboard_managed_repos.sh "/Users/halilkocoglu/Documents/autonomous-orchestrator,/Users/halilkocoglu/Documents/dev" ${WORKSPACE_ROOT}/.cache/ws_customer_default_multi2
python3 ./scripts/run_project_management_3phases.py \
  --orchestrator-root /Users/halilkocoglu/Documents/autonomous-orchestrator \
  --managed-repo-root /Users/halilkocoglu/Documents/autonomous-orchestrator \
  --managed-repo-root /Users/halilkocoglu/Documents/dev \
  --workspace-root-prefix ${WORKSPACE_ROOT}/.cache/ws_customer_default_multi2 \
  --phase all \
  --critical-only false \
  --print-evidence-map false \
  --stop-on-fail false \
  --bootstrap-workspace true
```

## 3) Tek repo test (ilk validasyon)

```bash
./scripts/onboard_managed_repos.sh /Users/halilkocoglu/Documents/autonomous-orchestrator
python3 ./scripts/run_project_management_3phases.py \
  --orchestrator-root /Users/halilkocoglu/Documents/autonomous-orchestrator \
  --managed-repo-root /Users/halilkocoglu/Documents/autonomous-orchestrator \
  --workspace-root-prefix ${WORKSPACE_ROOT}/.cache/ws_customer_default_multi2 \
  --phase all \
  --critical-only true \
  --print-evidence-map false \
  --bootstrap-workspace true
```

## 4) Uzun liste onboarding örneği (`repos.txt`)

```bash
./scripts/onboard_managed_repos.sh --input-file /Users/halilkocoglu/Documents/dev/repos.txt
python3 ./scripts/run_project_management_3phases.py \
  --orchestrator-root /Users/halilkocoglu/Documents/autonomous-orchestrator \
  --manifest-path ${WORKSPACE_ROOT}/.cache/ws_customer_default_multi2/.cache/managed_repos.v1.json \
  --workspace-root-prefix ${WORKSPACE_ROOT}/.cache/ws_customer_default_multi2 \
  --phase all \
  --critical-only true \
  --print-evidence-map false \
  --bootstrap-workspace true
```

## 5) Çıktıdan kritik/önemsiz filtrelenmiş özet

Kritik ve WARN seviyeli extension hatalarını hızlı görmek için:

```bash
python3 ./scripts/run_project_management_3phases.py ... \
  | jq -r '.extension_issue_summary.items[] | "\(.repo_slug) \(.command) \(.status)"'
```

Tek satır risk skoru için:

```bash
python3 ./scripts/run_project_management_3phases.py ... \
  | jq -r '.summary.risk_line'
```
