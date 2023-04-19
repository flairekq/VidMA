import sys
sys.path.append("./")
import config
from googleapiclient.discovery import build
import pandas as pd

class YouTubeDataAPIManagement:
    YOUTUBE_SEARCH_COST = 100
    YOUTUBE_READ_COST = 1
    QUOTA_PER_KEY = 10000
    def __init__(self):
        self.GOOGLE_API_SERVICE_NAME = "youtube"
        self.GOOGLE_API_VERSION = "v3"    
        self.usage_filename = "./general/youtube_api_usage.csv"
        self.current_youtube_api_key_index = 0
        self.current_total_cost = 0
        self.read_usage()
        self.youtube_data_api = build(self.GOOGLE_API_SERVICE_NAME, self.GOOGLE_API_VERSION,
                                developerKey=config.YOUTUBE_API_KEYS[self.current_youtube_api_key_index])
    
    def get_api(self):
        return self.youtube_data_api

    def read_usage(self):
        df = pd.read_csv(self.usage_filename)
        self.current_youtube_api_key_index = df["current_youtube_api_key_index"][0]
        self.current_total_cost = df["current_total_cost"][0]

    def save_usage(self):
        latest_usage = {"current_youtube_api_key_index": self.current_youtube_api_key_index, "current_total_cost": self.current_total_cost}
        df = pd.DataFrame(latest_usage, index=[0])
        df.to_csv(self.usage_filename, index=False)

    def check_quota_and_change_api_key_if_needed(self, cost):
        estimated_total_cost = self.current_total_cost + cost
        if estimated_total_cost <= YouTubeDataAPIManagement.QUOTA_PER_KEY:
            return self.youtube_data_api
        if self.current_youtube_api_key_index == len(config.YOUTUBE_API_KEYS) - 1:
            print("Hit full quota can't query anymore")
            return None
        # change API key and reset quota
        self.current_youtube_api_key_index += 1
        self.youtube_data_api = build(self.GOOGLE_API_SERVICE_NAME, self.GOOGLE_API_VERSION,
                                developerKey=config.YOUTUBE_API_KEYS[self.current_youtube_api_key_index])
        self.current_total_cost = 0
        print(f"changed api key to {config.YOUTUBE_API_KEYS[self.current_youtube_api_key_index]} (at index {self.current_youtube_api_key_index})")
        return self.youtube_data_api
    
    def use(self, cost):
        self.current_total_cost = self.current_total_cost + cost
        self.save_usage()
    
a = YouTubeDataAPIManagement()
a.check_quota_and_change_api_key_if_needed(10001)
a.use(YouTubeDataAPIManagement.YOUTUBE_SEARCH_COST)