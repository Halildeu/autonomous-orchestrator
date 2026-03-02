# PRJ-SEARCH

PRJ-SEARCH, Cockpit arama motorunu adapter kontrati ile yonetmek icin ayrilan extension iskeletidir.

## Faz-1 Kapsam
- `search_adapter_contract.v1` tanimi
- `/api/search/capabilities` endpointi
- Cockpit Search sekmesinde adapter kontrati gorunumu

## Faz-2 Kapsam
- `extensions/PRJ-SEARCH/search_adapter.py` aktif backend kaynagi
- `extensions/PRJ-UI-COCKPIT-LITE/keyword_search.py` geriye uyumlu shim
- Shim ile adapter kontrati uyumlulugu testi
- Gercek ops kapisi: `search-check` (JSON + MD rapor uretir)

## Sonraki Faz
- Server importunun shim yerine dogrudan PRJ-SEARCH adapterina alinmasi
- Ops tek kapida `search-check` komutu ve raporlama
- Adapter seviyesinde policy/gate baglantisi
