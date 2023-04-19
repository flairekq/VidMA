# VidMA
Vid - Video, M - Mining, A - Analysis<br>
A social media analytics project 

## Background & Motivation
With the growing popularity of social media, businesses wants to use the data from social media to understand their customers, competitors & identify market trends. However, they face 2 main issues in doing so. The first issue is related to data collection. With a variety of social media platforms available to collect data from, it is difficult to collect data from them be it manually or automatically due to the huge amount of data and different structure it has. Even though there are APIs available to use, most of the data offered are not comprehensive enough to allow businesses to analyze what they want/need. Some APIs might be unstable as well and some are also costly. The second issue is related to analysis. The processing required for unstructured data collected is complicated and insights cannot be extracted directly from the data collected. Hence, we aim to help businesses to analyze social media data.

## Target user
In particular, we are targeting brands that sells makeup products. For our prototype, VidMA, we are targeting Sephora, a beauty retailer that sells multiple brands and products including its own.

## Innovations
- VidMA uses the valuable data from video-based platforms like YouTube which is under-utilised in existing tools
- VidMA provide actionable insights with aspect-based sentiment analysis
- VidMA empower brands to react to user sentiments efficiently and effectively with influencer identification where influencers are profiled at the product level e.g., lipstick

## Features
1. Aspect-based sentiment analysis on makeup products reviews on YouTube
2. Identify, profile and rank YouTube beauty influencers for each makeup product categories

## Data Collection
- YouTube APIs: Data API v3 to get videos, channels and comments data, Transcript API to get text transcript and raw transcript with timestamps and Operational API to get video chapters
- Sephora website: Scraped the makeup products
- Beauty blogs: Collated a list of beauty brands from the blogs

## Tech Stack
- Python
- Flask framework for the website
- Firebase realtime database for storing of data

## Website
VidMA is hosted on https://vidma.onrender.com/ (P.S. as we are using the free plan for hosting on Render, it takes awhile to load when the website is in inactive state. We might take down the hosting after a period of time so we included screenshots of our website below to showcase it.)
### Products Review
For the prototype, we mined 40 videos from January to February 2023. In the carousel, we have a brand category chart, a makeup product category chart and a word cloud on the aspects. The charts were built with ZingChart. As the information for each product (e.g. the aspects, the video details) was placed in an accordion so as not to overwhelm the reader, the purpose of these charts was to provide a quick overview of the data mined. For example, using the brand category chart, user can understand the hot-topic brands for that timeframe. 

<img width="754" alt="image" src="https://user-images.githubusercontent.com/83572953/233053348-9a19f374-6aa8-4c7b-aa2a-bb12478fabf2.png">


Using the word cloud, Sephora can understand what users value in the makeup products. Then, to dig further, they can use the search box function if they want to see sentiments for a particular product, brand or category. 

<img width="764" alt="image" src="https://user-images.githubusercontent.com/83572953/233053476-c91b1532-43fb-4c93-9da7-315ab3d7d5ff.png">

They can also filter to “Comparisons” if they want to see reviews where a product was compared with another product. When there is more data mined and when these video reviews are used in tandem with their other social media data sources, Sephora could better understand the market and decide which product they can prioritize in their marketing. 

<img width="716" alt="image" src="https://user-images.githubusercontent.com/83572953/233053587-4a4a9403-b086-49ef-8c89-dbc372788ad8.png">

The filter of “Combinations” is for reviews where the Youtuber had shared for example that a product works well with another. One such review is for the ELF Luminous Putty Bronzer that was shared to work well with the ELF Prime and Stay Finishing Powder. This benefits Sephora because they can sell these products as sets. 

<img width="720" alt="image" src="https://user-images.githubusercontent.com/83572953/233053728-05b56e6c-c371-4b48-92b3-bf98798020cb.png">

We also have a sort function in the UI so that Sephora can sort the products based on metrics they value like comments, engagement rate, views or comment counts.
<img width="685" alt="image" src="https://user-images.githubusercontent.com/83572953/233053801-56e49b2f-db3f-42ac-ae6a-17dc41a24cea.png">

Finally, users can access information about the video by opening the "Video Details" section in the accordion

<img width="651" alt="image" src="https://user-images.githubusercontent.com/83572953/233053952-6809f9fd-2d38-41a5-82d6-78b41e457441.png">


### Influencers recommendation
![Image of the list of up to top 10 beauty influencers for BB & CC cream](images/influencers_recommendation_ss_1.png)
Influencers are mined on a quartely basis and we have mined influencers' data from 2022 Q4 and 2023 Q1 for our prototype. Users can view each quarter’s data through the tab view, with each tab corresponding to the quarter period and displaying the ranked list of beauty influencers for that quarter. Only one makeup product category’s ranked list of beauty influencers will be shown at a time to avoid overwhelming users. Users can click on navigation links in the collapsible side menu to view other makeup product categories’ ranked lists. Each listed ranked beauty influencer shows their ranking for the period’s product category, YouTube channel’s profile picture, title, custom handle URL (e.g., @paigekoren), engagement rate by views, sentiment score and label of positive/neutral, and associated brand categories. To view the influencer’s YouTube channel page, users can click on their profile picture, title or custom handle URL to be redirected to the page. As our target users are mainly non-technical people, they might not understand what sentiment score means so there's a tooltip that provides a brief explanation of what it means (see the image below).
 ![Brief explanation of what sentiment score means](images/influencers_recommendation_ss_2.png)
