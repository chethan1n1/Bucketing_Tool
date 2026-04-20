import csv
import logging
import re
from threading import Lock
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from loader import load_data
from matcher import SemanticMatcher, infer_category_with_matcher, rerank_candidates
from utils import ai_select_bucket

app = FastAPI()

logger = logging.getLogger("bucketing")
if not logger.handlers:
	logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

df = load_data()
semantic_matcher = None
semantic_matcher_lock = Lock()

TOP_K = 5
HIGH_CONFIDENCE = 0.8
MEDIUM_CONFIDENCE = 0.6
SHORT_CIRCUIT_EMBEDDING = 0.9
DB_PREFERRED_CONFIDENCE = 0.7
DB_PREFERRED_EMBEDDING = 0.65
DB_PREFERRED_MIN_GAP = 0.01
UNMAPPED = "UNMAPPED_REVIEW_REQUIRED"
FEEDBACK_FILE = Path("data") / "feedback_corrections.csv"


def get_semantic_matcher():
	global semantic_matcher
	if semantic_matcher is None:
		with semantic_matcher_lock:
			if semantic_matcher is None:
				semantic_matcher = SemanticMatcher(df)
	return semantic_matcher


def _load_feedback_memory():
	feedback_memory = {}
	if not FEEDBACK_FILE.exists():
		return feedback_memory

	try:
		with FEEDBACK_FILE.open("r", newline="", encoding="utf-8") as handle:
			reader = csv.DictReader(handle)
			for row in reader:
				factor_key = _normalize_key(row.get("factor", ""))
				category_key = _normalize_key(row.get("category", ""))
				corrected_bucket = str(row.get("corrected_bucket", "")).strip()
				if not corrected_bucket:
					continue

				if category_key and factor_key:
					feedback_memory[(category_key, factor_key)] = corrected_bucket
				if factor_key and factor_key not in feedback_memory:
					feedback_memory[factor_key] = corrected_bucket
	except Exception:
			logger.exception("Unable to load feedback corrections from %s", FEEDBACK_FILE)

	return feedback_memory


class InputData(BaseModel):
	category: str
	factors: list[str]


class FeedbackData(BaseModel):
	factor: str
	category: str
	predicted_bucket: str
	corrected_bucket: str


def _unmapped_result(factor, input_category, decision_path):
	return {
		"factor_input": factor,
		"source": "unmapped",
		"category": input_category,
		"subcategory": "",
		"factor": factor,
		"bucket": UNMAPPED,
		"hierarchy_level": "",
		"sort_order": "",
		"confidence_score": 0.0,
		"embedding_score": 0.0,
		"fuzz_score": 0.0,
		"decision_path": decision_path,
	}


def _row_to_result(factor, input_category, row, source, decision_path, final_score, embedding_score, fuzz_score):
	return {
		"factor_input": factor,
		"source": source,
		"category": input_category,
		"matched_category": row.get("category", ""),
		"subcategory": row.get("subcategory", ""),
		"factor": row.get("factor", ""),
		"bucket": row.get("bucket", UNMAPPED),
		"bucket_description": row.get("bucket_description", row.get("description", row.get("bucket_meaning", ""))),
		"bucket_description": row.get("bucket_description", row.get("description", row.get("bucket_meaning", ""))),
		"hierarchy_level": row.get("hierarchy_level", ""),
		"sort_order": row.get("sort_order", ""),
		"confidence_score": round(float(final_score), 4),
		"final_score": round(float(final_score), 4),
		"embedding_score": round(float(embedding_score), 4),
		"fuzz_score": round(float(fuzz_score), 4),
		"decision_path": decision_path,
	}


def _normalize_key(value):
	value = str(value).lower().strip()
	value = value.replace("_", " ")
	value = re.sub(r"[^a-z0-9\s]", " ", value)
	value = re.sub(r"\s+", " ", value)
	return value


def _bucket_rankings(reranked):
	bucket_groups = {}
	for item in reranked:
		bucket = str(item.get("bucket", "")).strip()
		if not bucket:
			continue
		group = bucket_groups.setdefault(bucket, {
			"bucket": bucket,
			"best_item": item,
			"score": float(item.get("final_score", 0.0)),
			"count": 0,
		})
		group["count"] += 1
		if float(item.get("final_score", 0.0)) > float(group["best_item"].get("final_score", 0.0)):
			group["best_item"] = item
		group["score"] = max(group["score"], float(item.get("final_score", 0.0)))

	rankings = []
	for group in bucket_groups.values():
		support_bonus = min(0.08, 0.02 * max(0, group["count"] - 1))
		best_item = group["best_item"]
		rankings.append({
			"bucket": group["bucket"],
			"best_item": best_item,
			"score": min(1.0, float(group["score"]) + support_bonus),
			"support_bonus": support_bonus,
			"count": group["count"],
			"context": best_item.get("bucket_context", {}),
		})

	rankings.sort(key=lambda item: item["score"], reverse=True)
	return rankings


