from tiktokapipy.api import TikTokAPI
from TikTokApi import TikTokApi as tiktokCommentsAPI
import os
import json

def GetCreatorInformation(creator_obj):
    creator_info_dict = {}
    creator_info_dict["creator_id"] = creator_obj.id
    creator_info_dict["creator_username"] = creator_obj.nickname
    creator_info_dict["creator_is_verified"] = creator_obj.verified
    user_stats = creator_obj.stats
    creator_info_dict["follower_count"] = user_stats.follower_count
    creator_info_dict["following_count"] = user_stats.following_count
    creator_info_dict["heart_count"] = user_stats.heart_count
    creator_info_dict["video_count"] = user_stats.video_count
    creator_info_dict["digg_count"] = user_stats.digg_count
    return creator_info_dict

def GetLatestVideoInformationFromTag(tag_name, video_limit_num):
    with TikTokAPI() as api:
        challenge = api.challenge(tag_name, video_limit=video_limit_num)
        challenge.videos.sorted_by(lambda vid: vid.create_time)
        result = {}
        for video in challenge.videos:
            result["num_comments"] = video.stats.comment_count
            result["num_likes"] = video.stats.digg_count
            result["num_views"] = video.stats.play_count
            result["num_shares"] = video.stats.share_count
            result["video_created_time"] = video.create_time.strftime("%m/%d/%Y, %H:%M:%S")
            result["desc"] = video.desc
            result["video_id"] = video.id
            creator = video.creator()
            creator_info_dict = GetCreatorInformation(creator)
            result["creator_info"] = creator_info_dict
    return result

#add comments to the result -- to fix this as the API is not working so might need to web scrape
def AddCommentsFromVideos(result, comment_limit):
    #video_ids = [result["video_id"] for video in result]
    video_ids = ["7107272719166901550"]
    api = tiktokCommentsAPI()
    for video_id in video_ids:
        video = api.video(id=video_id)
        comment_list = []
        for comment in video.comments():
            comment_list.append(comment.text)
            if len(comment_list) == comment_limit:
                break
        result["comments"] = comment_list
    return result

#2 APIs are used: One to scrape video/creator information from hashtag and another to get comments
result = GetLatestVideoInformationFromTag(tag_name="makeup recommendations", video_limit_num=1)

#Output the data into json
dir = os.path.dirname(__file__)
filename = os.path.join(dir, 'data', 'tiktok_data.json')
with open(filename, "w") as write_file:
   json.dump(result, write_file, indent=4)