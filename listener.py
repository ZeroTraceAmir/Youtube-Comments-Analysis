# package imports
import feedparser
import json
import requests

from dotenv import load_dotenv

# local imports
import database
from utils import log, get_proxy_url, get_requests_proxies

# load environment variables (optional proxy config)
load_dotenv()

# create datyabase and table (if it doesnt exists)
database.init_db()

# channel list file
channel_list = "channels.json"
# rss feed base url
rss_base = "https://www.youtube.com/feeds/videos.xml?"

# optional proxy for the rss requests
# None when no proxy is configured (requests default behavior)
PROXIES = get_requests_proxies()
if PROXIES:
  log(f"[LISTENER] Using proxy [{get_proxy_url()}]")

# uses the correct parameter in the feed url
# -----------------------------------------------------------------------------
def get_feed_parameter(channel_id: str) -> str:
  # if it starts with UC it's the channel ID
  if channel_id[:2] == "UC":
    return "channel_id"

  # anything else is the playlist ID
  return "playlist_id"

# gets the raw rss feed bytes for a channel
# -----------------------------------------------------------------------------
def fetch_rss_feed(feed_url: str) -> bytes | None:
  try:
    response = requests.get(feed_url, timeout = 30, proxies = PROXIES)
    response.raise_for_status()
    return response.content

  except requests.RequestException as e:
    log(f"[LISTENER] Error fetching RSS feed [{feed_url}]: {e}")
    return None

# -----------------------------------------------------------------------------
def main():
  # opens channel list for parsing
  with open(channel_list, 'r') as f:
    channels = json.load(f)

  # goes through each channel in the list
  for channel_id, config in channels.items():
    # get channel name
    channel = config['channel_name']
    log(f"[LISTENER] Starting parse for channel [{channel}]")

    # get the correct url parameter
    param = get_feed_parameter(channel_id)

    # get rss feed for this channel ID
    feed_url = rss_base + param + "=" + channel_id
    feed_content = fetch_rss_feed(feed_url)

    # if the feed could not be fetched
    # ignore it and go to the next channel
    if not feed_content:
      continue

    # parse the feed content
    feed_data = feedparser.parse(feed_content)

    # if the content is not a valid feed
    # ignore it and go to the next channel
    if feed_data.bozo and not feed_data.entries:
      log(
        f"[LISTENER] Error: Couldn't parse RSS data for channel [{channel}]: "
        f"{getattr(feed_data, 'bozo_exception', 'unknown error')}"
      )
      continue

    # get channel name from rss feed
    channel_name = getattr(getattr(feed_data, "feed", None), "author", "Unknown")
    # start with empty list of videos
    video_list = []

    # go through each video in the rss feed
    for video in feed_data.entries:
      # relevant video info:
      #
      # yt_channelid  -> channel ID
      # yt_videoid    -> video ID
      # links[0],href -> video link
      # author        -> author (channel name)
      # title         -> title
      # published     -> published date/time

      # ignore all shorts
      if "shorts" in video.links[0].href:
        continue

      # prepare data to database
      video_list.append({
        "video_id": video.yt_videoid,
        "channel_id": video.yt_channelid,
        "author": video.author,
        "title": video.title,
        "published_at": video.published,
      })

    # no videos in the feed
    # (shorts-only channels end up here since shorts are ignored)
    if not video_list:
      log(f"[LISTENER] No videos found for channel [{channel}]")
      continue

    # save new videos to database
    database.save_rss_videos(video_list, channel_name)

# -----------------------------------------------------------------------------
if __name__ == "__main__":
  main()
