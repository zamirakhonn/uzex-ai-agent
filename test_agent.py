"""Run representative Uzbek and Russian questions against the local agent."""

from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

from backend.app.pipeline import answer

QUESTIONS = [
    ("2025 yilda nechta bitim tuzilgan?", True),
    ("Сколько сделок было в январе 2024 года?", True),
    ("Eng ko'p bitim qilgan kompaniya qaysi?", True),
    ("ABC kompaniyasi qancha bitim qilgan?", False),
]


def run_tests():
    print("=" * 50)
    print("UZEX AI AGENT TEST")
    print("=" * 50)

    failures = 0
    for question, expected_found in QUESTIONS:
        print("\nQUESTION:")
        print(question)

        start = perf_counter()
        try:
            result = answer(question)
            elapsed = perf_counter() - start
            print("\nANSWER:")
            print(result.answer)
            if result.found != expected_found:
                failures += 1
                print("\nCHECK:")
                print(f"Expected found={expected_found}, received found={result.found}")
            print("\nTIME:")
            print(f"{elapsed:.2f} seconds")
        except Exception as error:
            failures += 1
            print("\nERROR:")
            print(f"{type(error).__name__}: {error}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run_tests())