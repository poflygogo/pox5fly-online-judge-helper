# 使用說明書

本文件提供 `pox5fly-online-judge-helper` 模組的詳細使用說明，涵蓋了基本設定、API 細節、進階用法，以及命令列介面的操作方式。

## `OnlineJudgeTester` 類別 API 說明

這是與本模組互動的主要入口。

### 初始化 `__init__`

建立 `OnlineJudgeTester` 物件時，需傳入目標腳本路徑及其他可選的設定參數，以客製化您的測試環境。

```python
from pox5fly_oj_helper import OnlineJudgeTester

tester = OnlineJudgeTester(
    target_script_path=__file__,
    time_limit=3000,
    test_case_path="./custom_tests/",
    max_diffs=5,
    show_missing_output=True
)
```

**參數詳解：**

- `target_script_path: str`
  - **功能**：**必需參數**，用來指定要測試的 Python 腳本檔案路徑。
  - **用法**：在大多數情況下，直接傳入 `__file__` 即可。模組會將此路徑轉換為絕對路徑，以確保在子行程中能正確執行。

- `time_limit: int = 3000`
  - **功能**：設定每筆測資的執行時間限制，單位為毫秒 (ms)。
  - **預設值**：`3000` (3 秒)。
  - **行為**：若程式執行超過此時間，會被強制終止並判定為 `TLE` (Time Limit Exceeded)。

- `compare_output: bool = True`
  - **功能**：控制是否要比對程式輸出與 `.out` 檔的內容。
  - **預設值**：`True`。
  - **進階應用**：若您只想測試程式是否能正常執行而不關心輸出正確性（例如，壓力測試），可以設為 `False`。

- `test_case_path: str | None = None`
  - **功能**：指定存放測資 (`.in`, `.out` 檔案) 的資料夾路徑。
  - **預設值**：若為 `None`，模組會自動尋找 `target_script_path` 腳本同層目錄下的 `test_case` 資料夾。

- `max_diffs: int | None = 10`
  - **功能**：當發生 `WA` (Wrong Answer) 時，設定最多顯示幾行輸出差異。
  - **預設值**：`10`。若設為 `None`，則會顯示所有差異行。

- `show_missing_output: bool = False`
  - **功能**：當找到了 `.in` 檔但找不到對應的 `.out` 檔時，決定是否要顯示程式的實際輸出。
  - **預設值**：`False`。
  - **用途**：在您還沒有標準答案但想先看看程式執行結果時，此選項非常有用。啟用後，狀態會是 `MISSING`，並印出 Raw Output。

### 執行測試 `run_tests()`

此方法是執行測試的主要入口，它會根據設定尋找測資、執行腳本、比對結果，並將報告印到終端機。

```python
# 假設 tester 已被初始化
def main():
    # ... 你的解題邏輯 ...

if __name__ == "__main__":
    tester.run_tests(
        sol_func=main,
        strict_comparison=False,
        repeat=3,
        cases_to_run=[1, 5, "special_case.in"],
        show_raw_output=False
    )
```

**參數詳解：**

- `sol_func: Callable[[], Any]`
  - **功能**：**必需參數**，傳入您的解題主函式。
  - **重要性**：這是模組能夠實現「行程隔離」的關鍵。`run_tests` 內部會啟動一個新的 Python 子行程來執行您的 `sol_func`，從而避免主程式與測試程式間的全域變數互相干擾。若未傳遞此參數，子行程將無法執行您的解題邏輯，導致測試無法進行。

- `strict_comparison: bool = False`
  - **功能**：選擇輸出結果的比對模式。
  - **預設值**：`False` (寬鬆比對)。
    - **寬鬆比對 (False)**：忽略所有比對前，會先將您的輸出和標準答案都進行以下處理：
      1. 按行分割。
      2. 去除每行頭尾的空白字元 (`strip()`)。
      3. **移除所有空行**。
      4. 最後比對處理後的結果。
    - **嚴格比對 (True)**：進行逐字元比對，任何空白、換行符的差異都會導致 `WA`。

- `repeat: int = 1`
  - **功能**：設定每筆測資重複執行的次數。
  - **預設值**：`1`。
  - **用途**：用於測量程式執行時間的穩定性。當 `repeat > 1` 時，時間報告會顯示「平均/最長/最短」時間。若其中任何一次執行失敗 (如 TLE, RE)，將立即停止該測資的後續執行。

- `cases_to_run: list[int | str] | None = None`
  - **功能**：指定只執行特定的幾筆測資，而不是全部執行。
  - **預設值**：`None` (執行所有找到的測資)。
  - **用法**：
    - **整數 (int)**：會進行數值匹配 (自動補零)。例如，`1` 會同時匹配 `1.in` 和 `01.in`。
    - **字串 (str)**：會進行部分字串包含匹配。例如，`"case"` 會匹配 `special_case.in` 和 `case_01.in`。

- `show_raw_output: bool = False`
  - **功能**：是否在每筆測資的報告中，強制顯示程式的原始標準輸出 (stdout)。
  - **預設值**：`False`。
  - **用途**：主要用於偵錯。當您想查看 `AC` 案例的完整輸出，或者想在 `TLE` / `RE` 時看到底印出了什麼內容，此選項非常有用。

## 判斷結果說明

每次測試後，您會看到以下幾種狀態：

- `AC` (Accepted)：恭喜！您的程式輸出與標準答案完全相符。
- `WA` (Wrong Answer)：您的程式輸出與標準答案不符。終端機會顯示詳細的差異報告。
- `TLE` (Time Limit Exceeded)：您的程式執行時間超過了 `time_limit` 設定的上限。
- `RE` (Runtime Error)：您的程式在執行過程中發生錯誤並崩潰。終端機會顯示經過濾的錯誤堆疊訊息，幫助您快速定位到自己程式碼中的問題。
- `MISSING`：測試框架找到了 `.in` 檔，但找不到對應的 `.out` 檔。如果 `show_missing_output` 設為 `True`，此時會印出您的程式輸出。
