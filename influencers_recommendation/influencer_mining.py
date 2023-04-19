import sys
sys.path.append("./")
from general.youtube_data_api_management import YouTubeDataAPIManagement
from googleapiclient.discovery import build
import googleapiclient.errors
import re
import json
import os
import requests
import datetime
from dateutil.relativedelta import relativedelta
import fasttext
import re
import nltk
from nltk import word_tokenize, sent_tokenize, pos_tag
from nltk import Tree
from nltk.corpus import stopwords
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import logging
import sys
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from operator import itemgetter as i
from functools import cmp_to_key

nltk.download('stopwords')
nltk.download('words')
nltk.download('maxent_ne_chunker')
nltk.download('averaged_perceptron_tagger')

class LoggerFilter(object):
    def __init__(self, level):
        self.__level = level

    def filter(self, logRecord):
        return logRecord.levelno <= self.__level

def remove_url(text):
    #regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
    # there was an issue with the original regex as it hangs for certain text due to catastrophic backtracking? 
    # referenced https://stackoverflow.com/questions/62578087/python-regex-matching-hangs-in-a-specific-string for solution
    regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))--> <--\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))--> <--\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
    removed_url_text = re.sub(regex, "", text)
    return removed_url_text


def remove_non_ascii(text):
    return re.sub(r'[^\x00-\x7F]+', ' ', text)


def clean_text(text):
    text = remove_url(text)
    text = text.replace(":", "")
    text = text.replace("*", "")
    text = text.replace("&", "and")
    text = remove_non_ascii(text)
    return text


def remove_keyword_from_text(text, keyword):
    # should also clean away channel's title !!
    # e.g., channel title: Olivia Loren The Makeup Princess #MYLIFEMYCHOICE, video_title: "KNOW THE DIFFERENCE BETWEEN SEX, GENDER, AND PRONOUNS!!||Olivia Loren The Makeup princess"
    hashtags = get_hashtags(keyword)
    for ht in hashtags:
        keyword = keyword.replace("#" + ht, "")
    keyword = keyword.strip()
    text = text.lower().replace(keyword.lower(), "")
    return text


def get_sentences(text):
    IS_REMOVE_STOP_WORDS = True
    IS_REMOVE_COMMA = True
    sentences = []
    chunks = sent_tokenize(text)
    stop_words = set(stopwords.words('english'))
    for c in chunks:
        chunk_sentences = c.split("\n")
        for s in chunk_sentences:
            if not IS_REMOVE_STOP_WORDS:
                sentences.append(s)
                continue
            words = word_tokenize(s)
            filtered_words = []
            for w in words:
                if w.lower() in stop_words:
                    continue
                if IS_REMOVE_COMMA:
                    if w == ",":
                        continue
                filtered_words.append(w)
            cleaned_sentence = " ".join(filtered_words)
            sentences.append(cleaned_sentence)
    return sentences


def get_beauty_lexicon():
    beauty_lexicon = []
    df = pd.read_csv("./influencers_recommendation/data/beauty_lexicon.csv")
    beauty_lexicon = df["Lexicon"].unique().tolist()
    return beauty_lexicon


def get_hashtags(text):
    tags = set({tag.strip("#") for tag in text.replace(
        '#', ' #').split() if tag.startswith("#")})
    return list(tags)


def get_words_of_interest_from_text(text):
    words_of_interest = []
    text = clean_text(text)
    sentences = get_sentences(text)
    for sentence in sentences:
        if sentence == "":
            continue
        words_of_interest.extend(
            get_words_of_interest_with_syntax_rules(sentence))
    return words_of_interest


def get_words_of_interest_with_syntax_rules(text):
    words_of_interest = []
    words = nltk.word_tokenize(text)
    tagged = nltk.pos_tag(words)

    keep_pos_lst = ["NN", "NNP", "NNS", "NNPS",
                    "JJ", "JJS", "JJR", "VBZ", "VB"]
    """ V3 - Avoid extracting singular words from a noun phrase """
    for i in range(len(tagged)):
        current_token = tagged[i][0]
        current_token_pos = tagged[i][1]
        if len(current_token) == 1 or current_token_pos not in keep_pos_lst:
            continue

        # final word among tokens
        if i == len(tagged) - 1 and i > 0:
            # get the word before it and check if it's also one of a keep_pos
            previous_token_pos = tagged[i-1][1]
            if current_token_pos in keep_pos_lst and previous_token_pos in keep_pos_lst:
                continue
        elif i < len(tagged) - 1:
            # get the word after it and check if it's also one of a keep_pos
            next_token_pos = tagged[i+1][1]
            if current_token_pos in keep_pos_lst and next_token_pos in keep_pos_lst:
                continue
        words_of_interest.append(current_token)

    chunk_name = "NP"
    rule = r""" NP:
            {<NN|NNS|NNP|NNPS>*<NN|VBZ|DT|JJ|JJS|JJR|NNS|NNP|NNPS|CC|VBD|RB>+<NN|NNS|NNP|NNPS>}
        """
    chunk_parser = nltk.RegexpParser(rule)
    tree = chunk_parser.parse(tagged)
    noun_phrases = []
    for subtree in tree.subtrees(filter=lambda t: t.label() == chunk_name):
        phrase = ''
        for item in subtree.leaves():
            phrase += ' ' + item[0]
        noun_phrases.append(phrase.strip())
    noun_phrases = list(filter(lambda x: len(x.split()) > 1, noun_phrases))
    words_of_interest.extend(noun_phrases)

    return words_of_interest


def read_brand_name_lexicon(filepath_1, filepath_2):
    brand_name_lexicon_list = []
    df = pd.read_csv(filepath_1)
    brand_name_lexicon_list = df["Brand"].unique().tolist()
    df = pd.read_csv(filepath_2)
    brand_name_lexicon_list.extend(df["Brand"].unique().tolist())
    for i in range(0, len(brand_name_lexicon_list)):
        brand_name_lexicon_list[i] = brand_name_lexicon_list[i].lower()
    return brand_name_lexicon_list


def is_url_exists(url):
    try:
        if "http" not in url:
            url = "https://" + url
        response = requests.head(url, timeout=5)
        return response.status_code < 400
    except Exception as e:
        return False


def get_product_categories_and_lexicon():
    filename = "./influencers_recommendation/data/product_category_lexicon.json"
    product_categories = {}
    with open(filename) as file:
        product_categories = json.load(file)
    product_categories_lexicon = []
    for cat in product_categories:
        product_categories_lexicon.extend(product_categories[cat])
        product_categories[cat] = set(product_categories[cat])
    return product_categories, product_categories_lexicon


def get_brand_categories_and_lexicon():
    filename = "./influencers_recommendation/data/brand_category_lexicon.json"
    brand_categories = {}
    with open(filename) as file:
        brand_categories = json.load(file)
    brand_categories_lexicon = []
    for cat in brand_categories:
        brand_categories[cat] = [l.lower() for l in brand_categories[cat]]
        brand_categories_lexicon.extend(brand_categories[cat])
        brand_categories[cat] = set(brand_categories[cat])
    brand_categories_lexicon_only_extract_once = set(pd.read_csv(
        "./influencers_recommendation/data/brand_category_lexicon_only_extract_once.csv")["Lexicon"].unique())
    return brand_categories, brand_categories_lexicon, brand_categories_lexicon_only_extract_once


