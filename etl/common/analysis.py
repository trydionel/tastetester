import numpy as np

def peak_year(ts):
  plays_by_year = ts.dt.year.value_counts()
  return np.average(plays_by_year.index.values, weights=plays_by_year.values).round()