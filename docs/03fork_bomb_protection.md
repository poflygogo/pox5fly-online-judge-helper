# 進階機制：防止無限遞迴 (Fork Bomb 防護)

內部實作了一層保護機制，防止因使用者的錯誤配置導致無限遞迴產生子行程 (Fork Bomb)。

## 遞迴是如何發生的？

想像一下，如果子行程在執行時，不小心又執行到了 `tester.run_tests(...)`，會發生什麼事？

1. **主行程 A** 呼叫 `run_tests`，啟動 **子行程 B**。
2. **子行程 B** 載入腳本，如果不小心再次觸發 `run_tests`，它會啟動 **子行程 C**。
3. **子行程 C** 又啟動 **子行程 D**...

這會導致電腦資源迅速耗盡。雖然標準的 `if __name__ == "__main__":` 可以防止大部分情況，但在某些特殊 import 場景下仍可能有漏網之魚。

## 防護機制實作

為了徹底杜絕此問題，模組在啟動子行程時會設置一個特殊的環境變數 `OJ_CHILD_PROCESS="1"`。

在 `run_tests` 函式的最開頭，有一段這樣的檢查邏輯：

```python
def run_tests(self, sol_func, ...):
    # 0. 檢查並處理子行程執行的情況 (防止遞迴)
    self._handle_child_process(sol_func)
    # ...
```

而 `_handle_child_process` 做了這件事：

```python
def _handle_child_process(self, sol_func):
    # 檢查是否帶有子行程標記
    if os.environ.get("OJ_CHILD_PROCESS") != "1":
        return  # 如果不是子行程，就繼續做父行程該做的事

    # 如果是子行程，我們只執行解題函式
    try:
        sol_func()
        sys.stdout.flush()
        sys.exit(0) # <--- 執行完直接結束程式！
    except Exception:
        # ... (錯誤處理)
        sys.exit(1)
```

這確保了**子行程只會執行解題邏輯 (sol_func)，然後立即結束**，絕對不會有機會繼續往下執行到可能再次呼叫 `run_tests` 的程式碼。