def get_unique_words_of_interest(words_of_interest):
    unique_woi_in_lowercase = set()
    unique_woi = []
    for woi in words_of_interest:
        woi_in_lowercase = woi.strip().lower()
        if woi_in_lowercase not in unique_woi_in_lowercase:
            unique_woi_in_lowercase.add(woi_in_lowercase)
            unique_woi.append(woi)
    return unique_woi


def get_overall_sentiment(overall_sentiment_score):
    # Compound ranges from -1 to 1 and is the metric used to draw the overall sentiment
    # positive if compound >= 0.5
    # neutral if -0.5 < compount < 0.5
    # negative if -0.5 >= compound
    if overall_sentiment_score >= 0.5:
        return 'Positive'
    elif overall_sentiment_score <= -0.5:
        return "Negative"
    else:
        return "Neutral"


def get_search_terms():
    search_terms = []
    df = pd.read_csv("./influencers_recommendation/data/search_keywords.csv")
    search_terms = df["Keywords"].unique().tolist()
    return search_terms

def get_current_time_str():
    now = datetime.datetime.now()
    time_str = now.strftime("%H:%M:%S")
    return time_str


# returns the language code e.g. 'en' for English
def detect_language(text):
    predictions = fmodel.predict(text)
    detected_lang = re.sub("__label__", "", predictions[0][0])
    return detected_lang


def is_video_in_eng(title, desc):
    try:
        if title != "" and detect_language(title) == 'en':
            return True
    except:
        pass
    try:
        if desc != "" and detect_language(desc) == 'en':
            return True
    except:
        pass
    return False


def get_dates(start_date_str, end_date_str=""):
    dates = []
    current_date = datetime.datetime.strptime(start_date_str, "%d-%m-%Y")
    end_date = datetime.datetime.strptime(end_date_str, "%d-%m-%Y")
    dates.append([current_date.strftime("%Y-%m-%d") + "T00:00:00Z",
                 current_date.strftime("%Y-%m-%d") + "T23:59:59Z"])

    if current_date == end_date:
        return dates

    while True:
        current_date = current_date + datetime.timedelta(days=1)
        dates.append([current_date.strftime("%Y-%m-%d") + "T00:00:00Z",
                     current_date.strftime("%Y-%m-%d") + "T23:59:59Z"])
        if current_date == end_date:
            break
    return dates


# constants or initial values
youtube_data_api_management = YouTubeDataAPIManagement()

# language detection model 
# download model from https://fasttext.cc/docs/en/language-identification.html and put into project folder before executing the codes
PATH_TO_PRETRAINED_LANG_MODEL = 'lid.176.bin'
fmodel = fasttext.load_model(PATH_TO_PRETRAINED_LANG_MODEL)

CURR_DIR = os.path.dirname(__file__)

BRAND_NAME_LEXICON_FILEPATH_1 = "./influencers_recommendation/data/brand_lexicon_scraped_sephora.csv"
BRAND_NAME_LEXICON_FILEPATH_2 = "./influencers_recommendation/data/collated_brands.csv"
brand_name_lexicon_list = read_brand_name_lexicon(BRAND_NAME_LEXICON_FILEPATH_1, BRAND_NAME_LEXICON_FILEPATH_2)
brand_name_lexicon_set = set(brand_name_lexicon_list)
brands_desc_lexicon = {"our shop", "our store", "shop", "shop at our website", "founder", "brand", "company", "I sell", "we sell", "bazaar", "our products",
                       "my business", "my company", "our company", "our business", "our merchandise", "selling merchandise", "our items", "customers", "launch in", "launched in", "ceo"}
brand_phrases_to_exclude_lexicon = {"brand partnership", "brand collaboration",
                                    "collaboration with our brand", "partnership with our brand", "brand new", "brand enquiries", "brand deals"}
BRAND_NAME_SIMILARITY_THRESHOLD = 92

to_exclude_domains = ["google", "facebook", "instagram", "twitter", "reddit", "linkedin", "snapchat", "pinterest", "pin.it", "tiktok", "youtube", "mcsaatchisocial",
                      "gmail", "outlook", "hotmail", "yahoo", "vidunit", "bilibili", "eventbrite", "patreon", "linktr", "linktr.ee", "anchor.fm", "throne.me", "soundcloud", "spotify"]
# domains_of_lower_priority = ["shopify", "spreadshop"]
email_regex = r"[\w\.]+@([\w-]+\.)+[\w-]{2,20}"
url_regex = r"\b((?:https?://)?(?:(?:www\.)?(?:[\da-z\.-]+)\.(?:[a-z]{2,6})|(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)|(?:(?:[0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,7}:|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}|(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:(?:(?::[0-9a-fA-F]{1,4}){1,6})|:(?:(?::[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(?::[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(?:ffff(?::0{1,4}){0,1}:){0,1}(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])|(?:[0-9a-fA-F]{1,4}:){1,4}:(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])))(?::[0-9]{1,4}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])?(?:/[\w\.-]*)*/?)\b"

NO_OF_RECENT_VIDEOS_REQUIRED = 10

beauty_lexicon = get_beauty_lexicon()
product_categories, product_categories_lexicon = get_product_categories_and_lexicon()
brand_categories, brand_categories_lexicon, brand_categories_lexicon_only_extract_once = get_brand_categories_and_lexicon()

IS_GET_CHANNELS = True
IS_GET_ACTIVE_INFLUENCERS = True
IS_GET_BEAUTY_INFLUENCERS = True
IS_CATEGORIZE_BEAUTY_INFLUENCERS = True
IS_ANALYZE_BEAUTY_INFLUENCERS = True
IS_RANK_INFLUENCERS = True

logger = logging.getLogger()


