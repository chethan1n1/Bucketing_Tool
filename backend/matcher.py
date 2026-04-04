import re
from collections import Counter

from rapidfuzz import fuzz


def _normalize(text):
	text = str(text).lower().strip()
	text = text.replace("_", " ")
	text = re.sub(r"[^a-z0-9\s]", " ", text)
	text = re.sub(r"\s+", " ", text)
	return text


def _tokenize(text):
	val = _normalize(text)
	return [token for token in val.split(" ") if token]


def fuzzy_match(input_val, target):
	left = _normalize(input_val)
	right = _normalize(target)
	if not left or not right:
		return 0.0
	if left == right:
		return 100.0

	# Weighted blend reduces false positives from subset matches like "service" vs
	# "superior personal service" while still handling word-order differences.
	ratio = float(fuzz.ratio(left, right))
	token_sort = float(fuzz.token_sort_ratio(left, right))
	token_set = float(fuzz.token_set_ratio(left, right))
	weighted = (0.5 * ratio) + (0.35 * token_sort) + (0.15 * token_set)

	left_tokens = set(_tokenize(left))
	right_tokens = set(_tokenize(right))
	common = left_tokens & right_tokens

	if not common:
		weighted *= 0.4

	# Penalize subset-only matches with large length mismatch.
	if (left_tokens.issubset(right_tokens) or right_tokens.issubset(left_tokens)) and abs(len(left_tokens) - len(right_tokens)) >= 2:
		weighted = min(weighted, 84.0)

	return max(0.0, min(100.0, weighted))


def infer_category(df, input_category, factors):
	if df is None or df.empty:
		return input_category

	category_col = "category_norm" if "category_norm" in df.columns else "category"
	factor_col = "factor_norm" if "factor_norm" in df.columns else "factor"

	norm_factors = [_normalize(f) for f in factors if _normalize(f)]
	if not norm_factors:
		return input_category

	norm_input_category = _normalize(input_category)
	best = None

	for category_value, group in df.groupby(category_col):
		group_factors = set(group[factor_col].astype(str).tolist())
		exact_hits = sum(1 for f in norm_factors if f in group_factors)
		category_alignment = fuzzy_match(norm_input_category, str(category_value)) if norm_input_category else 0.0
		score = (exact_hits * 35.0) + (0.8 * category_alignment)

		if best is None or score > best[0]:
			best = (score, category_value, exact_hits, category_alignment)

	if best is None:
		return input_category

	_, best_category_value, best_hits, best_alignment = best
	if best_hits >= 2 or best_alignment >= 70.0:
		if "category_norm" in df.columns:
			matched = df[df["category_norm"] == best_category_value]
			if not matched.empty:
				return matched.iloc[0]["category"]
		return str(best_category_value)

	return input_category


def get_dominant_bucket(buckets):
	clean = [str(b).strip() for b in buckets if str(b).strip()]
	if not clean:
		return None
	return Counter(clean).most_common(1)[0][0]


def find_best_match(df, category, factors, preferred_bucket=None):
	results = []
	if not factors:
		return 0.0, None, 0.0, 0.0

	category_col = "category" if "category" in df.columns else None
	bucket_col = "bucket" if "bucket" in df.columns else None
	factor_col = "factor" if "factor" in df.columns else None

	norm_category = _normalize(category)

	for _, row in df.iterrows():
		row_category = str(row[category_col]) if category_col else ""
		row_factor = str(row[factor_col]) if factor_col else ""
		row_bucket = str(row[bucket_col]) if bucket_col else ""

		category_score = fuzzy_match(norm_category, row_category) if norm_category else 0.0
		factor_scores = [fuzzy_match(f, row_factor) for f in factors]
		factor_score = (sum(factor_scores) / len(factor_scores)) if factor_scores else 0.0

		# Factor similarity should dominate. Category refines tie-breaks.
		total_score = (1.25 * factor_score) + (0.35 * category_score)

		if preferred_bucket and row_bucket == preferred_bucket:
			total_score += 6.0

		results.append((total_score, category_score, factor_score, row))

	results.sort(key=lambda x: x[0], reverse=True)

	if not results:
		return 0.0, None, 0.0, 0.0

	best_score, best_category_score, best_factor_score, best_row = results[0]
	return best_score, best_row, best_category_score, best_factor_score
