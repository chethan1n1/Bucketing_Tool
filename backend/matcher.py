import re
from functools import lru_cache
from typing import Any

import faiss
import numpy as np
from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer


def _normalize(text):
	text = str(text).lower().strip()
	text = text.replace("_", " ")
	text = re.sub(r"[^a-z0-9\s]", " ", text)
	text = re.sub(r"\s+", " ", text)
	return text


def _score_from_cosine(score):
	return max(0.0, min(1.0, (float(score) + 1.0) / 2.0))


@lru_cache(maxsize=2)
def _get_embedding_model(model_name):
	return SentenceTransformer(model_name)


@lru_cache(maxsize=4096)
def _get_query_embedding(model_name, normalized_text):
	model = _get_embedding_model(model_name)
	vector = model.encode([normalized_text], normalize_embeddings=True, convert_to_numpy=True)
	vector = np.asarray(vector[0], dtype=np.float32)
	return tuple(float(x) for x in vector)


def _get_embedding_vector(model_name, text):
	normalized_text = _normalize(text)
	if not normalized_text:
		return None
	return np.asarray(_get_query_embedding(model_name, normalized_text), dtype=np.float32)


def _normalize_vector(vector):
	vector = np.asarray(vector, dtype=np.float32)
	norm = float(np.linalg.norm(vector))
	if not norm:
		return vector
	return vector / norm


def _merge_search_results(*result_sets):
	merged = {}
	for result_set in result_sets:
		for item in result_set or []:
			row_id = item["row_id"]
			existing = merged.get(row_id)
			if existing is None or float(item["embedding_score"]) > float(existing["embedding_score"]):
				merged[row_id] = item
	return sorted(merged.values(), key=lambda item: item["embedding_score"], reverse=True)


def fuzzy_match_01(input_val, target):
	left = _normalize(input_val)
	right = _normalize(target)
	if not left or not right:
		return 0.0

	ratio = float(fuzz.ratio(left, right))
	partial = float(fuzz.partial_ratio(left, right))
	token_sort = float(fuzz.token_sort_ratio(left, right))
	token_set = float(fuzz.token_set_ratio(left, right))
	weighted_ratio = float(fuzz.WRatio(left, right))
	weighted = (0.18 * ratio) + (0.14 * partial) + (0.22 * token_sort) + (0.18 * token_set) + (0.28 * weighted_ratio)
	return max(0.0, min(1.0, weighted / 100.0))


def infer_category(df, input_category, factors):
	return infer_category_with_matcher(df, input_category, factors, matcher=None)


def infer_category_with_matcher(df, input_category, factors, matcher=None):
	if df is None or df.empty:
		return input_category

	category_col = "category_norm" if "category_norm" in df.columns else "category"
	factor_col = "factor_norm" if "factor_norm" in df.columns else "factor"
	norm_input_category = _normalize(input_category)
	norm_factors = [_normalize(f) for f in factors if _normalize(f)]
	if norm_input_category and category_col in df.columns:
		exact_match = df[df[category_col] == norm_input_category]
		if not exact_match.empty:
			return str(exact_match.iloc[0]["category"])

	best = None
	for category_value, group in df.groupby(category_col):
		category_name = str(group.iloc[0]["category"]) if not group.empty else str(category_value)
		cat_score = fuzzy_match_01(norm_input_category, str(category_value)) if norm_input_category else 0.0
		if matcher is not None:
			cat_score = max(cat_score, matcher.text_similarity(input_category, category_name))

		group_factors = group[factor_col].astype(str).tolist()
		factor_scores = []
		for factor in norm_factors:
			best_factor_score = 0.0
			for candidate_factor in group_factors:
				score = fuzzy_match_01(factor, candidate_factor)
				if score > best_factor_score:
					best_factor_score = score
				if best_factor_score >= 0.98:
					break
			if matcher is not None:
				best_factor_score = max(best_factor_score, matcher.category_profile_similarity(str(category_value), factor))
			if best_factor_score:
				factor_scores.append(best_factor_score)

		factor_score = sum(factor_scores) / len(factor_scores) if factor_scores else 0.0
		score = (0.55 * cat_score) + (0.45 * factor_score)
		if best is None or score > best[0]:
			best = (score, category_value)

	if not best:
		return input_category

	_, best_category_value = best
	if "category_norm" in df.columns:
		matched = df[df["category_norm"] == best_category_value]
		if not matched.empty:
			return matched.iloc[0]["category"]
	return str(best_category_value)