"""6 tasks to identify influencers and recommend top 10 for each makeup product category"""
# task 1 - get influential channels
# published_after and published_before uses format of (ISO-8601) YYYY-MM-DDThh:mm:ssZ
def get_channels(search_keyword, published_after="", published_before="", video_duration="any", channels={}, filtered_away_channels={}):
    logger.info(
        f"{get_current_time_str()}: get channels for published_after:{published_after} and published_before:{published_before} for search_keyword:{search_keyword}")

    youtube_data_api = youtube_data_api_management.check_quota_and_change_api_key_if_needed(YouTubeDataAPIManagement.YOUTUBE_SEARCH_COST)
    request = youtube_data_api.search().list(q=search_keyword, part='snippet',
                                             type='video', videoCaption="any", videoDuration=video_duration, maxResults=50)
    if published_after != "" and published_before != "":
        request = youtube_data_api.search().list(q=search_keyword, part="snippet", type="video",
                                                 videoCaption="any", videoDuration=video_duration, maxResults=50, publishedAfter=published_after, publishedBefore=published_before)
    elif published_after != "":
        request = youtube_data_api.search().list(q=search_keyword, part="snippet", type="video",
                                                 videoCaption="any", videoDuration=video_duration, maxResults=50, publishedAfter=published_after)
    elif published_before != "":
        request = youtube_data_api.search().list(q=search_keyword, part="snippet", type="video",
                                                 videoCaption="any", videoDuration=video_duration, maxResults=50, publishedBefore=published_before)
    try:
        res = request.execute()
        youtube_data_api_management.use(YouTubeDataAPIManagement.YOUTUBE_SEARCH_COST)
    except googleapiclient.errors.HttpError as e:
        if e.error_details[0]["reason"] != "quotaExceeded":
            return channels, filtered_away_channels
        youtube_data_api = youtube_data_api_management.check_quota_and_change_api_key_if_needed(YouTubeDataAPIManagement.QUOTA_PER_KEY + 1)
        
        request = youtube_data_api.search().list(q=search_keyword, part='snippet',
                                             type='video', videoCaption="any", videoDuration=video_duration, maxResults=50)
        if published_after != "" and published_before != "":
            request = youtube_data_api.search().list(q=search_keyword, part="snippet", type="video",
                                                    videoCaption="any", videoDuration=video_duration, maxResults=50, publishedAfter=published_after, publishedBefore=published_before)
        elif published_after != "":
            request = youtube_data_api.search().list(q=search_keyword, part="snippet", type="video",
                                                    videoCaption="any", videoDuration=video_duration, maxResults=50, publishedAfter=published_after)
        elif published_before != "":
            request = youtube_data_api.search().list(q=search_keyword, part="snippet", type="video",
                                                    videoCaption="any", videoDuration=video_duration, maxResults=50, publishedBefore=published_before)
        res = request.execute()
        youtube_data_api_management.use(YouTubeDataAPIManagement.YOUTUBE_SEARCH_COST)

    count = 0
    no_of_non_eng_videos = 0
    no_of_ineligible_channels = 0
    no_of_brand_channel = 0
    # no_of_potential_brand_channel = 0
    no_of_videos = len(res["items"])
    logger.info(f"There are a total of {no_of_videos} videos searched")
    for item in res["items"]:
        channel_id = item["snippet"]["channelId"]
        # check whether encountered the current channel before
        # if yes --> continue to next video
        if channels.get(channel_id) != None or filtered_away_channels.get(channel_id) != None:
            continue

        # filter away videos that are not in english
        is_eng = is_video_in_eng(
            item["snippet"]["title"], item["snippet"]["description"])
        if not is_eng:
            logger.info(
                f'video with id: {item["id"]["videoId"]} is non-english')
            no_of_non_eng_videos += 1
            continue

        searched_video_details = {
            "video_id": item["id"]["videoId"],
            "video_title": item["snippet"]["title"],
            "video_description": item["snippet"]["description"]
        }

        # filter away channels that are not eligible for verificiation, or does not have at least 10 videos
        # (Youtube must reach at least 100,000 subscriptions to be eligible to apply for verification)
        # https://support.google.com/youtube/answer/3046484?hl=en#:~:text=Verified%20channel%20eligibility,entity%20it%20claims%20to%20be
        min_subscriber_count = 100000
        # must meet at least the min. video count as we will be analyzing the top 10 videos in the next step of filtration
        min_video_count = 10
        youtube_data_api = youtube_data_api_management.check_quota_and_change_api_key_if_needed(YouTubeDataAPIManagement.YOUTUBE_READ_COST)
        # youtube_data_api = check_quota_and_change_api_key_if_needed(
        #     current_total_cost + YOUTUBE_READ_COST)
        # query for channel's details
        part = "snippet,statistics,status,topicDetails,brandingSettings"
        request = youtube_data_api.channels().list(id=channel_id, part=part)
        try:
            res = request.execute()
            # current_total_cost += YOUTUBE_READ_COST
            youtube_data_api_management.use(YouTubeDataAPIManagement.YOUTUBE_READ_COST)
        except googleapiclient.errors.HttpError as e:
            if e.error_details[0]["reason"] != "quotaExceeded":
                continue
            youtube_data_api = youtube_data_api_management.check_quota_and_change_api_key_if_needed(YouTubeDataAPIManagement.QUOTA_PER_KEY + 1)
            res = request.execute()
            youtube_data_api_management.use(YouTubeDataAPIManagement.YOUTUBE_READ_COST)

        if (len(res["items"]) == 0):
            logger.info(
                f"Can't find details about channel with id: {channel_id}")
            continue
        item = res["items"][0]

        channel_details = {"snippet": item["snippet"],
                           "statistics": item["statistics"],
                           "status": item["status"]}
        if item.get("topicDetails") != None:
            channel_details["topic_details"] = item["topicDetails"]
        if item.get("brandingSettings") != None:
            channel_details["branding_settings"] = item["brandingSettings"]

        if not (int(channel_details["statistics"]["subscriberCount"]) >= min_subscriber_count and int(channel_details["statistics"]["videoCount"]) >= min_video_count):
            logger.info(
                f"channel with id: {channel_id} is ineligible for verification and/or does not meet min. video count")
            no_of_ineligible_channels += 1
            filtered_away_channels[channel_id] = True
            continue

        channel_title = channel_details["snippet"]["title"]
        channel_desc = channel_details["snippet"]["description"]
        channel_desc = channel_desc.lower()


        # filter away channels that are makeup/beauty related brand via channel's title
        # check against the brands name lexicon set first (avg O(1)) retrieval
        if channel_title in brand_name_lexicon_set:
            logger.info(
                f"channel with id: {channel_id}, title: {channel_title} is a brand/company based on channel's title")
            no_of_brand_channel += 1
            filtered_away_channels[channel_id] = True
            continue
        is_brand = False
        # then check against the brands name lexicon list via fuzzywuzzy string matching
        for brand_name in brand_name_lexicon_list:
            ratio = fuzz.partial_ratio(
                channel_title.lower(), brand_name.lower())
            if ratio < BRAND_NAME_SIMILARITY_THRESHOLD:
                continue
            logger.info(
                f"channel with id: {channel_id}, title: {channel_title} is a brand/company based on channel's title being similar with {brand_name}")
            no_of_brand_channel += 1
            is_brand = True
            break
        if is_brand:
            filtered_away_channels[channel_id] = True
            continue
        # then check for potential brand url in channel's description
        channel_desc = re.sub(email_regex, "", channel_desc)
        url_matches = re.findall(url_regex, channel_desc)
        # is_potential_brand = False
        for url_match in url_matches:
            is_excluded_link = False
            # check if this is a link to be excluded from filtering
            for d in to_exclude_domains:
                exclude_domain_match = re.search(r'' + d, url_match)
                if exclude_domain_match != None:
                    is_excluded_link = True
                    break
            if is_excluded_link:
                continue

            # check if it's a valid link
            is_valid_link = is_url_exists(url_match)
            if not is_valid_link:
                continue

            # # check if the link is part of a domain that has lower priority
            # for d in domains_of_lower_priority:
            #     lower_priority_domain_match = re.search(r'' + d, url_match)
            #     if lower_priority_domain_match != None:
            #         is_potential_brand = True
            #         break

            # if is_potential_brand:
            #     logger.info(
            #         f"channel with id: {channel_id}, title: {channel_title} might be a brand/company based on {url_match}")
            #     no_of_potential_brand_channel += 1
            #     continue

            logger.info(
                f"channel with id: {channel_id}, title: {channel_title} is a brand/company based on {url_match}")
            no_of_brand_channel += 1
            break
        if is_brand:
            filtered_away_channels[channel_id] = True
            continue

        # then check against other aspects of the channel's description
        for bdl in brands_desc_lexicon:
            match = re.search(r'(?<!\S)\b' + bdl + r'(?![\w-])', channel_desc)
            if match == None:
                continue
            is_brand = True

            if bdl == "brand":
                # check if the brand is for "brand partnership" (or other synonym)
                for bpl in brand_phrases_to_exclude_lexicon:
                    bpl_match = re.search(
                        r'\b' + bpl + r'(?![\w-])', channel_desc)
                    if bpl_match != None:
                        is_brand = False
                        break
            if is_brand:
                logger.info(
                    f"channel with id: {channel_id}, title: {channel_title} is a brand/company based on {match.group()} matching lexicon: {bdl}")
                no_of_brand_channel += 1
                break
        if is_brand:
            filtered_away_channels[channel_id] = True
            continue

        # pass all filters
        # channels[channel_id] = {"is_potential_brand": is_potential_brand, "searched_video_details": searched_video_details, "channel_details": channel_details}
        channels[channel_id] = {"searched_video_details": searched_video_details, "channel_details": channel_details}

        count += 1

    logger.info(
        f"There are {no_of_non_eng_videos} non english videos being filtered away")
    logger.info(
        f"There are {no_of_ineligible_channels} ineligible channels being filtered away")
    logger.info(
        f"There are {no_of_brand_channel} brand channels being filtered away")
    # logger.info(
    #     f"There are {no_of_potential_brand_channel} channels that might be a brand/company")
    logger.info(f"There are a remaining of {count} channels being extracted")
    logger.info("\n")
    return channels, filtered_away_channels

