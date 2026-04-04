import re

from rapidfuzz import fuzz


def _normalize(text):
	text = str(text).lower().strip()
	text = re.sub(r"[^a-z0-9\s]", " ", text)
	text = re.sub(r"\s+", " ", text)
	return text


def fuzzy_match(input_val, target):
	left = _normalize(input_val)
	right = _normalize(target)
	if not left or not right:
		return 0.0
	# token_set_ratio is less prone to accidental high scores than partial matching.
	return float(fuzz.token_set_ratio(left, right))


def find_best_match(df, category, factors):
	results = []

	for _, row in df.iterrows():
		category_score = fuzzy_match(category, str(row['category']))
		factor_scores = [fuzzy_match(f, str(row['factor'])) for f in factors]
		# Use all provided factors, not just the best single factor.
		factor_score = (sum(factor_scores) / len(factor_scores)) if factor_scores else 0.0

		total_score = category_score + factor_score
		results.append((total_score, category_score, factor_score, row))

	# Sort by score
	results.sort(key=lambda x: x[0], reverse=True)

	if not results:
		return 0.0, None, 0.0, 0.0

	best_score, best_category_score, best_factor_score, best_row = results[0]
	return best_score, best_row, best_category_score, best_factor_score
