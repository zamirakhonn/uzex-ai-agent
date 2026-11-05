"""
UZEX AI Agent - Test Runner

Compatibility entrypoint for testing the AI agent locally.
"""

import os
from dotenv import load_dotenv

load_dotenv()

from backend.app.pipeline import answer


def answer_question(question: str) -> str:
    """
    Simple compatibility function.
    Returns only the final answer.
    """

    result = answer(question)

    return result.answer



def run_test():

    print("=" * 60)
    print("UZEX AI AGENT TEST")
    print("=" * 60)

    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY missing")
        print("Create .env file with:")
        print("OPENAI_API_KEY=your_key")
        return


    print("✅ API key loaded")


    while True:

        question = input("\nAsk question (or exit): ")

        if question.lower() in [
            "exit",
            "quit",
            "q"
        ]:
            break


        try:

            result = answer(question)


            print("\n" + "=" * 60)
            print("ANSWER")
            print("=" * 60)

            print(result.answer)


            # Show evidence if available
            if hasattr(result, "sources"):

                print("\n" + "=" * 60)
                print("SOURCES")
                print("=" * 60)

                print(result.sources)


            # Show confidence if available
            if hasattr(result, "confidence"):

                print("\nConfidence:")
                print(result.confidence)



        except Exception as e:

            print("\n❌ ERROR")
            print(e)



if __name__ == "__main__":
    run_test()