# task 2 - filter away non-active influencers
def get_active_influencers(channels, active_influencers, valid_start_date, filtered_away_channels={}):
    no_of_videos_with_tags = 0
    no_of_active_influencers = 0
    for channel_id in channels:
        if active_influencers.get(channel_id) != None or filtered_away_channels.get(channel_id) != None:
            continue

        # get the channel's uploads
        playlist_id = channel_id[0] + "U" + channel_id[2:]
        youtube_data_api = youtube_data_api_management.check_quota_and_change_api_key_if_needed(YouTubeDataAPIManagement.YOUTUBE_READ_COST)
        request = youtube_data_api.playlistItems().list(
            playlistId=playlist_id, maxResults=50, part="snippet,contentDetails")
        try:
            res = request.execute()
            youtube_data_api_management.use(YouTubeDataAPIManagement.YOUTUBE_READ_COST)
        except googleapiclient.errors.HttpError as e:
            if e.error_details[0]["reason"] != "quotaExceeded":
                continue
            youtube_data_api = youtube_data_api_management.check_quota_and_change_api_key_if_needed(YouTubeDataAPIManagement.QUOTA_PER_KEY + 1)
            res = request.execute()
            youtube_data_api_management.use(YouTubeDataAPIManagement.YOUTUBE_READ_COST)

        recent_videos = []
        for video in res["items"]:
            # filter away videos that are not in english
            is_eng = is_video_in_eng(
                video["snippet"]["title"], video["snippet"]["description"])
            if not is_eng:
                continue

            # check that the video's published date is within the recent period
            published_date = datetime.datetime.strptime(
                video["contentDetails"]["videoPublishedAt"], "%Y-%m-%dT%H:%M:%SZ")
            if published_date.date() >= valid_start_date.date():
                recent_videos.append(video["contentDetails"]["videoId"])

            if len(recent_videos) == NO_OF_RECENT_VIDEOS_REQUIRED:
                break

        if len(recent_videos) != NO_OF_RECENT_VIDEOS_REQUIRED:
            logger.info(
                f"channel with id: {channel_id}, title: {channels[channel_id]['channel_details']['snippet']['title']} is an inactive/non-english channel")
            filtered_away_channels[channel_id] = True
            continue

        no_of_active_influencers += 1

        # get the top 10 most recent english videos' details
        youtube_data_api = youtube_data_api_management.check_quota_and_change_api_key_if_needed(YouTubeDataAPIManagement.YOUTUBE_READ_COST)
        part = "snippet,localizations,statistics,topicDetails"
        request = youtube_data_api.videos().list(
            part=part, id=','.join(recent_videos), maxResults=50)
        try:
            res = request.execute()
            youtube_data_api_management.use(YouTubeDataAPIManagement.YOUTUBE_READ_COST)
        except googleapiclient.errors.HttpError as e:
            if e.error_details[0]["reason"] != "quotaExceeded":
                continue
            youtube_data_api = youtube_data_api_management.check_quota_and_change_api_key_if_needed(YouTubeDataAPIManagement.YOUTUBE_READ_COST)
            res = request.execute()
            youtube_data_api_management.use(YouTubeDataAPIManagement.YOUTUBE_READ_COST)

        for video_details in res["items"]:
            tags = video_details["snippet"].get("tags")
            if tags != None and len(tags) > 0:
                no_of_videos_with_tags += 1

        active_influencers[channel_id] = {"channel_title": channels[channel_id]
                                          ["channel_details"]["snippet"]["title"], "top_recent_videos": res["items"]}

    logger.info(
        f"There are {no_of_active_influencers} active channels/influencers extracted")
    logger.info(
        f"There are {no_of_videos_with_tags}/{NO_OF_RECENT_VIDEOS_REQUIRED * no_of_active_influencers} videos with tags")
    logger.info("\n")
    return active_influencers, filtered_away_channels

