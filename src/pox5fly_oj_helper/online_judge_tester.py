import sys
import os
import pathlib
import subprocess
import dataclasses
import time
import statistics
from typing import List, Optional, Union, Any, Callable


import traceback


@dataclasses.dataclass
class TestResult:
    """
    儲存單一測試案例的執行結果。

    Attributes:
        case_name: 測試案例名稱 (如 "01", "test_01")
        status: 執行狀態 (AC, WA, TLE, RE)
        execution_times: 執行時間列表 (ms)
        output: 程式的標準輸出
        error_message: 錯誤訊息 (WA 的 Diff 或 RE 的 Traceback)
    """

    case_name: str
    status: str
    execution_times: List[float]
    output: str
    error_message: str


class OnlineJudgeTester:
    """
    用於在本機模擬 Online Judge 環境並測試 Python 腳本的工具。
    """

    # 狀態常數
    STATUS_AC = "AC"
    STATUS_WA = "WA"
    STATUS_TLE = "TLE"
    STATUS_RE = "RE"
    STATUS_MISSING = "MISSING"

    def __init__(
        self,
        target_script_path: str,
        time_limit: int = 3000,
        compare_output: bool = True,
        test_case_path: Optional[str] = None,
        max_diffs: Optional[int] = 10,
        show_missing_output: bool = False,
    ) -> None:
        """
        初始化測試器。

        Args:
            target_script_path: 目標測試腳本的路徑。
            time_limit: 時間限制 (毫秒)，預設 3000ms。
            compare_output: 是否比對輸出，預設 True。
            test_case_path: 測資資料夾路徑。若為 None，預設為腳本同層的 'test_case' 資料夾。
            max_diffs: 最大顯示錯誤差異行數，預設 10。
            show_missing_output: 若找不到 .out 檔，是否顯示程式原始輸出，預設 False。
        """
        self.time_limit = time_limit
        self.compare_output = compare_output
        self.max_diffs = max_diffs
        self.show_missing_output = show_missing_output

        # 1. 處理腳本路徑為絕對路徑
        self.target_script = pathlib.Path(target_script_path).resolve()
        if not self.target_script.exists():
            raise FileNotFoundError(f"Target script not found: {self.target_script}")

        # 2. 處理測資路徑
        if test_case_path:
            self.test_case_dir = pathlib.Path(test_case_path).resolve()
        else:
            # 預設為腳本所在目錄下的 test_case 資料夾
            self.test_case_dir = self.target_script.parent / "test_case"

    def _collect_test_cases(self) -> List[tuple[pathlib.Path, Optional[pathlib.Path]]]:
        """
        搜尋 test_case_dir 下的所有 .in 檔，並嘗試配對 .out 檔。
        回傳結果已排序。
        """
        if not self.test_case_dir.exists():
            # 這裡不拋錯，留給 run_tests 時發現無測資再處理，
            # 或者也可以回傳空列表，由 caller 判斷。
            return []

        cases = []
        for input_path in self.test_case_dir.glob("*.in"):
            # 尋找對應的 .out 檔
            output_path = input_path.with_suffix(".out")
            if not output_path.exists():
                output_path = None
            cases.append((input_path, output_path))

        # 排序邏輯：嘗試抓取檔名中的數字進行排序，如果沒數字則使用字典序
        # 這裡我們使用一個 helper key function
        # 例如: "1.in" -> (1, "1.in"), "test02.in" -> (2, "test02.in")
        def sort_key(item):
            path, _ = item
            name = path.stem
            # 嘗試提取檔名中的數字部分
            import re

            numbers = re.findall(r"\d+", name)
            if numbers:
                # 取最後一個數字當作主要序號 (假設常見格式如 p1, test_01)
                # 或者取第一個，視慣例而定。這裡取第一個碰到的數字串轉 int
                return int(numbers[0])
            return name

        cases.sort(key=sort_key)
        return cases

    def _filter_test_cases(
        self,
        all_cases: List[tuple[pathlib.Path, Optional[pathlib.Path]]],
        cases_to_run: Optional[List[Union[int, str]]],
    ) -> List[tuple[pathlib.Path, Optional[pathlib.Path]]]:
        """
        根據使用者指定的 cases_to_run 列表篩選要執行的測資。

        Args:
            all_cases: 所有已發現的測資列表 [(input_path, output_path), ...]。
            cases_to_run: 使用者指定的測資編號或名稱列表。
                          - 整數 (int): 進行數值匹配 (如 1 匹配 "01.in")。
                          - 字串 (str): 進行部分包含匹配 (如 "test" 匹配 "my_test_01.in")。

        Returns:
            篩選後的測資列表。
        """
        if not cases_to_run:
            return all_cases

        filtered_cases = []
        for input_path, output_path in all_cases:
            case_name = input_path.stem
            matched = False
            for token in cases_to_run:
                if isinstance(token, int):
                    # 整數匹配：支援自動補零 (e.g., 1 matches "01")
                    # 僅當檔名為純數字時才進行數值比對
                    if case_name.isdigit() and int(case_name) == token:
                        matched = True
                        break

                elif isinstance(token, str):
                    # 字串匹配：包含檢查
                    if token in case_name:
                        matched = True
                        break

            if matched:
                filtered_cases.append((input_path, output_path))

        return filtered_cases

    def _run_single_process(self, input_str: str) -> tuple[str, str, float, str]:
        """
        單次執行測試腳本。

        Returns:
            (status, output, duration_ms, error_message)
        """
        # 準備環境變數：強制無緩衝
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        # 標記這是子行程，用於防止遞迴呼叫 run_tests
        env["OJ_CHILD_PROCESS"] = "1"

        # 啟動子行程
        # 使用 sys.executable 確保使用同一個 python 直譯器
        # -u 參數再次確保無緩衝 (雖有 env 但雙重保險)
        cmd = [sys.executable, "-u", str(self.target_script)]

        start_time = time.perf_counter()

        try:
            # text=True 讓 stdin/stdout 自動處理 encoding (預設 utf-8)
            # cwd=self.target_script.parent 確保腳本內的相對路徑讀取正確
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.target_script.parent,
                text=True,
                env=env,
            )

            # 使用 communicate 傳入輸入並取得輸出
            # timeout 單位為秒，這裡將 ms 轉為 s
            stdout, stderr = proc.communicate(
                input=input_str, timeout=self.time_limit / 1000
            )

            duration = (time.perf_counter() - start_time) * 1000  # ms

            if proc.returncode != 0:
                # Runtime Error
                return self.STATUS_RE, stdout, duration, stderr

            return self.STATUS_AC, stdout, duration, ""

        except subprocess.TimeoutExpired as e:
            # 發生超時
            duration = (time.perf_counter() - start_time) * 1000

            # 嘗試殺掉行程
            proc.kill()
            try:
                # 再次 communicate 取回剩餘輸出 (如果有)
                stdout, stderr = proc.communicate(timeout=0.2)
            except Exception:
                stdout = e.stdout if e.stdout else ""
                stderr = e.stderr if e.stderr else ""

            # 確保 stdout 不是 bytes (如果是 text=True 應該是 str，但 TimeoutExpired 有時行為不同)
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")

            # 規範要求：若 TLE，output 欄位應包含被殺掉前捕獲的輸出
            return self.STATUS_TLE, (stdout if stdout else ""), duration, ""

        except Exception as e:
            # 其他未知錯誤 (也許有?我不知道)
            return self.STATUS_RE, "", 0.0, str(e)

    def _execute_case_with_repeat(
        self, input_path: pathlib.Path, repeat: int
    ) -> tuple[str, List[float], str, str]:
        """
        執行單一測資 (含重複執行邏輯)。

        Returns:
             (status, execution_times, final_output, error_message)
        """
        try:
            input_content = input_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            input_content = input_path.read_text(encoding="latin-1")  # Fallback

        execution_times = []
        final_output = ""
        final_status = ""
        final_error = ""

        for i in range(repeat):
            status, output, duration, error_msg = self._run_single_process(
                input_content
            )

            execution_times.append(duration)
            final_status = status
            final_output = output
            final_error = error_msg

            # 若非 AC，立即停止重測
            if status != self.STATUS_AC:
                break

        return final_status, execution_times, final_output, final_error

    def _compare_output(
        self, actual_output: str, expected_path: pathlib.Path, strict: bool = False
    ) -> tuple[str, str]:
        """
        比對輸出結果。

        Returns:
            (status, error_message)
        """
        try:
            expected_output = expected_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            expected_output = expected_path.read_text(encoding="latin-1")

        if strict:
            # 嚴格比對：完全一致
            if actual_output == expected_output:
                return self.STATUS_AC, ""
            else:
                # 這裡嚴格比對如果不同，可能顯示第一個差異點會比較好，
                # 沿用寬鬆比對的逐行顯示，或者簡單顯示不一致。
                # 為了方便，用類似寬鬆比對的格式顯示差異 (針對行)
                pass
                # 讓下面的邏輯共用報告生成，只是預處理不同

        # 預處理
        if strict:
            act_lines = actual_output.splitlines()
            exp_lines = expected_output.splitlines()
        else:
            # 寬鬆比對：去除行尾空白，去除空行

            def process_lines(text: str) -> List[str]:
                lines = text.splitlines()
                processed = []
                for line in lines:
                    stripped = line.strip()
                    if stripped:
                        processed.append(stripped)
                return processed

            act_lines = process_lines(actual_output)
            exp_lines = process_lines(expected_output)

        # 開始比對列表
        if act_lines == exp_lines:
            return self.STATUS_AC, ""

        # 產生錯誤報告 (WA)
        # 逐行比對找出不同
        error_msg_lines = []
        max_len = max(len(act_lines), len(exp_lines))

        diff_count = 0

        for i in range(max_len):
            # Check for insufficient lines (Early EOF from actual output)
            if i >= len(act_lines):
                error_msg_lines.append("Error: Insufficient output lines.")
                break

            line_act = act_lines[i]
            line_exp = exp_lines[i] if i < len(exp_lines) else "<EOF>"

            if line_act != line_exp:
                diff_count += 1

                # 若 max_diffs 為 None 則無限顯示，否則檢查是否超過上限
                if self.max_diffs is None or diff_count <= self.max_diffs:
                    entry = f"line {i + 1}: got:    {repr(line_act)}\n        expect: {repr(line_exp)}"
                    error_msg_lines.append(entry)

        if self.max_diffs is not None and diff_count > self.max_diffs:
            error_msg_lines.append(
                f"... and {diff_count - self.max_diffs} more differences."
            )

        return self.STATUS_WA, "\n".join(error_msg_lines)

    def _handle_child_process(self, sol_func: Callable[[], Any]) -> None:
        """
        處理子行程的執行邏輯。

        若檢測到環境變數 OJ_CHILD_PROCESS 為 "1"，則執行用戶代碼。
        此方法會接管控制權並最終呼叫 sys.exit()，主進程不應調用此方法後繼續執行。

        Args:
            sol_func: 用戶提供的解題主函式。
        """
        if os.environ.get("OJ_CHILD_PROCESS") != "1":
            return

        try:
            # 直接執行 sol_func
            sol_func()
            # 使用 flush 確保 stdout 內容輸出
            sys.stdout.flush()
            sys.exit(0)
        except Exception:
            # 捕獲例外並自訂 Traceback 輸出
            # 目標：過濾掉 online_judge_tester.py 內部的堆疊框架，只顯示使用者代碼部分

            # 取得當前例外資訊
            exc_type, exc_value, exc_traceback = sys.exc_info()

            # 提取堆疊列表 (SummaryTuple list)
            tb_list = traceback.extract_tb(exc_traceback)

            # 過濾邏輯：移除檔案路徑包含本模組檔案名的框架
            # 注意：這裡使用 __file__ 來判斷
            current_file = os.path.abspath(__file__)
            filtered_tb = []
            for frame in tb_list:
                # 如果 frame.filename 與本模組路徑相同，則過濾掉
                # 為了保險，比較絕對路徑
                if os.path.abspath(frame.filename) != current_file:
                    filtered_tb.append(frame)

            # 重新組合成字串
            # 格式化 Traceback Header
            err_msg = "Traceback (most recent call last):\n"

            # 格式化過濾後的堆疊
            err_msg += "".join(traceback.format_list(filtered_tb))

            # 加上例外本身的訊息 (e.g. ValueError: ...)
            err_msg += "".join(traceback.format_exception_only(exc_type, exc_value))

            sys.stderr.write(err_msg)
            sys.exit(1)

    def _print_test_result(self, result: TestResult, show_raw_output: bool) -> None:
        """
        格式化並輸出單一測試案例的執行結果。

        Args:
            result: 測試結果物件。
            show_raw_output: 是否強制顯示原始輸出。
        """
        # 計算時間顯示字串
        exec_times = result.execution_times
        if not exec_times:
            time_str = "N/A"
        elif len(exec_times) == 1:
            time_str = f"{exec_times[0]:.2f}ms"
        else:
            avg_t = statistics.mean(exec_times)
            max_t = max(exec_times)
            min_t = min(exec_times)
            time_str = f"{avg_t:.2f}ms (min:{min_t:.2f}, max:{max_t:.2f})"

        # 狀態顯示
        print(f"[{result.case_name}] Status: {result.status} | Time: {time_str}")

        if result.status == self.STATUS_WA:
            print("  [Wrong Answer Info]")
            for line in result.error_message.splitlines():
                print(f"    {line}")

        elif result.status == self.STATUS_RE:
            print("  [Runtime Error Info]")
            print(result.error_message)

        elif result.status == self.STATUS_TLE:
            print("  [Time Limit Exceeded]")

        elif result.status == self.STATUS_MISSING:
            print(f"  [Info] {result.error_message}")
            if self.show_missing_output:
                print("  [Raw Output (Missing .out)]")
                print(result.output)
                print("  [End Raw Output]")

        if show_raw_output:
            print("  [Raw Output]")
            print(result.output)
            print("  [End Raw Output]")

        print("-" * 40)

    def run_tests(
        self,
        sol_func: Callable[[], Any],
        strict_comparison: bool = False,
        repeat: int = 1,
        cases_to_run: Optional[List[Union[int, str]]] = None,
        show_raw_output: bool = False,
    ) -> List[TestResult]:
        """
        執行測試的主流程。

        Args:
            sol_func: [必要] 用於子行程執行的解題主函式。若作為 CLI Runner 使用可傳入 dummy。
            strict_comparison: 是否啟用嚴格比對。
            repeat: 單一測資重複執行次數。
            cases_to_run: 指定執行的測資編號/名稱列表。
            show_raw_output: 是否顯示原始輸出。

        Returns:
            測試結果列表。
        """
        # 0. 檢查並處理子行程執行的情況 (防止遞迴)
        # 詳細原理請見 docs/03fork_bomb_protection.md
        self._handle_child_process(sol_func)

        # 1. 收集與篩選測資
        all_cases = self._collect_test_cases()
        if not all_cases and not cases_to_run:
            raise FileNotFoundError(f"No .in files found in {self.test_case_dir}")

        target_cases = self._filter_test_cases(all_cases, cases_to_run)

        if cases_to_run and not target_cases:
            print(f"[WARNING] No cases matched filter: {cases_to_run}")
            return []

        # 2. 顯示相關資訊
        print(f"=== Running Tests on {self.target_script.name} ===")
        print(f"Target: {self.target_script}")
        print(f"Cases: {len(target_cases)} selected")
        print("-" * 40)

        results = []
        for input_path, expected_path in target_cases:
            case_name = input_path.stem

            # 3. 執行
            status, exec_times, output, error_msg = self._execute_case_with_repeat(
                input_path, repeat
            )

            # 4. 比對 (若執行成功且有預期輸出且需要比對)
            if status == self.STATUS_AC and self.compare_output:
                if expected_path:
                    cmp_status, cmp_msg = self._compare_output(
                        output, expected_path, strict_comparison
                    )
                    status = cmp_status
                    if cmp_status != self.STATUS_AC:
                        error_msg = cmp_msg
                else:
                    status = self.STATUS_MISSING
                    error_msg = f"找不到對應的 {case_name}.out 檔案"

            # 5. 構建 Result 並保存
            result = TestResult(
                case_name=case_name,
                status=status,
                execution_times=exec_times,
                output=output,
                error_message=error_msg,
            )
            results.append(result)

            # 6. 即時顯示結果
            self._print_test_result(result, show_raw_output)

        return results


