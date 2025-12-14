# Online Judge Tester

這是一個專為 Python 開發者設計的輕量級 Online Judge (OJ) 本地測試模組。它能協助您在本機環境模擬 OJ 的評測流程，自動執行測資並比對輸出結果。

## 主要功能

- **自動測資配對**：自動尋找並配對資料夾中的 `.in` 與 `.out` 檔案。
- **行程隔離**：每個測試案例都在獨立的子行程中執行，防止全域變數汙染。
- **超時檢測 (TLE)**：支援設定執行時間限制，並能捕獲超時前的輸出。
- **執行期錯誤 (RE) 捕獲**：自動過濾框架內部的堆疊訊息，只顯示您的程式碼錯誤位置。
- **靈活的比對**：支援寬鬆比對 (忽略空白/空行) 與嚴格比對模式。

## 安裝方式 (Installation)

### 前置需求 (Prerequisites)

- Python 3.8 或以上版本

### 安裝步驟

本專案採用標準 Python 套件結構。請將專案 Clone 下來後，在專案根目錄執行以下指令進行安裝（建議使用 Editable 模式以便隨時更新）：

```bash
# 1. 下載專案
git clone https://github.com/poflygogo/pox5fly-online-judge-helper

# 2. 進入專案目錄
cd pox5fly-online-judge-helper

# 3. 安裝 (使用 Editable 模式)
pip install -e .
```

### 如何更新 (Updating)

由於採用 Editable 模式安裝，您只需要進入該目錄拉取最新程式碼即可：

```bash
# 假設您尚未在專案目錄中
cd pox5fly-online-judge-helper

# 拉取最新程式碼，功能即刻生效
git pull
```

## 快速開始 (Quick Start)

### 1. 準備您的解題腳本

為了確保模組能正確執行，您的解題腳本必須遵循以下結構：

1. 將解題邏輯封裝在一個主函式中 (例如 `solve()` 或 `main()`)。
2. 在 `if __name__ == "__main__":` 區塊中初始化測試器並呼叫 `run_tests`。

```python
from pox5fly_oj_helper import OnlineJudgeTester

# 需要一個主函式(入口函式)，名稱不拘，只要它是你的入口函式即可
def main():
    try:
        content = input()
        print(f"Hello, {content}!")
    except EOFError:
        pass

# 2. 測試進入點
if __name__ == "__main__":
    # 初始化 (傳入當前檔案路徑，通常情況下使用 __file__ 即可)
    tester = OnlineJudgeTester(__file__)
    
    # 執行測試 (必須在 sol_func 傳入主函式)
    tester.run_tests(sol_func=main)
```

### 2. 準備測資

預設情況下，模組會在腳本同層目錄下的 `test_case` 資料夾尋找測資。

目錄結構範例：

```text
project/
├── your_code.py
└── test_case/
    ├── 01.in
    ├── 01.out
    ├── 02.in
    └── 02.out
```

> **注意**：`test_case` 資料夾必須與您的 Python 腳本位於同一層級。

測資檔名有格式要求，應為 `編號` + `類型` 的結構

- 編號: 從 0 開始計數，如果是個位數，應補上前綴 0，如 `00`, `01`, ... `09`, `10`, `11`, ...
- 類型: 分兩種檔案類型: 輸入檔(`.in`) 和輸出檔(`.out`)

---

## API 參數與進階用法

更多詳細參數說明與進階功能 (如指定測資、嚴格比對模式等)，請參考完整的使用說明書： [./docs/manual.md](./docs/manual.md)

---

## FAQ

### 為什麼測試看似有跑，但實際上沒執行我的程式碼？

這通常是因為您在呼叫 `run_tests()` 時忘記傳入 `sol_func` 參數，或者您傳入的不是函式。請確保寫法如下 `test.run_tests(sol_func=your_main_func)`，這樣與子行程架構才能正確串接。

正確寫法:

```py
test = OnlineJudgeTester(__file__)
test.run_tests(sol_func=your_main_func)
```

錯誤寫法:

```py
test = OnlineJudgeTester(__file__)

# 請勿必要添加入口函式
test.run_tests()

# 請勿添加額外的括號
test.run_tests(sol_func=your_main_func())
```

### 為什麼要強制將解題邏輯寫在函式裡？除了模組需求外有其他好處嗎？

有的，且非常重要！

模組需求當然是其中一個原因，請原諒我的爛 code

**將邏輯封裝在函式中能顯著提升 Python 程式的執行效能**。

這是因為 Python 對於「區域變數 (Local Variables)」與「全域變數 (Global Variables)」的查找機制不同：

- **全域變數**: 存取時需要進行字典 (Dictionary) 查找，指令較慢 (`LOAD_GLOBAL` / `STORE_NAME`)。
- **區域變數**: 在編譯時已確定位置，改用陣列索引方式直接存取，指令極快 (`LOAD_FAST` / `STORE_FAST`)。

在 Online Judge 這種對執行時間錙銖必較的環境下，將主邏輯寫在 `solve()` 或 `main()` 函式中，往往能避免不必要的 **TLE (Time Limit Exceeded)**。