# task 3 - filter away non-beauty influencers 
def get_beauty_influencers(active_influencers, influencers, filtered_away_channels={}):
    no_of_non_beauty_influencers = 0
    no_of_beauty_influencers = 0
    percentage_of_beauty_videos_required = 0.6

    BEAUTY_SIMILARITY_THRESHOLD = 90
    count = 1
    no_of_active_influencers = len(active_influencers)
    for channel_id in active_influencers:
        logger.info(
            f"checking {count}/{no_of_active_influencers} - channel's id: {channel_id}")
        count += 1

        if filtered_away_channels.get(channel_id) != None:
            continue

        channel_title = active_influencers[channel_id]['channel_title']
        no_of_beauty_videos = 0
        beauty_videos = []
        non_beauty_videos = []
        for video in active_influencers[channel_id]["top_recent_videos"]:
            video_title = video["snippet"]["title"]
            video_title = remove_keyword_from_text(video_title, channel_title)
            video_desc = video["snippet"]["description"]
            video_desc = remove_keyword_from_text(video_desc, channel_title)

            words_of_interest = get_words_of_interest_from_text(video_title)
            words_of_interest.extend(
                get_words_of_interest_from_text(video_desc))
            video_tags = video["snippet"].get("tags")

            video["is_a_beauty_video"] = False
            min_length_of_beauty_lexicon = len(min(beauty_lexicon, key=len))
            for woi in words_of_interest:
                if len(woi) < min_length_of_beauty_lexicon:
                    continue
                extracted = process.extractOne(woi, [bl.strip() for i, bl in enumerate(
                    beauty_lexicon) if len(woi) >= len(bl.strip())], scorer=fuzz.WRatio)
                if extracted == None or extracted[1] < BEAUTY_SIMILARITY_THRESHOLD:
                    continue
                video["identified_by"] = f"{woi} might be under {extracted[0]} (confidence of {extracted[1]})"
                video["is_a_beauty_video"] = True
                no_of_beauty_videos += 1
                break

            video_details_to_extract = {"id": video["id"], "is_a_beauty_video": video["is_a_beauty_video"], "published_at": video["snippet"]
                                        ["publishedAt"], "title": video["snippet"]["title"], "description": video["snippet"]["description"],
                                        "tags": [], "statistics": video["statistics"]}
            if video_tags != None and len(video_tags) > 0:
                video_details_to_extract["tags"] = video_tags

            if video["is_a_beauty_video"]:
                video_details_to_extract["identified_by"] = video["identified_by"]
                beauty_videos.append(video_details_to_extract)
            else:
                non_beauty_videos.append(video_details_to_extract)

        percentage_of_beauty_videos = no_of_beauty_videos / \
            len(active_influencers[channel_id]["top_recent_videos"])

        influencer = {"channel_title": channel_title, "is_beauty_influencer": False, "recent_beauty_videos": {
            "count": len(beauty_videos), "videos": beauty_videos}, "recent_non_beauty_videos": {"count": len(non_beauty_videos), "videos": non_beauty_videos}}

        if percentage_of_beauty_videos < percentage_of_beauty_videos_required:
            no_of_non_beauty_influencers += 1
            filtered_away_channels[channel_id] = True
            if influencers.get("non_beauty_influencers") != None:
                influencers["non_beauty_influencers"][channel_id] = influencer
            else:
                influencers["non_beauty_influencers"] = {
                    channel_id: influencer}
            logger.info(
                f"channel with id: {channel_id}, title: {channel_title} is not a beauty influencer")
            continue

        no_of_beauty_influencers += 1
        influencer["is_beauty_influencer"] = True
        if influencers.get("beauty_influencers") != None:
            influencers["beauty_influencers"][channel_id] = influencer
        else:
            influencers["beauty_influencers"] = {channel_id: influencer}
    logger.info(
        f"There are {no_of_non_beauty_influencers} non-beauty influencers being filtered away")
    logger.info(
        f"There are {no_of_beauty_influencers} beauty influencers extracted")
    return influencers, filtered_away_channels

# helper function to extract product categories from words of interest
def extract_product_categories(lexicon, woi, woi_in_lowercase, channel_identified_product_categories, woi_identified_product_categories, total_of_product_categories_count, video):
    lexicon_match = re.search(
        r'(?<!\S)\b' + lexicon + r'(?![\w-])', woi_in_lowercase)
    if lexicon_match == None:
        return

    extracted_category = ""
    for cat in product_categories:
        if lexicon in product_categories[cat]:
            extracted_category = cat
            break

    if channel_identified_product_categories.get(extracted_category) == None:
        channel_identified_product_categories[extracted_category] = 1
        woi_identified_product_categories[extracted_category] = 1
        total_of_product_categories_count += 1
    elif woi_identified_product_categories.get(extracted_category) == None:
        channel_identified_product_categories[extracted_category] += 1
        total_of_product_categories_count += 1

    if video["identified_product_categories"].get(extracted_category) == None:
        video["identified_product_categories"][extracted_category] = [
            {"woi": woi, "lexicon_matched": lexicon}]
    elif woi_identified_product_categories.get(extracted_category) == None:
        video["identified_product_categories"][extracted_category].append(
            {"woi": woi, "lexicon_matched": lexicon})
    woi_identified_product_categories[extracted_category] = 1
    return [channel_identified_product_categories, total_of_product_categories_count, woi_identified_product_categories, video]

# helper function to extract brand categories from words of interest
def extract_brand_categories(lexicon, woi, no_of_tokens_in_woi, is_tag, woi_in_lowercase, channel_identified_brand_categories, total_of_brand_categories_count, woi_identified_brand_categories, video):
    if not is_tag and no_of_tokens_in_woi == 1:
        return
    elif is_tag and woi == "fresh":
        return

    lexicon_match = re.search(
        r'(?<!\S)\b' + lexicon + r'(?![\w-])', woi_in_lowercase)
    if lexicon_match == None:
        return
    extracted_category = ""
    for cat in brand_categories:
        if lexicon in brand_categories[cat]:
            extracted_category = cat
            break

    if channel_identified_brand_categories.get(extracted_category) == None:
        channel_identified_brand_categories[extracted_category] = 1
        woi_identified_brand_categories[extracted_category] = 1
        total_of_brand_categories_count += 1
    elif woi_identified_brand_categories.get(extracted_category) == None:
        channel_identified_brand_categories[extracted_category] += 1
        total_of_brand_categories_count += 1

    if video["identified_brand_categories"].get(extracted_category) == None:
        video["identified_brand_categories"][extracted_category] = [
            {"woi": woi, "lexicon_matched": lexicon}]
    elif lexicon not in brand_categories_lexicon_only_extract_once and woi_identified_brand_categories.get(extracted_category) == None:
        video["identified_brand_categories"][extracted_category].append(
            {"woi": woi, "lexicon_matched": lexicon})
    woi_identified_brand_categories[extracted_category] = 1
    return [channel_identified_brand_categories, total_of_brand_categories_count, woi_identified_brand_categories, video]

