# Filter Builder — Baştan Yazım Planı

## Context
Mevcut filter-builder (7 dosya) çalışıyor ama UX kötü: görsel hiyerarşi belirsiz, bağımsız combinator toggle'ları kararsız, drag-and-drop yok, clone/lock yok. react-querybuilder'ın Bootstrap demo'sundaki UX referans alınarak tamamen yeniden yazılacak.

**Kaynak repo:** `/Users/halilkocoglu/Documents/dev/web/`
**Hedef dizin:** `packages/design-system/src/advanced/data-grid/filter-builder/`

## Bağımlılık Kurulumu (Ön Adım)

```bash
cd /Users/halilkocoglu/Documents/dev/web/packages/design-system
pnpm add @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities
```

- `lucide-react` root'ta var (^0.554.0), design-system zaten root'tan erişiyor — ek kurulum gerekmez
- `@dnd-kit` seçimi: React 18+ uyumlu, lightweight, tree-sortable desteği var, react-dnd'den daha modern

## Dosya Yapısı (9 dosya)

```
filter-builder/
├── index.ts                  — barrel export
├── types.ts                  — tüm tipler (ayrı dosyada)
├── useFilterBuilder.ts       — state hook (yeniden yazım)
├── filterModelConverter.ts   — AG Grid ↔ tree (güncelleme)
├── FilterBuilderPanel.tsx    — ana drawer (Drawer primitive kullanarak)
├── FilterGroupNode.tsx       — recursive grup + branch lines
├── FilterConditionRow.tsx    — tek kural satırı + tüm aksiyonlar
├── FilterValueEditor.tsx     — tip-bazlı değer editörü
└── FilterCombinatorRow.tsx   — bağımsız AND/OR dropdown (YENİ)
```

## Dosya Bazlı Plan

### 1. `types.ts` (YENİ)
Mevcut useFilterBuilder.ts'den tipleri çıkar + genişlet:

```ts
FilterCondition     — { id, type:'condition', colId, filterType, operator, value, valueTo?, locked }
FilterCombinator    — { id, type:'combinator', logic:'AND'|'OR' }
FilterGroup         — { id, type:'group', not:boolean, children:FilterTreeNode[], locked }
FilterTreeNode      — FilterCondition | FilterCombinator | FilterGroup
FilterType          — 'text' | 'number' | 'date' | 'set'
FilterOperator      — string (operator keys)
```

Yeni alanlar: `locked: boolean` (her node'da), `not: boolean` (grup'ta)

### 2. `useFilterBuilder.ts` (YENİDEN YAZIM)
Mevcut operasyonlar korunur + yeni eklenir:

| Mevcut | Yeni |
|--------|------|
| addCondition | cloneNode(id) — kural/grup deep copy |
| addGroup | toggleLock(id) — locked toggle |
| removeNode | toggleNot(groupId) — NOT toggle |
| updateCondition | moveNodeDnD(activeId, overId, overGroupId) — DnD handler |
| setLogic | — |
| indentNode | — |
| outdentNode | — |
| moveNode | — |

State: `useState<FilterGroup>` (root node)
Max nesting: configurable (default 3)
Import/export: `importTree(tree)`, `exportTree()` → deep clone
Locked node'larda tüm mutasyonlar skip edilir

### 3. `filterModelConverter.ts` (GÜNCELLEME)
Mevcut dönüşüm mantığı büyük oranda korunur, yeni alanlar eklenir:
- `locked` alanı dönüşümde ignore edilir (sadece UI state)
- `not` grubu: AG Grid native desteği yok → tree state'te tutulur, filterModel'e dönüşümde skip
- Operator sabitleri ve Türkçe label'lar korunur
- `treeToFilterModel()` ve `filterModelToTree()` imzaları aynı

### 4. `FilterBuilderPanel.tsx` (YENİDEN YAZIM)
Mevcut Drawer primitive'i kullanır (`packages/design-system/src/primitives/drawer/`):

```
┌─────────────────────────────────────┐
│ [Filter icon] Filtre Oluşturucu  [X]│  ← Drawer header
├─────────────────────────────────────┤
│                                     │
│  <DndContext>                       │  ← @dnd-kit context
│    <FilterGroupNode root={tree} />  │
│  </DndContext>                      │
│                                     │
├─────────────────────────────────────┤
│ X satır eşleşiyor  [Temizle][Uygula]│  ← Footer
└─────────────────────────────────────┘
```

- Drawer: `placement="right"`, `size="lg"` (620px override via className)
- DndContext: `@dnd-kit/core` — collision detection: closestCenter
- State import: `gridApi.__filterBuilderTree` → fallback `gridApi.getFilterModel()`
- Apply: `treeToFilterModel()` → `gridApi.setFilterModel()` → `gridApi.onFilterChanged()`
- FilterBuilderButton: toolbar butonu, aktif filtre sayısı badge

### 5. `FilterGroupNode.tsx` (YENİDEN YAZIM)
react-querybuilder layout'u:

```
┌─ Group Header ─────────────────────────────────┐
│ [Not] [+ Kural] [+ Grup] [Kopyala] [🔒] [🗑]  │
├─────────────────────────────────────────────────┤
│ ┃                                               │
│ ┃── FilterConditionRow (kural 1)                │
│ ┃                                               │
│ ┃── FilterCombinatorRow (AND ▼)                 │
│ ┃                                               │
│ ┃── FilterConditionRow (kural 2)                │
│ ┃                                               │
│ ┃── FilterCombinatorRow (OR ▼)                  │
│ ┃                                               │
│ ┃── [FilterGroupNode] (alt grup — recursive)    │
│ ┃                                               │
└─────────────────────────────────────────────────┘
```

