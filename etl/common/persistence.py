from prefect import task
import pandas as pd

from etl.common import root_path

def parquet_path(filename):
   return str(root_path().joinpath("etl", "artifacts", filename))

@task
def df_to_parquet(df, filename_or_path):
   if "/" in filename_or_path:
      path = filename_or_path
   else:
      path = parquet_path(filename_or_path)
   return df.to_parquet(path)
  
@task
def parquet_to_df(filename_or_path):
   if "/" in filename_or_path:
      path = filename_or_path
   else:
      path = parquet_path(filename_or_path)
   return pd.read_parquet(path)