# task 4 - categorize beauty influencers by product and brand categories
def categorize_beauty_influencers(beauty_influencers):
    count = 1
    no_of_beauty_influencers = len(beauty_influencers)
    for channel_id in beauty_influencers:
        channel_title = beauty_influencers[channel_id]["channel_title"]
        logger.info(
            f"processing {count}/{no_of_beauty_influencers} - channel's id: {channel_id}, channel's title: {channel_title}")
        beauty_videos = beauty_influencers[channel_id]["recent_beauty_videos"]["videos"]
        channel_identified_product_categories = {}
        channel_identified_brand_categories = {}
        total_of_product_categories_count = 0
        total_of_brand_categories_count = 0

        for video in beauty_videos:
            video_title = video["title"]
            video_desc = video["description"]

            words_of_interest = []
            words_of_interest = get_words_of_interest_from_text(video_title)
            words_of_interest.extend(
                get_words_of_interest_from_text(video_desc))
            words_of_interest = get_unique_words_of_interest(words_of_interest)
            video["words_of_interest"] = words_of_interest

            video["identified_product_categories"] = {}
            video["identified_brand_categories"] = {}
            for woi in words_of_interest:
                woi_in_lowercase = woi.lower()
                no_of_tokens_in_woi = len(woi_in_lowercase.split(" "))
                woi_identified_product_categories = {}
                woi_identified_brand_categories = {}
                for l in product_categories_lexicon:
                    result = extract_product_categories(l, woi, woi_in_lowercase, channel_identified_product_categories,
                                                        woi_identified_product_categories, total_of_product_categories_count, video)
                    if result == None:
                        continue
                    channel_identified_product_categories = result[0]
                    total_of_product_categories_count = result[1]
                    woi_identified_product_categories = result[2]
                    video = result[3]

                for l in brand_categories_lexicon:
                    result = extract_brand_categories(l, woi, no_of_tokens_in_woi, False, woi_in_lowercase,
                                                      channel_identified_brand_categories, total_of_brand_categories_count, woi_identified_brand_categories, video)
                    if result == None:
                        continue
                    channel_identified_brand_categories = result[0]
                    total_of_brand_categories_count = result[1]
                    woi_identified_brand_categories = result[2]
                    video = result[3]
                    no_of_tokens_in_lexicon = len(l.split(" "))
                    if no_of_tokens_in_lexicon == no_of_tokens_in_woi:
                        break

            video_tags = video.get("tags")
            if video_tags == None or len(video_tags) == 0:
                continue
            for tag in video_tags:
                tag_in_lowercase = tag.lower()
                no_of_tokens_in_tag = len(tag_in_lowercase.split(" "))
                tag_identified_product_categories = {}
                tag_identified_brand_categories = {}
                for l in product_categories_lexicon:
                    result = extract_product_categories(l, tag, tag_in_lowercase, channel_identified_product_categories,
                                                        tag_identified_product_categories, total_of_product_categories_count, video)
                    if result == None:
                        continue
                    channel_identified_product_categories = result[0]
                    total_of_product_categories_count = result[1]
                    woi_identified_product_categories = result[2]
                    video = result[3]
                for l in brand_categories_lexicon:
                    result = extract_brand_categories(l, tag, no_of_tokens_in_tag, True, tag_in_lowercase,
                                                      channel_identified_brand_categories, total_of_brand_categories_count, tag_identified_brand_categories, video)
                    if result == None:
                        continue
                    channel_identified_brand_categories = result[0]
                    total_of_brand_categories_count = result[1]
                    woi_identified_brand_categories = result[2]
                    video = result[3]
                    no_of_tokens_in_lexicon = len(l.split(" "))
                    if no_of_tokens_in_lexicon == no_of_tokens_in_woi:
                        break

        for category in channel_identified_product_categories:
            channel_identified_product_categories[category] = (
                channel_identified_product_categories[category] / total_of_product_categories_count) * 100
        for category in channel_identified_brand_categories:
            channel_identified_brand_categories[category] = (
                channel_identified_brand_categories[category] / total_of_brand_categories_count) * 100
        channel_identified_product_categories = dict(sorted(
            channel_identified_product_categories.items(), key=lambda item: item[1], reverse=True))
        channel_identified_brand_categories = dict(sorted(
            channel_identified_brand_categories.items(), key=lambda item: item[1], reverse=True))
        beauty_influencers[channel_id] = {"channel_title": beauty_influencers[channel_id]["channel_title"], "identified_product_categories": channel_identified_product_categories,
                                          "identified_brand_categories": channel_identified_brand_categories, "recent_beauty_videos": beauty_influencers[channel_id]["recent_beauty_videos"]}
        count += 1
    return beauty_influencers


# task 5 - calculate statistics of beauty influencers (overall engagement rate by views and overall sentiment score)
def analyze_beauty_influencers(beauty_influencers, channels, stats={}):
    analyzer = SentimentIntensityAnalyzer()
    count = 1
    no_of_beauty_influencers = len(beauty_influencers)
    for channel_id in beauty_influencers:
        logger.info(f"analyzing {count}/{no_of_beauty_influencers} - channel's id: {channel_id}")
        count += 1

        identified_product_categories = beauty_influencers[channel_id]["identified_product_categories"]
        identified_brand_categories = beauty_influencers[channel_id]["identified_brand_categories"]
        if len(identified_product_categories) == 0 and len(identified_brand_categories) == 0:
            continue

        # get channel's overall details
        if channels.get(channel_id) == None:
            continue
        channel_details = channels[channel_id]["channel_details"]
        channel_custom_url = channel_details["snippet"]["customUrl"].strip()
        channel_title = beauty_influencers[channel_id]["channel_title"].strip()
        channel_thumbnails = channel_details["snippet"]["thumbnails"]
        channel_statistics = channel_details["statistics"]

        videos = beauty_influencers[channel_id]["recent_beauty_videos"]["videos"]
        total_likes = 0
        total_comments = 0
        total_engagement_rate_by_views = 0
        total_sentiment_score = 0
        no_of_comments = 0
        no_of_videos = 0
        for video in videos:
            # get the comments of this video
            video_id = video["id"]
            youtube_data_api = youtube_data_api_management.check_quota_and_change_api_key_if_needed(YouTubeDataAPIManagement.YOUTUBE_READ_COST)
            is_calculate_engagement_rate = True
            video_statistics = video["statistics"]
            comment_count = float(video_statistics.get("commentCount", 0))
            is_process_comments = False
            if comment_count > 0:
                try:
                    # avoid comments that are likely spam (moderation by youtube)
                    response = youtube_data_api.commentThreads().list(
                        part="snippet",
                        videoId=video_id,
                        maxResults=100,
                        moderationStatus="published",
                        textFormat="plainText",
                        order="relevance"
                    ).execute()
                    youtube_data_api_management.use(YouTubeDataAPIManagement.YOUTUBE_READ_COST)
                    is_process_comments = True
                except googleapiclient.errors.HttpError as e:
                    if e.error_details[0]["reason"] == "videoNotFound":
                        logger.info(f"Video id: {video_id} not found")
                        is_calculate_engagement_rate = False
                    elif e.error_details[0]["reason"] == "commentsDisabled":
                        logger.info(f"Video id: {video_id} has comments disabled")
                    elif e.error_details[0]["reason"] == "quotaExceeded":
                        youtube_data_api = youtube_data_api_management.check_quota_and_change_api_key_if_needed(YouTubeDataAPIManagement.QUOTA_PER_KEY + 1)
                        response = youtube_data_api.commentThreads().list(
                            part="snippet",
                            videoId=video_id,
                            maxResults=100,
                            moderationStatus="published",
                            textFormat="plainText",
                            order="relevance"
                        ).execute()
                        youtube_data_api_management.use(YouTubeDataAPIManagement.YOUTUBE_READ_COST)
                    else:
                        logger.info(f"Video id: {video_id} has other api errors")
                except:
                    logger.info(f"Video id: {video_id} has other errors")

                if is_process_comments:
                    for item in response["items"]:
                        snippet = item["snippet"]["topLevelComment"]["snippet"]
                        commenter_channel_id = ""
                        if snippet.get("authorChannelId") != None:
                            commenter_channel_id = snippet["authorChannelId"]["value"]
                        if commenter_channel_id == channel_id:
                            continue
                        comment = snippet["textDisplay"].strip()
                        polarity_scores = analyzer.polarity_scores(comment)
                        overall_sentiment_score = polarity_scores['compound']
                        total_sentiment_score += overall_sentiment_score
                        no_of_comments += 1

            if is_calculate_engagement_rate:
                like_count = float(video_statistics.get("likeCount", 0))
                view_count = float(video_statistics.get("viewCount", 0))
                total_likes += like_count
                total_comments += comment_count
                video_engagement_rate_by_views = 0
                if view_count != 0:
                    video_engagement_rate_by_views = (
                        (like_count + comment_count) / view_count) * 100
                total_engagement_rate_by_views += video_engagement_rate_by_views
                no_of_videos += 1
            
        try:
            avg_likes = round(total_likes / no_of_videos)
            avg_comments = round(total_comments / no_of_videos)
            engagements = total_likes + total_comments
            engagement_rate_by_followers_on_posts = (
                engagements / float(channel_statistics["subscriberCount"])) * 100
            engagement_rate_by_views = total_engagement_rate_by_views / no_of_videos
        except:
            print(f"{channel_id} has 0 videos")

        # calculate avg overall sentiment score
        average_overall_sentiment_score = 0
        average_overall_sentiment = "N.A."
        if no_of_comments > 0:
            average_overall_sentiment_score = total_sentiment_score / no_of_comments
            average_overall_sentiment = get_overall_sentiment(
                average_overall_sentiment_score)

        beauty_influencer_details = {"channel_id": channel_id, "channel_custom_url": channel_custom_url, "channel_title": channel_title, "subscribers":
                                     channel_statistics["subscriberCount"], "engagement_rate_by_followers_on_posts": engagement_rate_by_followers_on_posts,
                                     "engagement_rate_by_views": engagement_rate_by_views, "average_likes": avg_likes, "average_comments": avg_comments, 
                                     "overall_sentiment_score": average_overall_sentiment_score, "overall_sentiment": average_overall_sentiment,
                                     "identified_brand_categories": identified_brand_categories, "identified_product_categories": identified_product_categories, "thumbnails": channel_thumbnails}
        stats[channel_id] = beauty_influencer_details
    return stats

