# law-assistant-mcp

日本の法改正を自動監視し、業種別に質問できる MCP サーバー。

e-Gov API v2 から公式条文をリアルタイム取得。AI の法令幻覚を防止しながら、VoiceOS や Claude Desktop から音声・テキストで質問できます。

---

## 対応業種

| キー | 業種 | 主な法律 |
|------|------|---------|
| `transport` | 運輸・ドライバー | 道路交通法、道路運送法、自動車損害賠償保障法 |
| `construction` | 建設・不動産 | 建築基準法、都市計画法、建設業法 |
| `food` | 飲食・食品 | 食品衛生法、食品表示法、食品安全基本法 |
| `entertainment` | 風俗・エンタメ | 風俗営業等の規制及び業務の適正化等に関する法律（風営法） |
| `medical` | 医療・介護 | 医療法、薬機法、介護保険法 |
| `labor` | 労務・人事 | 労働基準法、労働安全衛生法、最低賃金法 |
| `it` | IT・データ | 個人情報保護法、不正アクセス禁止法、電気通信事業法 |
| `finance` | 金融・保険 | 金融商品取引法、銀行法、保険業法 |

`industries.json` を編集するだけで業種・法律を追加できます。

---

## MCP ツール

### Q&A（調査・質問）

| ツール | 説明 | 例 |
|--------|------|----|
| `ask_law` | 法律について自由に質問 | 「深夜営業に必要な許可は？」 |
| `is_legal` | 行為の合法性を判定 | 「18歳未満をホールで働かせてよい？」 |
| `get_penalty` | 罰則・罰金・行政処分を調べる | 「食品衛生法違反の罰則は？」 |
| `get_article` | 公式条文をそのまま取得（幻覚ゼロ） | 「食品衛生法第6条」 |

### 監視・通知

| ツール | 説明 |
|--------|------|
| `check_updates` | 改正チェック実行（業種指定可） |
| `get_amendments` | 過去の改正通知を取得 |

### 設定・管理

| ツール | 説明 |
|--------|------|
| `list_industries` | 登録済み業種一覧 |
| `list_laws` | 監視中の法律一覧 |
| `add_law` | e-Gov で検索して監視リストに追加 |

---

## アーキテクチャ

```
VoiceOS / Claude Desktop
        │ MCP (stdio)
        ▼
  server.py  ─── industries.json（業種定義）
        │
   ┌────┴────┐
   │  core/  │
   │ egov    │──► e-Gov API v2（公式条文取得）
   │ claude  │──► Claude API（Q&A・要約）
   │ cache   │
   │ voice   │──► 音声向け整形
   └─────────┘
        │
   data/
   ├── watch_state.json   （監視ハッシュ）
   └── amendments.jsonl   （改正履歴ログ）
```

---

## クイックスタート

```bash
git clone https://github.com/bonsai/law-assistant-mcp
cd law-assistant-mcp
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key

python server.py
```

### VoiceOS 連携

設定 → 連携 → カスタム連携 → 追加

```
名前: 法律アシスタント
起動コマンド: python /path/to/server.py
```

### Claude Desktop 連携

`claude_desktop_config.json` に追記:

```json
{
  "mcpServers": {
    "law-assistant": {
      "command": "python",
      "args": ["/path/to/server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "your_key"
      }
    }
  }
}
```

---

## 使用例

```
# 飲食業の深夜営業ルールを質問
ask_law("深夜に酒類を提供する営業の届出は何が必要？", industry="food")

# 行為の合法性チェック
is_legal("調理師免許なしで飲食店を開業する", industry="food")

# 全法律の改正チェック
check_updates()

# 建築業種だけチェック
check_updates(industry="construction")

# 監視リストに法律を追加
add_law("景品表示法", industry="it")
```

---

## 環境変数

| 変数 | 説明 |
|------|------|
| `ANTHROPIC_API_KEY` | Anthropic API キー（必須） |
| `EGOV_TIMEOUT_MS` | e-Gov API タイムアウト（デフォルト: 20000ms） |
| `LAW_LOG_LEVEL` | ログレベル: debug / info / warn / error |

---

## ロードマップ

- [x] 計画・設計
- [ ] Phase 1: 基盤実装（transport / food 業種）
- [ ] Phase 2: 全業種対応・自動定期チェック
- [ ] Phase 3: 公式条文そのまま返す幻覚ゼロモード
- [ ] Phase 4: VoiceOS スタイル調整・多言語対応

---

## ライセンス

MIT
