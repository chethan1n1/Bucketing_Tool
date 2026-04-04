from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from loader import load_data
from matcher import find_best_match, get_dominant_bucket, infer_category
from utils import ai_fallback

app = FastAPI()

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

df = load_data()
THRESHOLD = 95
CATEGORY_MIN_SCORE = 25
FACTOR_MIN_SCORE = 72


class InputData(BaseModel):
	category: str
	factors: list[str]


@app.post("/predict")
def predict(data: InputData):
	factors = [str(f).strip() for f in data.factors if str(f).strip()]
	inferred_category = infer_category(df, data.category, factors)
	inferred_category_norm = str(inferred_category).lower().replace("_", " ").strip()

	# First pass: gather strong unambiguous matches to infer dominant bucket context.
	first_pass = []
	strong_buckets = []
	for factor in factors:
		score, result, category_score, factor_score = find_best_match(df, inferred_category, [factor])
		first_pass.append((factor, score, result, category_score, factor_score))

		if result is None:
			continue

		factor_norm = factor.lower().replace("_", " ").strip()
		exact_rows = df[
			(df["category_norm"] == inferred_category_norm)
			& (df["factor_norm"] == factor_norm)
		]
		bucket_options = exact_rows["bucket"].dropna().astype(str).str.strip().replace("", None).dropna().unique().tolist()

		is_unambiguous_exact = len(bucket_options) == 1
		if score >= THRESHOLD and factor_score >= 95 and is_unambiguous_exact:
			strong_buckets.append(result["bucket"])

	dominant_bucket = get_dominant_bucket(strong_buckets)
	results = []

	for factor, score, result, category_score, factor_score in first_pass:
		preferred_bucket = None
		if dominant_bucket:
			factor_norm = factor.lower().replace("_", " ").strip()
			exact_rows = df[
				(df["category_norm"] == inferred_category_norm)
				& (df["factor_norm"] == factor_norm)
			]
			bucket_options = exact_rows["bucket"].dropna().astype(str).str.strip().replace("", None).dropna().unique().tolist()
			if len(bucket_options) > 1 and dominant_bucket in bucket_options:
				preferred_bucket = dominant_bucket

		if preferred_bucket:
			score, result, category_score, factor_score = find_best_match(
				df,
				inferred_category,
				[factor],
				preferred_bucket=preferred_bucket,
			)

		if (
			result is not None
			and score >= THRESHOLD
			and category_score >= CATEGORY_MIN_SCORE
			and factor_score >= FACTOR_MIN_SCORE
		):
			results.append({
				"factor_input": factor,
				"source": "database",
				"category": result["category"],
				"factor": result["factor"],
				"bucket": result["bucket"],
				"confidence_score": score,
				"category_score": category_score,
				"factor_score": factor_score,
			})
			continue

		try:
			ai_result = ai_fallback(
				inferred_category,
				[factor],
				df.head(20).to_dict(orient="records"),
				df["bucket"].dropna().astype(str).unique().tolist(),
			)
		except Exception:
			ai_result = {
				"category": inferred_category,
				"factor": factor,
				"bucket": "UNMAPPED_REVIEW_REQUIRED",
			}

		results.append({
			"factor_input": factor,
			"source": "ai",
			"category": ai_result.get("category", inferred_category),
			"factor": ai_result.get("factor", factor),
			"bucket": ai_result.get("bucket", "Novel_AI_Bucket"),
			"confidence_score": score,
			"category_score": category_score,
			"factor_score": factor_score,
		})

	return {
		"category": inferred_category,
		"results": results,
	}
