# Roadmap Runner SSOT Format (v0.3)

Bu doküman, `roadmaps/SSOT/roadmap.v1.json` için kullanılan **minimal ve kilitli** formatı açıklar.

## Amaç
- Yol haritasını “doküman” değil, **Roadmap Runner tarafından uygulanabilir SSOT** yapmak.
- Deterministik plan üretmek (`roadmap-plan`) ve fail-closed şekilde uygulamak (`roadmap-apply`).
- “Living roadmap” güncellemelerini **Change Proposal** mekanizmasıyla SSOT’a geri beslemek.
- Core ürün ile Workspace (tenant/private) ayrımını **workspace root** ile netleştirmek.

## Dosya konumu
- SSOT roadmap: `roadmaps/SSOT/roadmap.v1.json`
- Şema: `schemas/roadmap.schema.json`
- Change Proposal şeması: `schemas/roadmap-change.schema.json`

## Top-level alanlar
```json
{
  "roadmap_id": "RM-SSOT-001",
  "version": "v1",
  "iso_core_required": false,
  "milestones": [ ... ]
}
```

- `roadmap_id`: kısa, stabil ID (örn. `RM-SSOT-001`)
- `version`: schema/format versiyonu (örn. `v1`)
- `iso_core_required` (opsiyonel): `true` ise plan başına otomatik ISO core preflight step eklenir (v0.2’de varsayılan `false`)
- `milestones`: sıralı milestone listesi (SSOT sırası budur)

## Milestone ID konvansiyonu (dotted ids)
- `M0`, `M1`, `M2` gibi base milestone’lar.
- `M2.5`, `M3.5`, `M6.5` gibi **ara milestone**’lar (dotted id).
- ID’ler string’dir; sıra `milestones[]` dizisi ile belirlenir (sort ile değil).

## Milestone alanları
```json
{
  "id": "M2",
  "title": "Tenant Decision Bundle SSOT v0.1 + Consistency Gate",
  "notes": ["(opsiyonel) kısa notlar"],
  "constraints": {
    "forbidden_paths": [".env", "evidence/", ".cache/secrets"],
    "max_files_changed": 50,
    "max_diff_lines": 2000
  },
  "steps": [ ... ],
  "gates": [ ... ],
  "dod": ["..."]
}
```

- `steps`: milestone deliverables (dosya ekleme/patch vb.)
- `gates`: milestone sonrası koşulacak gate adımları (v0.2 readonly dry-run allowlist ile)
- `dod`: “Definition of Done” maddeleri (insan okur, CI raporlar)

Not: Legacy roadmap’larda `deliverables` alanı `steps` yerine kullanılabilir (v0.2 geriye uyumlu).

## Step templates (v0.3)
Desteklenen step tipleri (template `type`):
- `note` (no-op; SSOT completeness)
- `create_file`
- `ensure_dir`
- `workspace_root_guard`
- `write_file_allowlist`
- `patch_file`
- `create_json_from_template`
- `add_schema_file`
- `add_ci_gate_script`
- `patch_policy_report_inject`
- `change_proposal_apply`
- `incubator_sanitize_scan`
- `run_cmd`
- `assert_paths_exist`
- `iso_core_check`

Detaylar için: `schemas/roadmap.schema.json` ve `src/roadmap/step_templates.py`.

## Milestone seçerek çalışma
- Plan:
  - `python -m src.ops.manage roadmap-plan --roadmap roadmaps/SSOT/roadmap.v1.json --milestone M2 --out .cache/roadmap_plan.json`
- Dry-run (simulate):
  - `python -m src.ops.manage roadmap-apply --roadmap roadmaps/SSOT/roadmap.v1.json --milestone M2 --dry-run true --dry-run-mode simulate`
- Dry-run (readonly gates):
  - `python -m src.ops.manage roadmap-apply --roadmap roadmaps/SSOT/roadmap.v1.json --milestone M2 --dry-run true --dry-run-mode readonly`

## Core vs Workspace boundary (paths)
Roadmap Runner iki ayrı “root” kavramını netleştirir:
- **Core repo root**: ürün kodu + schema/policy/gates + roadmap runner’ın kendisi.
- **Workspace root**: tenant/customer/private SSOT (tenant bundles, packs, formats, incubator vb.).

`roadmap-apply` / `roadmap-plan` komutları `--workspace-root <path>` alabilir:
- Tüm roadmap step `path` alanları **workspace-root’a göre** resolve edilir.
- Workspace-root dışına çıkma denemesi fail-closed olur (`WORKSPACE_ROOT_VIOLATION`).
- Roadmap evidence her zaman core repo altında tutulur: `evidence/roadmap/<run_id>/...`

## Living Roadmap Updates via Change Proposals
Change proposal’lar SSOT roadmap’i kontrollü şekilde güncellemek için kullanılır.

- Konum: `roadmaps/SSOT/changes/` (git SSOT)
- Şema: `schemas/roadmap-change.schema.json`

Örnek ops akışı:
```bash
# Yeni change taslağı üret
python -m src.ops.manage roadmap-change-new --type modify --milestone M2 --out <CHG_PATH>

# Apply + gate koş (fail-closed)
python -m src.ops.manage roadmap-change-apply --change <CHG_PATH>
```

Not: `<CHG_PATH>` değeri `roadmaps/SSOT/changes/` altında olmalıdır (ör: `CHG-YYYYMMDD-001.json`).

Kural: Change apply sırasında en azından schema validate + smoke (veya readonly gate set) çalışır; başarısızsa change uygulanmış sayılmaz.

## Readonly dry-run gate allowlist (v0.2)
Readonly modda `run_cmd` sadece şu komutları çalıştırır (diğerleri fail-closed):
- `python ci/validate_schemas.py`
- `python smoke_test.py`
- `python -m src.ops.manage policy-check --source fixtures`

Readonly modda her `run_cmd` sonrası `git status --porcelain` kontrol edilir; repo kirlenirse run FAIL olur.