if __name__ == "__main__":
    # 簡單 CLI 介面，方便測試本模組
    import argparse

    parser = argparse.ArgumentParser(description="Online Judge Tester")
    parser.add_argument("script", help="Target Python script to test")
    parser.add_argument("--dir", help="Test case directory", default=None)
    parser.add_argument("--time", type=int, default=3000, help="Time limit in ms")
    parser.add_argument(
        "--strict", action="store_true", help="Enable strict comparison"
    )
    parser.add_argument("--repeat", type=int, default=1, help="Repeat count")
    parser.add_argument(
        "--cases", nargs="+", help="Specific cases to run (e.g. 1 02 string)"
    )
    parser.add_argument("--raw", action="store_true", help="Show raw output")

    args = parser.parse_args()

    # 處理 case list
    # argparse 讀進來都是字串，嘗試轉 int
    cases_arg = None
    if args.cases:
        cases_arg = []
        for c in args.cases:
            if c.isdigit():
                cases_arg.append(int(c))
            else:
                cases_arg.append(c)

    try:
        tester = OnlineJudgeTester(
            target_script_path=args.script,
            time_limit=args.time,
            compare_output=True,
            test_case_path=args.dir,
        )

        # CLI 模式下，子行程執行的是 args.script 本身，
        # 它並不會執行到這裡的 sol_func (除非 args.script 內部又呼叫了 run_tests，那由它自己處理)
        # 所以這裡傳入一個 dummy 函式即可滿足型別檢查。
        tester.run_tests(
            sol_func=lambda: None,
            strict_comparison=args.strict,
            repeat=args.repeat,
            cases_to_run=cases_arg,
            show_raw_output=args.raw,
        )
    except Exception as e:
        print(f"Error: {e}")
