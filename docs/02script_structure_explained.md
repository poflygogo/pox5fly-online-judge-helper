# 為什麼我需要遵循特定的程式碼結構？

在使用 `pox5fly_oj_helper` 時，您可能會疑惑為什麼不能直接寫像一般的 Python 腳本，而必須將邏輯包裝在函式中並使用 `if __name__ == "__main__":`。

這份文檔將解釋這個設計背後的原理。

## 核心原因：多行程 (Multiprocessing) 與 IO 攔截

本模組的核心機制是：當您執行測試時，它會為每一個測試案例啟動一個**獨立的子行程 (Subprocess)** 來重新執行您的腳本。這能確保：

1. **環境隔離**：某個測資產生的全域變數汙染不會影響下一個測資。
2. **IO 重導向**：我們可以攔截標準輸入/輸出 (stdin/stdout) 進行比對。

為了達成這個機制，我們必須明確區分「主控端邏輯」與「解題邏輯」。

### 如果不遵守結構會發生什麼事？

假設您寫成這樣（錯誤示範）：

```python
# 錯誤示範：沒有封裝邏輯
import sys
from pox5fly_oj_helper import OnlineJudgeTester

# 這裡的程式碼會在「主行程」執行一次
# 並且在每一個「子行程」啟動時"再"被執行一次！
print(f"Start processing...")  # <--- 這行會被執行 N+1 次

line = sys.stdin.read()
print(line)

# 初始化測試器
tester = OnlineJudgeTester(__file__)
tester.run_tests(sol_func=None)
```

當測試器嘗試啟動子行程來跑第一筆測資時，它會重新 import 或執行這份檔案。這會導致以下後果：

1. **輸出汙染 (Output Pollution)**：
    `print(f"Start processing...")` 會在子行程啟動時立即執行。這行文字會被測試器捕捉到，並誤判為您解題輸出的一部分，導致比對失敗 (Wrong Answer)。

2. **效能浪費**：
    所有位於 Global scope 的程式碼都會被重複執行。如果這裡包含耗時的初始計算，會嚴重拖慢測試速度。

3. **邏輯混亂**：
    子行程本應只專注於處理當前的測資輸入，但全域程式碼會導致它尚未準備好就開始搶資源或輸出。

## 正確結構的運作方式

為了避免上述問題，我們採用以下結構：

```python
# v1-1.py
import sys
from pox5fly_oj_helper import OnlineJudgeTester

# 1. 定義解題主函式：就像把解題邏輯「關」起來
def solve():
    # 這裡的程式碼「只有」在被明確呼叫時才會執行
    pass

# 2. 測試進入點：只有當這裡是「主程式」時才執行
if __name__ == "__main__":
    # 這段代碼只會在您手動執行 python v1-1.py 時跑一次
    # 子行程 import 這份檔案時，不會執行這段
    tester = OnlineJudgeTester(__file__)
    
    # 告訴測試器：「當你啟動子行程時，請呼叫 solve() 這個函式」
    tester.run_tests(sol_func=solve)
```

### 流程解析

1. **使用者執行 `python v1-1.py`**
    - 進入 `if __name__ == "__main__":` 區塊。
    - 初始化 `tester`。
    - 呼叫 `tester.run_tests(sol_func=solve)`。

2. **`run_tests` 開始工作**
    - 準備測資。
    - **啟動子行程** (帶有特殊環境變數 `OJ_CHILD_PROCESS=1`)。

3. **子行程啟動**
    - Python 載入 `v1-1.py`。
    - 忽略 `if __name__ == "__main__":` 區塊 (因為它是被作為模組載入或子行程執行)。
    - 偵測到環境變數 `OJ_CHILD_PROCESS=1` (由模組內部機制處理)。
    - **精準呼叫** `solve()` 函式。
    - 執行完畢，乾淨退出。

### 總結

- **`solve()`**：是給**子行程**用的 (負責實際解題)。
- **`if __name__ ...`**：是給**主行程**用的 (負責發號施令)。

這樣的職責分離確保了測試環境的穩定、乾淨與高效。
