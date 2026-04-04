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

	return df