@app.post("/predict")
def predict(data: InputData):
	factors = [str(f).strip() for f in data.factors if str(f).strip()]
	input_category = str(data.category).strip()
	if not factors:
		return {"category": input_category, "results": []}

	matcher = get_semantic_matcher()
	feedback_memory = _load_feedback_memory()

	input_category_norm = _normalize_key(input_category)
 
	all_db_buckets = set(df["bucket"].dropna().astype(str).str.strip().tolist())

	scoped_df = df[df["category_norm"] == input_category_norm]
	search_category = input_category_norm
	ranking_df = scoped_df
	if scoped_df.empty:
		inferred_category = infer_category_with_matcher(df, input_category, factors, matcher=matcher)
		search_category = _normalize_key(inferred_category)
		ranking_df = df[df["category_norm"] == search_category]
		if ranking_df.empty:
			ranking_df = df
			logger.warning("No exact DB category scope found for category '%s'; using full taxonomy", input_category)

	results = []
	audit = []

	for factor in factors:
		factor_norm = _normalize_key(factor)
		feedback_bucket = feedback_memory.get((input_category_norm, factor_norm)) or feedback_memory.get(factor_norm)
		if feedback_bucket and feedback_bucket not in all_db_buckets:
			feedback_bucket = None

		candidates = matcher.search(search_category, factor, top_k=TOP_K) if search_category else []
		if not candidates:
			candidates = matcher.search_any(factor, top_k=TOP_K)
		if not candidates:
			results.append(_unmapped_result(factor, input_category, "embedding_empty"))
			audit.append({"factor": factor, "decision_path": "embedding_empty", "selected_bucket": UNMAPPED})
			continue

		reranked = rerank_candidates(
			ranking_df,
			factor,
			candidates,
			preferred_bucket=feedback_bucket,
			input_category=input_category,
			matcher=matcher,
		)
		if not reranked and ranking_df is not df:
			reranked = rerank_candidates(
			df,
			factor,
			candidates,
			preferred_bucket=feedback_bucket,
			input_category=input_category,
			matcher=matcher,
		)
		if not reranked:
			results.append(_unmapped_result(factor, input_category, "rerank_empty"))
			audit.append({"factor": factor, "decision_path": "rerank_empty", "selected_bucket": UNMAPPED})
			continue

		bucket_rankings = _bucket_rankings(reranked)
		top_bucket = bucket_rankings[0] if bucket_rankings else None
		top = top_bucket["best_item"] if top_bucket else reranked[0]
		row = top["row"]
		bucket = str(top["bucket"]).strip()
		final_score = float(top["final_score"])
		embedding_score = float(top["embedding_score"])
		fuzz_score = float(top["fuzz_score"])
		bucket_confidence = float(top_bucket["score"]) if top_bucket else final_score
		category_score = float(top.get("category_score", 0.0))
		bucket_semantic_score = float(top.get("bucket_semantic_score", 0.0))
		support_bonus = float(top.get("support_bonus", 0.0))
		second_bucket_score = float(bucket_rankings[1]["score"]) if len(bucket_rankings) > 1 else 0.0
		bucket_gap = bucket_confidence - second_bucket_score

		candidate_buckets = []
		candidate_bucket_contexts = []
		for item in bucket_rankings[:8]:
			candidate_bucket = str(item["bucket"]).strip()
			if candidate_bucket and candidate_bucket not in candidate_buckets:
				candidate_buckets.append(candidate_bucket)
				candidate_bucket_contexts.append(item.get("context", {"bucket": candidate_bucket, "examples": [], "top_categories": [], "count": 0, "description": "", "signature_text": candidate_bucket}))

		decision_path = ""
		selected_bucket = UNMAPPED
		selected_source = "unmapped"
		selected_row = None

		if embedding_score >= SHORT_CIRCUIT_EMBEDDING and bucket_confidence >= HIGH_CONFIDENCE and bucket in all_db_buckets:
			decision_path = "high_short_circuit"
			selected_bucket = bucket
			selected_source = "database"
			selected_row = row
		elif feedback_bucket and feedback_bucket in candidate_buckets and feedback_bucket in all_db_buckets:
			decision_path = "feedback_preferred"
			selected_bucket = feedback_bucket
			selected_source = "database"
			selected_row = next((item["row"] for item in reranked if str(item["bucket"]).strip() == feedback_bucket), row)
		elif bucket_confidence >= HIGH_CONFIDENCE and bucket in all_db_buckets:
			decision_path = "high"
			selected_bucket = bucket
			selected_source = "database"
			selected_row = row
		elif (
			bucket in all_db_buckets
			and bucket_confidence >= DB_PREFERRED_CONFIDENCE
			and embedding_score >= DB_PREFERRED_EMBEDDING
			and bucket_gap >= DB_PREFERRED_MIN_GAP
		):
			decision_path = "medium_db_preferred"
			selected_bucket = bucket
			selected_source = "database"
			selected_row = row
		elif bucket_confidence >= MEDIUM_CONFIDENCE:
			decision_path = "ai"
			try:
				ai_bucket = ai_select_bucket(input_category, factor, candidate_bucket_contexts)
			except Exception:
				ai_bucket = UNMAPPED

			if ai_bucket in candidate_buckets and ai_bucket in all_db_buckets:
				selected_bucket = ai_bucket
				selected_source = "ai_assisted"
				selected_row = next((item["row"] for item in reranked if str(item["bucket"]).strip() == ai_bucket), row)
			elif bucket in all_db_buckets and bucket_confidence >= DB_PREFERRED_CONFIDENCE:
				decision_path = "ai_db_fallback"
				selected_bucket = bucket
				selected_source = "database"
				selected_row = row
			else:
				selected_bucket = UNMAPPED
		else:
			decision_path = "low"
			selected_bucket = UNMAPPED

		if selected_bucket == UNMAPPED or selected_bucket not in all_db_buckets or selected_row is None:
			results.append(_unmapped_result(factor, input_category, decision_path or "unmapped"))
			selected_bucket = UNMAPPED
		else:
			results.append(_row_to_result(
				factor=factor,
				input_category=input_category,
				row=selected_row,
				source=selected_source,
				decision_path=decision_path,
				final_score=bucket_confidence,
				embedding_score=embedding_score,
				fuzz_score=fuzz_score,
			))

		audit.append({
			"factor": factor,
			"category": input_category,
			"bucket_confidence": round(float(bucket_confidence), 4),
			"bucket_gap": round(float(bucket_gap), 4),
			"category_score": round(float(category_score), 4),
			"bucket_semantic_score": round(float(bucket_semantic_score), 4),
			"support_bonus": round(float(support_bonus), 4),
			"feedback_bucket": feedback_bucket or "",
			"candidate_bucket_contexts": candidate_bucket_contexts,
			"embedding_candidates": [
				{
					"bucket": item["bucket"],
					"embedding_score": round(float(item["embedding_score"]), 4),
					"fuzz_score": round(float(item["fuzz_score"]), 4),
					"category_score": round(float(item.get("category_score", 0.0)), 4),
					"bucket_semantic_score": round(float(item.get("bucket_semantic_score", 0.0)), 4),
					"bucket_context": item.get("bucket_context", {}),
					"final_score": round(float(item["final_score"]), 4),
				}
				for item in reranked[:5]
			],
			"selected_bucket": selected_bucket,
			"decision_path": decision_path,
		})

	logger.info("classification_audit=%s", audit)

	def _sort_key(item):
		sort_order = str(item.get("sort_order", "")).strip()
		try:
			numeric_order = float(sort_order)
		except ValueError:
			numeric_order = 10**9
		return (
			str(item.get("category", "")).lower(),
			str(item.get("subcategory", "")).lower(),
			numeric_order,
			str(item.get("bucket", "")).lower(),
		)

	results = sorted(results, key=_sort_key)

	return {
		"category": input_category,
		"results": results,
	}


@app.post("/feedback")
def store_feedback(data: FeedbackData):
	FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
	file_exists = FEEDBACK_FILE.exists()

	with FEEDBACK_FILE.open("a", newline="", encoding="utf-8") as handle:
		writer = csv.DictWriter(handle, fieldnames=[
			"factor",
			"category",
			"predicted_bucket",
			"corrected_bucket",
			"timestamp",
		])
		if not file_exists:
			writer.writeheader()
		writer.writerow({
			"factor": data.factor,
			"category": data.category,
			"predicted_bucket": data.predicted_bucket,
			"corrected_bucket": data.corrected_bucket,
			"timestamp": datetime.now(timezone.utc).isoformat(),
		})

	return {"status": "stored"}
