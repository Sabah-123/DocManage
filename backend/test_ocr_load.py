from agents.ocr_agent import _get_paddle, _get_pix2tex
print("Loading Paddle...")
try:
    _get_paddle()
    print("Paddle loaded.")
except Exception as e:
    print(f"Paddle error: {e}")

print("Loading Pix2Tex...")
try:
    _get_pix2tex()
    print("Pix2Tex loaded.")
except Exception as e:
    print(f"Pix2Tex error: {e}")