class SemanticMatcher:
	def __init__(self, df, model_name="sentence-transformers/all-MiniLM-L6-v2"):
		self.model_name = model_name
		self.model = _get_embedding_model(model_name)
		self.indices = {}
		self.global_entry = None
		self.category_profiles = {}
		self.bucket_profiles = {}
		self._build_indices(df)

	def _collect_text_values(self, group, columns):
		values = []
		seen = set()
		for column in columns:
			if column not in group.columns:
				continue
			for value in group[column].astype(str).tolist():
				clean_value = value.strip()
				key = _normalize(clean_value)
				if not clean_value or key in seen:
					continue
				seen.add(key)
				values.append(clean_value)
		return values

	def _top_examples(self, group, top_n=5):
		if group is None or group.empty:
			return []

		seen = set()
		examples = []
		for value in group["factor"].astype(str).tolist():
			clean_value = value.strip()
			key = _normalize(clean_value)
			if not clean_value or key in seen:
				continue
			seen.add(key)
			examples.append(clean_value)
			if len(examples) >= top_n:
				break
		return examples

	def _bucket_description(self, group, bucket_label, examples, top_categories):
		description_values = self._collect_text_values(
			group,
			(
				"bucket_description",
				"bucket_meaning",
				"description",
				"meaning",
				"notes",
			),
		)
		if description_values:
			return " ".join(description_values[:3])

		parts = [f"Bucket: {bucket_label}"]
		if top_categories:
			parts.append(f"Common categories: {', '.join(top_categories[:3])}")
		if examples:
			parts.append(f"Typical factors: {', '.join(examples[:5])}")
		return " | ".join(parts)

	def _build_index_entry(self, row_ids, texts):
		if not texts:
			return None

		embeddings = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
		vectors = np.asarray(embeddings, dtype=np.float32)
		if vectors.ndim != 2 or vectors.size == 0:
			return None

		index = faiss.IndexFlatIP(vectors.shape[1])
		index.add(vectors)
		return {"index": index, "row_ids": row_ids, "vectors": vectors}

	def _build_indices(self, df):
		if df is None or df.empty:
			return

		all_row_ids = []
		all_texts = []

		for category_norm, group in df.groupby("category_norm"):
			factors = group["factor_norm"].astype(str).tolist()
			entry = self._build_index_entry(group.index.to_list(), factors)
			if entry is None:
				continue

			self.indices[category_norm] = entry
			centroid = _normalize_vector(np.mean(entry["vectors"], axis=0))
			self.category_profiles[category_norm] = {
				"category": str(group.iloc[0]["category"]),
				"centroid": centroid,
				"count": int(len(group)),
			}

			all_row_ids.extend(group.index.to_list())
			all_texts.extend(factors)

		for bucket_norm, group in df.groupby("bucket_norm"):
			bucket_factors = group["factor_norm"].astype(str).tolist()
			entry = self._build_index_entry(group.index.to_list(), bucket_factors)
			if entry is None:
				continue

			examples = self._top_examples(group, top_n=5)
			category_counts = group["category"].astype(str).value_counts().to_dict()
			top_categories = list(category_counts.keys())[:3]
			signature_parts = [str(group.iloc[0]["bucket"])]
			if top_categories:
				signature_parts.append("categories: " + ", ".join(top_categories))
			if examples:
				signature_parts.append("examples: " + "; ".join(examples))
			description_text = self._bucket_description(group, str(group.iloc[0]["bucket"]), examples, top_categories)
			signature_text = " | ".join(signature_parts)

			centroid = _normalize_vector(np.mean(entry["vectors"], axis=0))
			self.bucket_profiles[bucket_norm] = {
				"bucket": str(group.iloc[0]["bucket"]),
				"centroid": centroid,
				"count": int(len(group)),
				"examples": examples,
				"top_categories": top_categories,
				"description": description_text,
				"signature_text": signature_text,
			}

		self.global_entry = self._build_index_entry(all_row_ids, all_texts)

	def _vector_for_text(self, text):
		return _get_embedding_vector(self.model_name, text)

	def text_similarity(self, left, right):
		fuzz_score = fuzzy_match_01(left, right)
		semantic_score = self.semantic_similarity(left, right)
		return max(0.0, min(1.0, (0.58 * fuzz_score) + (0.42 * semantic_score)))

	def semantic_similarity(self, left, right):
		left_vector = self._vector_for_text(left)
		right_vector = self._vector_for_text(right)
		if left_vector is None or right_vector is None:
			return 0.0
		return _score_from_cosine(float(np.dot(left_vector, right_vector)))

	def category_profile_similarity(self, category_norm, text):
		profile = self.category_profiles.get(_normalize(category_norm))
		if not profile:
			return 0.0
		text_vector = self._vector_for_text(text)
		if text_vector is None:
			return 0.0
		return _score_from_cosine(float(np.dot(text_vector, profile["centroid"])))

	def bucket_semantic_score(self, bucket, text):
		bucket_norm = _normalize(bucket)
		profile = self.bucket_profiles.get(bucket_norm)
		if not profile:
			return 0.0
		text_vector = self._vector_for_text(text)
		if text_vector is None:
			return 0.0
		label_similarity = self.text_similarity(text, profile["bucket"])
		centroid_similarity = _score_from_cosine(float(np.dot(text_vector, profile["centroid"])))
		signature_similarity = self.text_similarity(text, profile.get("signature_text", profile["bucket"]))
		description_similarity = self.text_similarity(text, profile.get("description", profile["bucket"]))
		return max(label_similarity, centroid_similarity, signature_similarity, description_similarity)

	def bucket_context(self, bucket):
		profile = self.bucket_profiles.get(_normalize(bucket))
		if not profile:
			return {
				"bucket": str(bucket).strip(),
				"examples": [],
				"top_categories": [],
				"count": 0,
				"signature_text": str(bucket).strip(),
			}
		return {
			"bucket": profile["bucket"],
			"examples": profile.get("examples", []),
			"top_categories": profile.get("top_categories", []),
			"count": profile.get("count", 0),
			"description": profile.get("description", profile.get("signature_text", profile["bucket"])),
			"signature_text": profile.get("signature_text", profile["bucket"]),
		}

	def _search_entry(self, entry, factor, top_k):
		query = _normalize(factor)
		if not query:
			return []

		q_cached = _get_query_embedding(self.model_name, query)
		q = np.asarray([q_cached], dtype=np.float32)
		k = min(top_k, len(entry["row_ids"]))
		if k <= 0:
			return []

		scores, idxs = entry["index"].search(q, k)
		results = []
		for score, idx in zip(scores[0], idxs[0]):
			if idx < 0:
				continue
			emb_score = max(0.0, min(1.0, (float(score) + 1.0) / 2.0))
			results.append({
				"row_id": entry["row_ids"][idx],
				"embedding_score": emb_score,
			})
		return results

	def search(self, category_norm, factor, top_k=10):
		results = []
		entry = self.indices.get(category_norm)
		if entry:
			results = self._search_entry(entry, factor, top_k)

		if self.global_entry is not None:
			global_results = self._search_entry(self.global_entry, factor, top_k)
			results = _merge_search_results(results, global_results)

		return results[:top_k]

	def search_any(self, factor, top_k=10):
		if self.global_entry is None:
			return []
		return self._search_entry(self.global_entry, factor, top_k)