- **Branch lines:** Sol tarafta `border-left` ile dikey çizgi, her çocuk node'dan horizontal connector
- **Depth coloring:** Mevcut 3 renk şeması korunur (blue → violet → amber)
- **Header butonları:** Not toggle (checkbox), + Kural, + Grup, Kopyala (Copy), Kilit (Lock), Sil (Trash2)
- **Recursive:** `<SortableContext>` ile her grup kendi sortable listesi
- Root grup silinemez, kilit/kopyala gösterilmez
- Locked grup: tüm çocuklar disabled, opak görünüm

### 6. `FilterConditionRow.tsx` (YENİDEN YAZIM)
Her kural satırı:

```
[⠿] [↑] [↓]  [Sütun ▼] [Operatör ▼] [Değer input]  [Kopyala] [🔒] [🗑]
 │    │    │                                             │        │     │
 DnD  Shift                                            Clone   Lock  Delete
```

- **DnD handle:** `@dnd-kit/sortable` useSortable hook → GripVertical icon
- **Shift:** ChevronUp / ChevronDown → `moveNode(id, 'up'/'down')`
- **Clone:** Copy icon → `cloneNode(id)`
- **Lock:** Lock/Unlock icon → `toggleLock(id)`, locked ise tüm input'lar disabled
- **Delete:** Trash2 icon → `removeNode(id)`
- **Field selector:** `<select>` filterable sütun listesi
- **Operator:** Tip-bazlı operator listesi (mevcut TEXT/NUMBER/DATE_OPERATORS)
- **Value:** FilterValueEditor component

### 7. `FilterValueEditor.tsx` (GELİŞTİRME)
Mevcut 4 tip desteği korunur + bulk paste geliştirilir:

- **Text:** Input + bulk paste → Tag chip'leri (design-system Tag primitive)
- **Number:** Input veya range (from-to)
- **Date:** Date picker veya range
- **Set:** Checkbox listesi + bulk paste → Tag chip'leri
- **Bulk paste:** Textarea açılır, Excel'den yapıştırılan değerler `,` `;` `\n` `\t` ile split
- **Chip render:** Tag primitive (`closable`, `size="sm"`, `variant="primary"`)
- `locked` prop: true ise tüm input'lar disabled

### 8. `FilterCombinatorRow.tsx` (YENİ)
Bağımsız AND/OR dropdown — her kural arasında:

```
          ┃
    ┃─── [VE ▼] ───┃
          ┃
```

- Basit bir `<select>` veya toggle button: AND ↔ OR
- Birini değiştirmek diğerlerini ETKİLEMEZ (bağımsız)
- Branch line ile bağlantılı görünüm
- `locked` parent ise disabled
- Compact tasarım: tek satır, centered

### 9. `index.ts` (GÜNCELLEME)
Tüm yeni component ve tip exportları:

```ts
export { FilterBuilderPanel, FilterBuilderButton } from './FilterBuilderPanel'
export { useFilterBuilder } from './useFilterBuilder'
export { treeToFilterModel, filterModelToTree } from './filterModelConverter'
export type { FilterGroup, FilterCondition, FilterCombinator, FilterTreeNode, FilterType } from './types'
```

## Entegrasyon Noktası
`EntityGridTemplate.tsx` satır ~510: Mevcut `<FilterBuilderButton gridApi={gridApi} columnDefs={columnDefs} />` — **değişiklik gerekmez**, aynı prop interface korunur.

## Mevcut Bileşenlerin Yeniden Kullanımı
- **Drawer** (`primitives/drawer/Drawer.tsx`): Panel container — `placement="right"`, `size="lg"`
- **Tag** (`primitives/tag/Tag.tsx`): Bulk paste chip'leri — `closable`, `size="sm"`
- **Lucide React**: GripVertical, ChevronUp, ChevronDown, Copy, Lock, Unlock, Trash2, Plus, Filter, X

## AG Grid Kısıtları (ag-grid.md)
- v34.3.1 pinned — `setGridOption()` API kullan
- `enableAdvancedFilter` KULLANMA — floating filter + context menu kapatır
- Sütun başına max 2 condition — 3+ değer `multiSearch` backend parametresine
- SSRM: `gridApi.refreshServerSide({ purge: true })` filter değişikliğinde
- `gridApi.__filterBuilderTree`: custom property ile tree state persist

## Uygulama Sırası
1. `pnpm add @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities`
2. Mevcut 7 dosyayı sil
3. `types.ts` yaz
4. `useFilterBuilder.ts` yaz
5. `filterModelConverter.ts` yaz
6. `FilterCombinatorRow.tsx` yaz
7. `FilterValueEditor.tsx` yaz
8. `FilterConditionRow.tsx` yaz
9. `FilterGroupNode.tsx` yaz
10. `FilterBuilderPanel.tsx` yaz
11. `index.ts` yaz
12. Build kontrol: `pnpm --filter design-system build`

## Doğrulama
- [x] "Kural" tıkla → yeni kural satırı
- [x] "Grup" tıkla → yeni alt grup kutusu
- [x] Her kural arası bağımsız AND/OR dropdown
- [x] Birini VE→VEYA yapınca diğerleri değişmez
- [x] Sürükle-bırak ile sıralama
- [x] Clone butonu kural/grup kopyalar
- [x] Lock butonu düzenlemeyi kilitler
- [x] Bulk paste: Excel'den yapıştır → chip'ler
- [x] Uygula → grid filtrelenir + floating filter senkron
- [x] Kapat → aç → tree state korunur (AND/OR dahil)
- [x] SSRM modunda çalışır
- [x] Build başarılı