# helper function to compare properties' values
def cmp(x, y):
    """
    Replacement for built-in function cmp that was removed in Python 3

    Compare the two objects x and y and return an integer according to
    the outcome. The return value is negative if x < y, zero if x == y
    and strictly positive if x > y.

    https://portingguide.readthedocs.io/en/latest/comparisons.html#the-cmp-function
    """
    return (x > y) - (x < y)

# helper function to sort columns
# referenced from https://stackoverflow.com/questions/1143671/how-to-sort-objects-by-multiple-keys
# use "-" infront of column to reverse sort
def multikeysort(items, columns):
    comparers = [
        ((i(col[1:].strip()), -1) if col.startswith('-') else (i(col.strip()), 1))
        for col in columns
    ]
    def comparer(left, right):
        comparer_iter = (
            cmp(fn(left), fn(right)) * mult
            for fn, mult in comparers
        )
        return next((result for result in comparer_iter if result), 0)
    return sorted(items, key=cmp_to_key(comparer))

# task 6 - rank beauty influencers in each makeup product category
def rank_beauty_influencers(beauty_influencers_stats):
    PRODUCT_CATEGORY_THRESHOLD = 10
    BRAND_CATEGORY_THRESHOLD = 33
    no_of_beauty_influencers_with_both_categories = 0
    categories = {}
    for channel_id in beauty_influencers_stats:
        bi = beauty_influencers_stats[channel_id]
        identified_product_categories = bi["identified_product_categories"]
        identified_brand_categories = bi["identified_brand_categories"]
        if len(identified_product_categories) == 0 and len(identified_brand_categories) == 0:
            continue
        
        bi["brand_categories_tag"] = []
        for cat in identified_brand_categories:
            rounded_val = round(identified_brand_categories[cat])
            if rounded_val < BRAND_CATEGORY_THRESHOLD:
                continue
            bi["brand_categories_tag"].append(cat)

        if len(bi["brand_categories_tag"]) == 0:
            continue
        
        bi["product_categories_tag"] = []
        # get all product categories within threshold
        for cat in identified_product_categories:
            rounded_val = round(identified_product_categories[cat])
            if rounded_val < PRODUCT_CATEGORY_THRESHOLD:
                continue
            bi["product_categories_tag"].append(cat)
            if categories.get(cat) == None:
                categories[cat] = []
            categories[cat].append(bi)

        if len(bi["product_categories_tag"]) == 0:
            continue
        
        no_of_beauty_influencers_with_both_categories += 1

    logger.info(
        f"There are {no_of_beauty_influencers_with_both_categories} beauty influencers with both product/brand categories identified")

    ranked_beauty_influencers = {}
    TOP_X = 10
    for category in categories:
        beauty_influencers_for_this_cat = categories[category]
        beauty_influencers_for_this_cat = multikeysort(beauty_influencers_for_this_cat, ['-engagement_rate_by_views', '-overall_sentiment_score'])
        # get top 10 for each category
        ranked_beauty_influencers_for_this_cat = set()
        ranked_beauty_influencers[category] = []
        no_of_ranked_beauty_influencers = 0
        for i in range(len(beauty_influencers_for_this_cat)):
            if no_of_ranked_beauty_influencers == TOP_X:
                break

            if beauty_influencers_for_this_cat[i]["overall_sentiment"] == "Negative":
                continue
            
            # remove duplicated influencer
            if beauty_influencers_for_this_cat[i]["channel_id"] in ranked_beauty_influencers_for_this_cat:
                continue
            ranked_beauty_influencers[category].append(beauty_influencers_for_this_cat[i])
            ranked_beauty_influencers_for_this_cat.add(beauty_influencers_for_this_cat[i]["channel_id"])
            no_of_ranked_beauty_influencers += 1
        logger.info(f"Up to top {TOP_X} beauty influencers were extracted from {len(beauty_influencers_for_this_cat)} beauty influencers of {category} category")
    return ranked_beauty_influencers


