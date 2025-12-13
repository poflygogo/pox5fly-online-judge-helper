import sys
from pathlib import Path

path = Path(__file__).resolve().parent
while not (path / "src").exists():
    if path == path.parent:
        raise Exception("can't find the dir")
    path = path.parent
sys.path.append(str(path))

from src.pox5fly_oj_helper.online_judge_tester import OnlineJudgeTester


def main():
    while True:
        try:
            name: str = input().strip()
            print(f"hello, {name}   ")
        except EOFError:
            break


if __name__ == "__main__":
    test = OnlineJudgeTester(__file__, max_diffs=0)

    # expect WA
    test.run_tests(main, strict_comparison=True)

    # expect AC
    test.run_tests(main, strict_comparison=False)
