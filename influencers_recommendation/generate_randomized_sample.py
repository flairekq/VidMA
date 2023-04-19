import pandas as pd
import os

def get_randomized_sample(input_filename, output_filename):
    df = pd.read_csv(input_filename)
    sample_size = 50
    sample = df.sample(n=sample_size)
    sample.to_csv(output_filename, index=False)

CURR_DIR = os.path.dirname(__file__)
start_date_str = "01-10-2022"
end_date_str = "31-12-2022"
input_filename = os.path.join(
    CURR_DIR, 'results', f'ranked_beauty_influencers_{start_date_str}_to_{end_date_str}.csv')
output_filename = os.path.join(
    CURR_DIR, 'results', f'ranked_beauty_influencers_{start_date_str}_to_{end_date_str}_randomized_sample.csv')
get_randomized_sample(input_filename, output_filename)