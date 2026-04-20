import pandas as pd
import re


def _normalize_key(value):
	value = str(value).lower().strip()
	value = value.replace("_", " ")
	value = re.sub(r"[^a-z0-9\s]", " ", value)
	value = re.sub(r"\s+", " ", value)
	return value


def load_data():
	df = pd.read_excel("data/Master_DB_Clean.xlsx")

	# Normalize
	df.columns = df.columns.str.lower()
	if "factor" not in df.columns and "factor_name" in df.columns:
		df = df.rename(columns={"factor_name": "factor"})
	if "bucket" not in df.columns and "factor_type" in df.columns:
		df = df.rename(columns={"factor_type": "bucket"})
	df = df.fillna("")

	# Ensure the required columns exist, then normalize them for matching.
	for col in ("category", "factor", "bucket"):
		if col not in df.columns:
			df[col] = ""

	# Optional semantic context columns that may exist in richer source files.
	for col in (
		"description",
		"bucket_description",
		"bucket_meaning",
		"factor_description",
		"notes",
		"meaning",
	):
		if col not in df.columns:
			df[col] = ""

	# Optional hierarchy columns used for grouped display and enterprise reporting.
	for col in ("subcategory", "hierarchy_level", "sort_order"):
		if col not in df.columns:
			df[col] = ""

	for col in ("category", "subcategory", "factor", "bucket"):
		df[col] = df[col].astype(str).str.strip()

	# Remove unusable rows to reduce ambiguous/empty outputs.
	df = df[(df["category"] != "") & (df["factor"] != "") & (df["bucket"] != "")].copy()

	# Canonical keys to support robust comparisons.
	df["category_norm"] = df["category"].map(_normalize_key)
	df["factor_norm"] = df["factor"].map(_normalize_key)
	df["bucket_norm"] = df["bucket"].map(_normalize_key)
	df["subcategory_norm"] = df["subcategory"].map(_normalize_key)

	return df
