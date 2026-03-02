# Coding Standards (SSOT)

Bu doküman agent'ların ve geliştiricilerin uyması gereken kod yazma standartlarını tanımlar.

## Zorunlu Import'lar

Aşağıdaki fonksiyonlar için `src/shared/utils.py` kullanılmalıdır.
Başka dosyalarda yeniden tanımlamak **YASAKTIR**.

| İhtiyaç | Import |
|---|---|
| JSON okuma | `from src.shared.utils import load_json` |
| JSON okuma (hata toleranslı) | `from src.shared.utils import load_json_or_default` |
| JSON yazma (atomic) | `from src.shared.utils import write_json_atomic` |
| Dosya yazma (atomic text) | `from src.shared.utils import write_text_atomic` |
| Dosya yazma (atomic bytes) | `from src.shared.utils import write_bytes_atomic` |
| ISO8601 zaman üretme | `from src.shared.utils import now_iso8601` |
| ISO8601 parse etme | `from src.shared.utils import parse_iso8601` |
| SHA256 hash (text) | `from src.shared.utils import sha256_text` |
| SHA256 hash (file) | `from src.shared.utils import sha256_file` |
| SHA256 kısa hash | `from src.shared.utils import sha256_short` |
| Env variable boolean | `from src.shared.utils import env_true` |
| Env variable string | `from src.shared.utils import env_str` |

## YASAK Pattern'ler

Aşağıdaki tanımlamalar yeni dosyalarda **YASAKTIR** — CI gate reddeder:

```python
# YASAK — bunları dosya içinde tanımlama
def _load_json(path):     # ❌ from src.shared.utils import load_json
def _now_iso():            # ❌ from src.shared.utils import now_iso8601
def _now_iso8601():        # ❌ from src.shared.utils import now_iso8601
def _atomic_write_text():  # ❌ from src.shared.utils import write_text_atomic
def _atomic_write():       # ❌ from src.shared.utils import write_text_atomic
def _sha256_file():        # ❌ from src.shared.utils import sha256_file
def _parse_iso8601():      # ❌ from src.shared.utils import parse_iso8601
```

## Yeni Dosya Yazarken Checklist

1. Önce `src/shared/utils.py` içindeki fonksiyonları kontrol et
2. İhtiyacın olan utility varsa import et, **yeniden yazma**
3. Yeni bir genel utility gerekiyorsa `src/shared/utils.py`'ye ekle
4. Dosya-spesifik helper'lar `_` prefix ile yazılabilir (ama shared olanlar yasak)

## Genel Kurallar

- JSON dosyalar: `write_json_atomic()` ile yaz (tmp → replace pattern)
- Zaman: `now_iso8601()` kullan, `datetime.now()` doğrudan çağırma
- Hash: `sha256_text()` veya `sha256_file()` kullan
- Environment: `env_true()` / `env_str()` kullan
- Dosya boyutu: script_budget limitlerine uy (soft: 1200 satır, hard: 2000 satır)
