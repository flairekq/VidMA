from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from googleapiclient.discovery import build

import re
import json
import os
import datetime
import requests

#https://github.com/Benjamin-Loison/YouTube-operational-API -- set up your local host first

def parse_duration(duration):
    # Reference: https://www.thepythoncode.com/article/using-youtube-api-in-python
    # duration in the form of something like 'PT5H50M15S'
    # parsing it to be something like '5:50:15'
    if duration == None:
        return None
    parsed_duration = re.search(f"PT(\d+H)?(\d+M)?(\d+S)", duration).groups()
    duration_str = ""
    for d in parsed_duration:
        if d:
            duration_str += f"{d[:-1]}:"
    duration_str = duration_str.strip(":")
    return duration_str

def get_video_details(youtube, **kwargs):
    #Reference: https://www.thepythoncode.com/article/using-youtube-api-in-python
    try:
        # add additional video information using Youtube API
        video_response = youtube.videos().list(part="snippet,contentDetails,statistics",**kwargs).execute()

        items = video_response.get("items")[0]
        # get the snippet, statistics & content details & replies from the video response
        snippet = items["snippet"]
        statistics = items["statistics"]
        content_details = items["contentDetails"]

        result = {}
        result["channel_title"] = snippet["channelTitle"]
        result["title"] = snippet["title"]
        result["description"] = snippet["description"]
        result["publish time"] = snippet["publishedAt"]

        # get stats infos
        result["comment count"] = statistics["commentCount"]
        result["like count"] = statistics["likeCount"]
        result["view count"] = statistics["viewCount"]

        # get duration from content details
        result["duration"] = parse_duration(content_details["duration"])

        return result
    except:
        key_list = ["channel_title", "title", "description", "publish time", "comment count", "like count", "view count", "duration"]
        return dict.fromkeys(key_list, None)

def get_video_comments(youtube, result=[], token='', **kwargs):
    #Reference: https://www.geeksforgeeks.org/how-to-extract-youtube-comments-using-youtube-api-python/
    # retrieve youtube video results
    try:
        #extract a max of 50 comments per video
        if len(result) >= 50:
            return result
        video_response = youtube.commentThreads().list(part='snippet,replies',**kwargs).execute()
        for comment_thread in video_response['items']:
            # Extracting comments
            id = comment_thread['snippet']['topLevelComment']["id"]
            comment = comment_thread['snippet']['topLevelComment']['snippet']['textDisplay']
            likes = comment_thread['snippet']['topLevelComment']['snippet']["likeCount"]
            comment_dict = {"id":id, "comment": comment, "likes":likes}
            result.append(comment_dict)
        result = sorted(result, key=lambda comment_dict: comment_dict["likes"], reverse=True)
        if "nextPageToken" in video_response:
            return get_video_comments(youtube, result=result, token=video_response['nextPageToken'], **kwargs)
        else:
            return result
    except:
        return []

def get_english_transcript(video_id):
    list_of_eng_lang_codes = ['en', 'en-AU', 'en-CA', 'en-GB', 'en-IE', 'en-IN', 'en-NZ', 'en-US', 'en-ZA']
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = []
        for eng_code in list_of_eng_lang_codes:
            # the API defaults to en only but sometimes videos tag their transcript as 'en-GB' for e.g. but the api will throw error
            # because API only tries to find 'en' data
            try:
                transcript = transcript_list.find_transcript([eng_code]).fetch()
                if transcript == []:
                    continue
                else:
                    break
            except Exception as e:
                pass
    except Exception as e:
        pass
    # we will just skip the exceptions and return an empty transcript then check later if the transcript is empty

    return transcript

def get_youtube_data(video_ids, youtube_data_api):
    formatter = TextFormatter()
    unable_to_transcript_counter = 0
    final_result = {}
    for video_id in video_ids:
        # defaults to English and manually generated data
        transcript = get_english_transcript(video_id)
        if transcript == []:
            unable_to_transcript_counter += 1
            continue
        else:
            text = formatter.format_transcript(transcript)

            youtube_stats_dict = get_video_details(youtube_data_api, id=video_id)
            youtube_stats_dict["transcript_raw"] = transcript
            youtube_stats_dict["transcript_text"] = text

            first_page_comments_list = get_video_comments(youtube_data_api, videoId=video_id, order="relevance", textFormat="html")
            youtube_stats_dict["first_page_comments_list"] = first_page_comments_list

            final_result[video_id] = youtube_stats_dict

    print(f"There were {unable_to_transcript_counter} number of videos that transcripts couldn't be taken from. These videos were not added to the result")

    return final_result

"""
For getting chapter data -- require use of another API -- youtube operational API
"""

def get_data(api):
  response = requests.get(f"{api}")
  if response.status_code == 200:
    return response.json()
  else:
    return {}

def process_chapter_json(json_dict):
    if json_dict == {}:
        return []
    chapters = json_dict["items"][0]["chapters"]["chapters"]
    cleaned_chapter_list = []
    for chapter in chapters:
        title = chapter["title"]
        time_in_s = chapter["time"]
        time_in_min = round(time_in_s / 60,3)
        cleaned_chapter_list.append({"title":title, "time_in_min":time_in_min})
    return cleaned_chapter_list

def get_chapters_for_video_ids(youtube_json):
    api_template_str = "http://localhost/YouTube-operational-API/videos?part=chapters&id="
    for video_id_key in youtube_json:
        chapter_json_dict = get_data(api_template_str+video_id_key)
        chapter_list = process_chapter_json(chapter_json_dict)
        youtube_json[video_id_key]["chapters"] = chapter_list
    return youtube_json

def Get_SGT_Timestamp(datetime_obj):
  sgtTimeDelta =datetime.timedelta(hours=8)
  sgtTZObject = datetime.timezone(sgtTimeDelta, name="SGT")
  sgtTime = datetime_obj.replace(tzinfo=sgtTZObject)
  return sgtTime.isoformat()

#Define desired inputs into API
topic_id =  "/m/041xxh"
query_list = ['sephora makeup product review','makeup reviews','makeup recommendation','sephora review']
query = "|".join(set(query_list))

start_date_scraping = Get_SGT_Timestamp(datetime.datetime(2023, 3, 1))
end_date_scraping = Get_SGT_Timestamp(datetime.datetime(2023, 3, 22))

maximum_results_count = 50
output_json_filename = 'data/Mar23.json'

# API information
api_service_name = "youtube"
api_version = "v3"
developer_key = ""
youtube_data_api = build(api_service_name, api_version, developerKey=developer_key)

#Get relevant video IDs -- note that for both comments and search we can change the order
request = youtube_data_api.search().list(q=query,part='snippet',type='video', order="relevance",videoCaption="closedCaption", topicId=topic_id,publishedAfter=start_date_scraping,publishedBefore=end_date_scraping, maxResults=maximum_results_count)
res = request.execute()
video_ids = [item["id"]["videoId"] for item in res['items']]
print(f"There are {len(video_ids)} videos being extracted")

#Get data from video ids identified along with first page top comments (20)
result_dict = get_youtube_data(video_ids, youtube_data_api)
print(f"There are {len(result_dict)} videos extracted.Note that some values could be None e.g. no comments if comments were disabled.")

#Add chapter data
print("Extracting chapter data")
get_chapters_for_video_ids(result_dict)

print("Outputing data into JSON")
#Output the data into json
dir = os.path.dirname(__file__)
filename = os.path.join(dir, 'data', output_json_filename)
with open(filename, "w") as write_file:
   json.dump(result_dict, write_file, indent=4)

