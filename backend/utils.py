import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()


def _get_client():
	api_key = os.getenv("GROQ_API_KEY")
	if not api_key:
		raise ValueError("GROQ_API_KEY is not set. Add it to your .env file.")
	return Groq(api_key=api_key)


def _build_prompt(category, factors, df_sample, existing_buckets):
	return f"""
	You are a classification engine.

	Based on this dataset sample:
	{df_sample}

	Known database buckets (DO NOT USE ANY OF THESE):
	{existing_buckets}

	Input to classify:
	Category: {category}
	Factors: {factors}

	Rules:
	1) Propose a NEW bucket label that is not in the known database buckets.
	2) Do not reuse or slightly rephrase an existing bucket.
	3) Return strict JSON only.

	Return output in JSON:
	{{
	  \"category\": \"...\",
	  \"factor\": \"...\",
	  \"bucket\": \"new_bucket_not_in_db\"
	}}
	"""


def _is_new_bucket(bucket, existing_bucket_set):
	return str(bucket).strip().lower() not in existing_bucket_set


def ai_fallback(category, factors, df_sample, existing_buckets):
	client = _get_client()
	existing_bucket_set = {str(b).strip().lower() for b in existing_buckets if str(b).strip()}

	prompt = _build_prompt(category, factors, df_sample, existing_buckets)
	messages = [{"role": "user", "content": prompt}]

	for _ in range(2):
		response = client.chat.completions.create(
			model="llama-3.3-70b-versatile",
			messages=messages,
			temperature=0.2,
			response_format={"type": "json_object"},
		)

		content = response.choices[0].message.content or "{}"
		result = json.loads(content)
		bucket = result.get("bucket", "")

		if _is_new_bucket(bucket, existing_bucket_set):
			return result

		messages.append({
			"role": "assistant",
			"content": content,
		})
		messages.append({
			"role": "user",
			"content": "The bucket you returned already exists in DB. Return a different NEW bucket not in the provided list.",
		})

	# Guaranteed non-DB fallback if the model still violates constraints.
	return {
		"category": category,
		"factor": ", ".join(factors) if factors else "unknown",
		"bucket": "Novel_AI_Bucket",
	}