def main():
    # start_date_str = "01-10-2022"
    # end_date_str = "31-12-2022"
    start_date_str = "01-01-2023"
    end_date_str = "31-03-2023"
    dates = get_dates(start_date_str, end_date_str)

    # setup logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.setFormatter(formatter)

    log_file_path = os.path.join(
        CURR_DIR, "results", f'mining_{start_date_str}_to_{end_date_str}.log')
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(logging.INFO)
    file_handler.addFilter(LoggerFilter(logging.INFO))
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stdout_handler)

    filtered_away_channels = {}
    filtered_channels_filename = os.path.join(
        CURR_DIR, 'results',  f'filtered_away_channels_{start_date_str}_to_{end_date_str}.json')
    if os.path.exists(filtered_channels_filename):
        with open(filtered_channels_filename) as file:
            filtered_away_channels = json.load(file)

    channels = {}
    channels_filename = os.path.join(
        CURR_DIR, 'results',  f'channels_{start_date_str}_to_{end_date_str}.json')
    if os.path.exists(channels_filename):
        with open(channels_filename) as file:
            channels = json.load(file)

    start_no_of_channels = len(channels)

    if IS_GET_CHANNELS:
        search_terms = get_search_terms()
        start_index = 0
        # update the value of no. of terms to process accordingly
        no_of_terms_to_process = 5
        no_of_terms_processed = 0
        for i in range(start_index, len(search_terms)):
            try:
                if no_of_terms_processed == no_of_terms_to_process:
                    break
                search_keyword = search_terms[i].strip()
                for date in dates:
                    channels, filtered_away_channels = get_channels(
                        search_keyword=search_keyword, published_after=date[0], published_before=date[1], channels=channels, filtered_away_channels=filtered_away_channels)
                no_of_terms_processed += 1
            except Exception as e:
                print(str(e))
            finally:
                logger.info(
                    f"There are a total of {len(channels) - start_no_of_channels} unique channels being extracted from {start_date_str} to {end_date_str} for keyword: {search_keyword}")
                logger.info(
                    f"There are now a total of {len(channels)} unique channels being extracted from {start_date_str} to {end_date_str}")
                logger.info("\n")
                with open(channels_filename, "w") as write_file:
                    json.dump(channels, write_file, indent=4)
                with open(filtered_channels_filename, "w") as write_file:
                    json.dump(filtered_away_channels, write_file, indent=4)

    active_influencers = {}
    filename = os.path.join(
        CURR_DIR, 'results', f'active_influencers_{start_date_str}_to_{end_date_str}.json')
    if os.path.exists(filename):
        with open(filename) as file:
            active_influencers = json.load(file)
    if IS_GET_ACTIVE_INFLUENCERS:
        try:
            valid_end_date = datetime.datetime.strptime(end_date_str, "%d-%m-%Y")
            valid_start_date = valid_end_date - relativedelta(years=1)
            active_influencers, filtered_away_channels = get_active_influencers(
                channels, active_influencers, valid_start_date, filtered_away_channels=filtered_away_channels)
        except Exception as e:
            print(str(e))
        finally:
            logger.info("\n")
            with open(filename, "w") as write_file:
                json.dump(active_influencers, write_file, indent=4)
            with open(filtered_channels_filename, "w") as write_file:
                json.dump(filtered_away_channels, write_file, indent=4)

    beauty_influencers = {}
    categorized_influencers = {}
    filename = os.path.join(
        CURR_DIR, 'results', f'categorized_influencers_{start_date_str}_to_{end_date_str}.json')
    if os.path.exists(filename):
        with open(filename) as file:
            categorized_influencers = json.load(file)
    if IS_GET_BEAUTY_INFLUENCERS:
        categorized_influencers, filtered_away_channels = get_beauty_influencers(active_influencers, categorized_influencers, filtered_away_channels=filtered_away_channels)
        with open(filename, "w") as write_file:
            json.dump(categorized_influencers, write_file, indent=4)
        with open(filtered_channels_filename, "w") as write_file:
            json.dump(filtered_away_channels, write_file, indent=4)

        influencers = []
        beauty_influencers = categorized_influencers["beauty_influencers"]
        non_beauty_influencers = categorized_influencers["non_beauty_influencers"]
        for channel_id in beauty_influencers:
            row = {"channel_id": channel_id,
                   "channel_title": beauty_influencers[channel_id]["channel_title"], "is_beauty_influencer": "Y"}
            influencers.append(row)
        for channel_id in non_beauty_influencers:
            row = {"channel_id": channel_id,
                   "channel_title": non_beauty_influencers[channel_id]["channel_title"], "is_beauty_influencer": "N"}
            influencers.append(row)
        df = pd.DataFrame(influencers)
        filename = os.path.join(
            CURR_DIR, 'data', f'categorized_influencers_{start_date_str}_to_{end_date_str}.csv')
        df.to_csv(filename, index=False)

    beauty_influencers = categorized_influencers.get("beauty_influencers", {})
    filename = os.path.join(
        CURR_DIR, 'results', f'categorized_beauty_influencers_{start_date_str}_to_{end_date_str}.json')
    if os.path.exists(filename):
        with open(filename) as file:
            beauty_influencers = json.load(file)
    if IS_CATEGORIZE_BEAUTY_INFLUENCERS:
        logger.info(
            f"Categorizing beauty influencers from categorized_beauty_influencers_{start_date_str}_to_{end_date_str}.json")
        beauty_influencers = categorize_beauty_influencers(beauty_influencers)
        logger.info("Done categorizing beauty influencers")
        logger.info("\n")
        with open(filename, "w") as write_file:
            json.dump(beauty_influencers, write_file, indent=4)

    beauty_influencers_stats = {}
    filename = os.path.join(
            CURR_DIR, 'results', f'beauty_influencers_stats_{start_date_str}_to_{end_date_str}.json')
    if os.path.exists(filename):
        with open(filename) as file:
            beauty_influencers_stats = json.load(file)
    if IS_ANALYZE_BEAUTY_INFLUENCERS:
        try:
            logger.info(f"Analyzing categorized beauty influencers from categorized_beauty_influencers_{start_date_str}_to_{end_date_str}.json")
            beauty_influencers_stats = analyze_beauty_influencers(beauty_influencers, channels, stats=beauty_influencers_stats)
            logger.info("Done analyzing beauty influencers")
        except Exception as e:
            print(str(e))
        finally:
            logger.info("\n")
            with open(filename, "w") as write_file:
                json.dump(beauty_influencers_stats, write_file, indent=4)


    ranked_influencers = {}
    filename = os.path.join(
            CURR_DIR, 'results', f'ranked_beauty_influencers_{start_date_str}_to_{end_date_str}.json')
    if IS_RANK_INFLUENCERS:
        logger.info(f"Ranking categorized beauty influencers from beauty_influencers_stats_{start_date_str}_to_{end_date_str}.json")
        ranked_influencers = rank_beauty_influencers(beauty_influencers_stats)
        logger.info("Done ranking beauty influencers")
        logger.info("\n")
        with open(filename, "w") as write_file:
            json.dump(ranked_influencers, write_file, indent=4)

        ranked_influencers_for_csv = []
        for category in ranked_influencers:
            rank = 1
            for influencer in ranked_influencers[category]:
                row = {"category": category, "rank": rank, "channel": influencer["channel_id"] + " " + influencer["channel_custom_url"] + " " + influencer["channel_title"],
                       "engagement_rate_by_views": format(influencer["engagement_rate_by_views"], '.4f'), "overall_sentiment_score": format(influencer["overall_sentiment_score"], ".4f"),
                       "overall_sentiment_label": influencer["overall_sentiment"], "brands_categories": ' '.join(influencer["brand_categories_tag"])}
                ranked_influencers_for_csv.append(row)
                rank += 1
        df = pd.DataFrame(ranked_influencers_for_csv)
        filename = os.path.join(
            CURR_DIR, 'results', f'ranked_beauty_influencers_{start_date_str}_to_{end_date_str}.csv')
        df.to_csv(filename, index=False)
            

main()