def rerank_candidates(df, factor, candidates, preferred_bucket=None, input_category=None, matcher=None):
	bucket_counts = {}
	for item in candidates:
		row_id = item["row_id"]
		if row_id not in df.index:
			continue

		row = df.loc[row_id]
		bucket = str(row.get("bucket", "")).strip()
		if bucket:
			bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

	rows = []
	for item in candidates:
		row_id = item["row_id"]
		if row_id not in df.index:
			continue

		row = df.loc[row_id]
		bucket = str(row.get("bucket", "")).strip()
		fuzz_score = fuzzy_match_01(factor, row.get("factor", ""))
		embedding_score = float(item["embedding_score"])

		category_score = 0.0
		if input_category:
			if matcher is not None:
				category_score = matcher.text_similarity(input_category, row.get("category", ""))
			else:
				category_score = fuzzy_match_01(input_category, row.get("category", ""))

		bucket_semantic_score = 0.0
		bucket_context = {}
		if matcher is not None:
			bucket_semantic_score = matcher.bucket_semantic_score(bucket, factor)
			bucket_context = matcher.bucket_context(bucket)

		support_bonus = min(0.08, 0.02 * max(0, bucket_counts.get(bucket, 0) - 1))
		final_score = (0.48 * embedding_score) + (0.24 * fuzz_score) + (0.16 * bucket_semantic_score) + (0.12 * category_score) + support_bonus

		if preferred_bucket and bucket == preferred_bucket:
			final_score = min(1.0, final_score + 0.03)

		rows.append({
			"row": row,
			"embedding_score": embedding_score,
			"fuzz_score": fuzz_score,
			"category_score": category_score,
			"bucket_semantic_score": bucket_semantic_score,
			"bucket_context": bucket_context,
			"support_bonus": support_bonus,
			"final_score": final_score,
			"bucket": bucket,
		})

	rows.sort(key=lambda x: x["final_score"], reverse=True)
	return rows


def get_dominant_bucket(items: list[dict[str, Any]]):
	buckets = [str(item.get("bucket", "")).strip() for item in items if str(item.get("bucket", "")).strip()]
	if not buckets:
		return None
	counts = {}
	for bucket in buckets:
		counts[bucket] = counts.get(bucket, 0) + 1
	return max(counts.items(), key=lambda kv: kv[1])[0]
