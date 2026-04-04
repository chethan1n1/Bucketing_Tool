from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from loader import load_data
from matcher import find_best_match
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
THRESHOLD = 120
CATEGORY_MIN_SCORE = 55
FACTOR_MIN_SCORE = 55


class InputData(BaseModel):
	category: str
	factors: list[str]


@app.post("/predict")
def predict(data: InputData):
	results = []

	for factor in data.factors:
		score, result, category_score, factor_score = find_best_match(df, data.category, [factor])

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

		ai_result = ai_fallback(
			data.category,
			[factor],
			df.head(20).to_dict(orient="records"),
			df["bucket"].dropna().astype(str).unique().tolist(),
		)

		results.append({
			"factor_input": factor,
			"source": "ai",
			"category": ai_result.get("category", data.category),
			"factor": ai_result.get("factor", factor),
			"bucket": ai_result.get("bucket", "Novel_AI_Bucket"),
			"confidence_score": score,
			"category_score": category_score,
			"factor_score": factor_score,
		})

	return {
		"category": data.category,
		"results": results,
	}
