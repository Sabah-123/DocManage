import asyncio
from agents.ocr_agent import extract_text

async def main():
    try:
        with open("Sans titre.png", "rb") as f:
            b = f.read()
            text, engine = extract_text(b, "png")
            print("OCR RESULT:", text)
            print("ENGINE:", engine)
    except Exception as e:
        print("ERROR:", e)

if __name__ == "__main__":
    asyncio.run(main())
