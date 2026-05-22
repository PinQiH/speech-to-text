import argparse
import os
import sys

import google.generativeai as genai
import whisper


# > 工具函式

def format_segments(segments: list) -> str:
	"""將 Whisper segments 格式化為帶時間戳記的逐字稿字串"""
	lines = []
	for seg in segments:
		start = seg["start"]
		end = seg["end"]
		text = seg["text"]
		lines.append(f"[{start:.2f}s -> {end:.2f}s] {text}")
	return "\n".join(lines)


def ask_gemini(model, prompt: str) -> str:
	"""呼叫 Gemini 模型並回傳文字結果"""
	response = model.generate_content(prompt)
	return response.text


# > 主流程

def main():
	parser = argparse.ArgumentParser(description="語音轉文字 + AI 摘要工具")
	parser.add_argument("audio", help="音檔路徑（mp3、wav、m4a 等）")
	parser.add_argument(
		"--model",
		default="small",
		choices=["tiny", "base", "small", "medium", "large"],
		help="Whisper 模型大小（預設: small）",
	)
	parser.add_argument(
		"--no-llm",
		action="store_true",
		help="跳過 Gemini 摘要與錯字修正步驟",
	)
	args = parser.parse_args()

	if not os.path.exists(args.audio):
		print(f"[錯誤] 找不到音檔：{args.audio}", file=sys.stderr)
		sys.exit(1)

	# > Whisper 語音辨識
	print(f"\n[1/4] 載入 Whisper 模型（{args.model}）...")
	whisper_model = whisper.load_model(args.model)

	print(f"[2/4] 辨識音檔：{args.audio}")
	result = whisper_model.transcribe(args.audio)

	print("\n========== 逐字稿 ==========")
	print(result["text"])

	print("\n========== 字幕段落 ==========")
	for seg in result["segments"]:
		print(f"[{seg['start']:.2f}s -> {seg['end']:.2f}s] {seg['text']}")

	if args.no_llm:
		print("\n（已跳過 LLM 步驟）")
		return

	# > 確認 Google API Key
	api_key = os.environ.get("GOOGLE_API_KEY", "")
	if not api_key:
		print("\n[警告] 未設定 GOOGLE_API_KEY，跳過 Gemini 摘要步驟", file=sys.stderr)
		return

	genai.configure(api_key=api_key)
	transcription_text = format_segments(result["segments"])

	print("\n[3/4] 載入 Gemini 模型...")
	llm = genai.GenerativeModel("models/gemini-pro-latest")

	# > 段落重點整理
	print("[4/4] 生成段落重點摘要...")
	summary_prompt = f"""請根據以下音頻逐字稿，提取主要關鍵點或重要段落，並為每個關鍵點提供大致的起始時間和結束時間。時間格式為 `[起始時間s -> 結束時間s]`，摘要內容。

逐字稿內容：
{transcription_text}

請以以下格式輸出：
[起始時間s -> 結束時間s] 摘要內容
[起始時間s -> 結束時間s] 摘要內容
..."""

	print("\n========== 段落重點摘要 ==========")
	print(ask_gemini(llm, summary_prompt))

	# > 錯字修正
	typo_prompt = f"""請檢查以下音頻逐字稿，並修正其中的錯別字。特別是，請將所有簡體中文字轉換為繁體中文字。輸出時，只返回修正後的文本，不需要任何額外的說明或格式。

逐字稿內容：
{transcription_text}
"""

	print("\n========== 繁體中文修正逐字稿 ==========")
	print(ask_gemini(llm, typo_prompt))


if __name__ == "__main__":
	main()
