import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

load_dotenv()


def _get_client():
	api_key = os.getenv("GROQ_API_KEY")
	if not api_key:
		raise ValueError("GROQ_API_KEY is not set.")
	return Groq(api_key=api_key)


# Normalize free-text inputs to reduce noise from casing/punctuation variations.
def _normalize_text(text):
	if not text:
		return ""
	value = str(text).lower().strip()
	value = re.sub(r"[^a-z0-9\s,]", "", value)
	value = re.sub(r"\s+", " ", value)
	return value


def _normalize_bucket(text):
	value = _normalize_text(text)
	value = value.replace(",", "")
	return value


def _build_prompt(category, factor, candidate_buckets):
	candidate_lines = []
	for item in candidate_buckets:
		if isinstance(item, dict):
			bucket = str(item.get("bucket", "")).strip()
			examples = [str(example).strip() for example in item.get("examples", []) if str(example).strip()]
			top_categories = [str(category_name).strip() for category_name in item.get("top_categories", []) if str(category_name).strip()]
			count = item.get("count", 0)
			signature = str(item.get("signature_text", bucket)).strip()
			description = str(item.get("description", "")).strip()
			if not bucket:
				continue
			line = f"- {bucket}"
			if top_categories:
				line += f" | categories: {', '.join(top_categories)}"
			if description:
				line += f" | meaning: {description}"
			if examples:
				line += f" | examples: {', '.join(examples[:5])}"
			if signature:
				line += f" | signature: {signature}"
			line += f" | count: {count}"
			candidate_lines.append(line)
		else:
			bucket = str(item).strip()
			if bucket:
				candidate_lines.append(f"- {bucket}")

	candidate_block = "\n".join(candidate_lines)
	return f"""
	You are a strict bucket selector.

	Rules:
	- Return only one bucket name that already exists in the candidate bucket list.
	- Never invent a new bucket name.
	- Never paraphrase, rename, or merge buckets.
	- If no candidate bucket matches the category and factor, return NONE.
	- Do not explain your answer.
	- Infer the latent meaning of the factor before matching it to a bucket.
	- Prefer the bucket whose examples, meaning, and category fit the implied intent, tone, or status of the factor.
	- For abstract or brand-like inputs, map the implied attribute rather than the surface word.
	- Borderline examples should be interpreted semantically: "prestige" usually signals status, premium positioning, exclusivity, or prestige-related brand tone; "ambani" can signal wealth, scale, influence, power, or high-end corporate stature.

	Category: {category}
	Factor: {factor}
	Candidate Bucket Profiles:
	{candidate_block}

	Output JSON only:
	{{"bucket": "<one exact candidate or NONE>"}}
	"""


def ai_select_bucket(category, factor, candidate_buckets):
	clean_candidates = []
	for bucket in candidate_buckets:
		if isinstance(bucket, dict):
			clean_bucket = str(bucket.get("bucket", "")).strip()
			if clean_bucket:
				clean_candidates.append({
					"bucket": clean_bucket,
					"examples": [str(example).strip() for example in bucket.get("examples", []) if str(example).strip()],
					"top_categories": [str(category_name).strip() for category_name in bucket.get("top_categories", []) if str(category_name).strip()],
					"description": str(bucket.get("description", "")).strip(),
					"count": bucket.get("count", 0),
					"signature_text": str(bucket.get("signature_text", clean_bucket)).strip(),
				})
		else:
			clean_bucket = str(bucket).strip()
			if clean_bucket:
				clean_candidates.append({"bucket": clean_bucket, "examples": [], "top_categories": [], "description": clean_bucket, "count": 0, "signature_text": clean_bucket})

	if not clean_candidates:
		return "UNMAPPED_REVIEW_REQUIRED"

	normalized_candidates = {
		_normalize_bucket(item["bucket"]): item["bucket"]
		for item in clean_candidates
	}

	client = _get_client()
	prompt = _build_prompt(_normalize_text(category), _normalize_text(factor), clean_candidates)
	messages = [{"role": "user", "content": prompt}]

	for _ in range(2):
		response = client.chat.completions.create(
			model="llama-3.3-70b-versatile",
			messages=messages,
			temperature=0.0,
			response_format={"type": "json_object"},
		)

		content = response.choices[0].message.content or "{}"
		try:
			result = json.loads(content)
		except json.JSONDecodeError:
			continue

		bucket = str(result.get("bucket", "")).strip()
		if not bucket or bucket == "NONE":
			return "UNMAPPED_REVIEW_REQUIRED"

		normalized_bucket = _normalize_bucket(bucket)
		if normalized_bucket in normalized_candidates:
			return normalized_candidates[normalized_bucket]
		return "UNMAPPED_REVIEW_REQUIRED"

	return "UNMAPPED_REVIEW_REQUIRED"
