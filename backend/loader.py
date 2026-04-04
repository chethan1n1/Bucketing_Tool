import pandas as pd


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

	for col in ("category", "factor", "bucket"):
		df[col] = df[col].astype(str).str.strip()

	# Remove unusable rows to reduce ambiguous/empty outputs.
	df = df[(df["category"] != "") & (df["factor"] != "") & (df["bucket"] != "")].copy()

	# Canonical keys to support robust comparisons.
	df["category_norm"] = (
		df["category"]
		.astype(str)
		.str.lower()
		.str.replace("_", " ", regex=False)
		.str.replace(r"\s+", " ", regex=True)
		.str.strip()
	)
	df["factor_norm"] = (
		df["factor"]
		.astype(str)
		.str.lower()
		.str.replace("_", " ", regex=False)
		.str.replace(r"\s+", " ", regex=True)
		.str.strip()
	)
	df["bucket_norm"] = df["bucket"].astype(str).str.lower().str.strip()

	return df
