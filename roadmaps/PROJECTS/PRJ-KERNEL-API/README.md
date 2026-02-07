# PRJ-KERNEL-API (v0.1)

## Amaç
Codex UI olmadan, program-led API ile ops/gate/runner akışını çağırmak.

## Kapsam (katmanlara göre)
- L0 CORE: ops/gates/runner (mevcut). Bu projede core_lock açılmaz.
- L2 WORKSPACE: run outputs/evidence/reports.
- L3 EXTERNAL: müşteri repo (opsiyonel).

## Non-goals
- Core değişikliği yok.
- Core unlock yok.
- Runtime implementasyon yok (doküman ve plan-only).

## Tek kapı (program-led)
- /status => project-status + system-status (+ doc-nav-check summary)
- /run/finish => roadmap-finish (bounded)
- /run/follow => roadmap-follow (max-steps=1)
- /pause, /resume
- /doc-nav => doc-nav-check (summary default; strict ayrı rapor)
Not: Summary varsayılan; strict ayrı kanıt üretir ve cockpit'i etkilemez.
Adapter entrypoint: src.prj_kernel_api.adapter:handle_request (program-led).

## Çıktılar (taslak)
- API yüzeyi (contract.v1.md)
- Kernel orchestration entrypoint yaklaşımı (spec.v1.md)
- İç çağrı haritası + hata kodları (acceptance.v1.md referanslı)

## Kanıt (beklenen)
- AUTOPILOT CHAT + JSON tail
- Evidence path listesi (program-led)
- Cockpit snapshot pointer

## Core immutability
Bu proje çekirdeği değiştirmez. Çekirdeğe dokunmak ayrı, explicit “core unlock” projesidir.

## Mevcut durum notu
- summary report: .cache/ws_customer_default/.cache/reports/doc_graph_report.v1.json
- strict report: .cache/ws_customer_default/.cache/reports/doc_graph_report.strict.v1.json
- strict_isolated_from_cockpit=true
