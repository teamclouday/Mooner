# this file contains code to crawl twitter tweets
# from specific users

import os
import re
import sys
import json
import time
import tweepy
import pickle
import pandas as pd
import networkx as nx

class TwitterAPI:
    def __init__(self, tweepy_api):
        self.api = tweepy_api
        self.remaining_time = 0
        self.block_time = 0

    def block(self):
        """Block this api if rate limit exceeds"""
        self.remaining_time = 15 * 60 + 5 # for how long to restart
        self.block_time = time.time() # store block time
    
    def update(self):
        """Refresh the api"""
        if(self.remaining_time == 0):
            return
        self.remaining_time -= (time.time() - self.block_time)
        self.remaining_time = 0 if self.remaining_time <= 0 else self.remaining_time

class TweetCrawler:
    def __init__(self, userids, auth_path="auth.json", num_per_user=50, only_long_tweets=True, keep_cache=False):
        self.auth_path = auth_path
        self.api_queue = []
        self.num_per_user = num_per_user
        if only_long_tweets:
            assert num_per_user <= 1500 # max fetch less than 3000
        self.only_long_tweets = only_long_tweets
        self.keep_cache = keep_cache
        self.target_user_ids = userids
        self.cursor = -1
        self.current_userid_index = 0
        self.tweets = {}
        self.char_list = list(range(97, 123)) + list(range(65, 91)) + [ord(' '), ord('\'')]

    def load_auths(self):
        """Load auth apis from json"""
        assert os.path.exists(self.auth_path)
        with open(self.auth_path, "r") as inFile:
            data = json.load(inFile)
        for api_info in data:
            print("Loading api info from " + api_info["id"])
            auth = tweepy.OAuthHandler(consumer_key=api_info["API_key"], consumer_secret=api_info["API_sec_key"])
            auth.set_access_token(key=api_info["Access_token"], secret=api_info["Access_sec_token"])
            tweepyapi = tweepy.API(auth)
            if(tweepyapi is None):
                print("Failed to init api for " + api_info["id"])
                continue
            api = TwitterAPI(tweepyapi)
            self.api_queue.append(api)
            print("Load complete")

    def run(self, savefile=True):
        """Get tweets from target users"""
        assert len(self.target_user_ids) >= 1
        num = len(self.target_user_ids) - self.current_userid_index - 1
        print("Total num of ids to crawl: {}".format(num))
        print("Max num of tweets per user: {}".format(self.num_per_user))
        num *= self.num_per_user
        if self.only_long_tweets: num *= 2
        print("Estimated running time: {:.2f}hr".format(num / (len(self.api_queue) * 1500) * 15 / 60))
        if not hasattr(self, "start_time") or self.start_time is None:
            self.start_time = time.time()
        while self.current_userid_index < len(self.target_user_ids):
            current_user = self.target_user_ids[self.current_userid_index]
            percent = (self.current_userid_index+1)/len(self.target_user_ids)*100
            print("{:.1f}% - Now crawling tweets from userid={}".format(percent, current_user))
            try:
                if self.only_long_tweets:
                    tweets = self.api_queue[0].api.user_timeline(user_id=current_user, count=self.num_per_user*2, tweet_mode="extended") # if only long tweets, need to fetch more
                else:
                    tweets = self.api_queue[0].api.user_timeline(user_id=current_user, count=self.num_per_user, tweet_mode="extended")
            except tweepy.RateLimitError:
                self.api_queue[0].block() # block current api
                remaining = self.recycle_apis() # recycle apis
                self._tmp_save()
                if(remaining > 0): # if all apis are blocked, then wait
                    print("All APIs are blocked, sleeping for {:.2f}s".format(remaining))
                    time.sleep(remaining + 1)
                continue
            except tweepy.TweepError as e:
                print("Error: {}\nCurrent userid = {}\nIgnore and continue".format(e, current_user))
                self.current_userid_index += 1
                continue
            else:
                tweets = [tweet.full_text for tweet in tweets]
                tweets_with_length = [[self._tweet_length(text), text] for text in tweets]
                tweets_with_length.sort(key=lambda x: x[1], reverse=True) # sort by number of words
                final_tweets = [x[0] for x in tweets_with_length[:self.num_per_user]] # get final tweets
                self.tweets[current_user] = final_tweets
                print("{:.1f}% - {} tweets fetched for userid={}".format(percent, len(final_tweets), current_user))
            self.current_userid_index += 1
        self._tmp_save()
        if savefile:
            with open("tweets.json", "w") as outFile:
                json.dump(self.tweets, outFile)
            print("File Saved")
        if not self.keep_cache:
            self._tmp_delete()
        print("Running Time: {:.2f}min".format((time.time() - self.start_time) / 60))
        self.start_time = None
    
    def recycle_apis(self):
        """Put the current api to the end of queue, and start using the next one"""
        assert len(self.api_queue) >= 1
        print("Recycling APIs")
        self._refresh()
        first = self.api_queue[0]
        self.api_queue = self.api_queue[1:] + [first]
        return self.api_queue[0].remaining_time

    def _refresh(self):
        """Refresh all api block time"""
        for api in self.api_queue:
            api.update()

    def _tmp_save(self):
        with open("tweets_crawler.py.tmp.pickle", "wb") as outFile:
            pickle.dump(self, outFile)

    def _tmp_delete(self):
        if os.path.exists("tweets_crawler.py.tmp.pickle"):
            os.remove("tweets_crawler.py.tmp.pickle")

    def _tweet_length(self, tweet_text):
        """Get actual length (num of words) of a tweet"""
        tweet_text = re.sub(r"(@|#)([A-Z]|[a-z]|[0-9]|_)+", "", tweet_text) # remove @username
        tweet_text = re.sub(r"(http|https)://([A-Z]|[a-z]|[0-9]|/|\.)+", "", tweet_text) # remove urls
        tweet_text = "".join([ch.lower() if ord(ch) in self.char_list else ' ' for ch in list(tweet_text)]) # remove non-english or number chars
        tweet_text = tweet_text.strip() # remove space at front or end
        return len(tweet_text.split())

def recover():
    """Recover running app from temp pickle file"""
    if os.path.exists("tweets_crawler.py.tmp.pickle"):
        with open("tweets_crawler.py.tmp.pickle", "rb") as inFile:
            app = pickle.load(inFile)
        return app
    else:
        print("No tmp pickle found\nFailed to recover")
        sys.exit()

if __name__ == "__main__":
    df = pd.read_csv("centrality.csv")
    userids = []
    for community in df["Centers ID"]:
        userids += [int(x) for x in community.split(" | ")]
    app = TweetCrawler(userids=userids, auth_path=os.path.join("..", "NetworkData", "auth.json"),
                       num_per_user=200, only_long_tweets=True, keep_cache=True)
    app.load_auths()
    app.run(savefile=True)