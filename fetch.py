# This file will collect a social network on Twitter
# It reads authentication information from auth.json
# and generates several api objects as workers
# It will start crawling from a given point of user

import os
import json
import time
import tweepy
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

class Crawler:
    def __init__(self, auth_path="auth.json", max_nodes=100000, max_followers_per_user=5000, max_friends_per_user=5000):
        self.auth_path = auth_path
        self.api_queue = []
        self.start = None
        self.graph = nx.Graph()
        self.max_nodes = max_nodes
        self.max_followers_per_user = max_followers_per_user
        self.max_friends_per_user = max_friends_per_user
        self.cursor_saved = -1 # for storing temp cursor

    def set_starting_user(self, username=None, userid=None):
        """Set the starting point"""
        assert len(self.api_queue) >= 1
        if(userid):
            self.start = userid
        elif(username):
            self.start = self.api_queue[0].api.get_user(screen_name=username).id
        else:
            self.start = self.api_queue[0].api.me().id

    def load_auths(self):
        """Load auth apis from json"""
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
        self.set_starting_user() # set default starting point
    
    def recycle_apis(self):
        """Put the current api to the end of queue, and start using the next one"""
        assert len(self.api_queue) >= 1
        first = self.api_queue[0]
        self.api_queue = self.api_queue[1:].append(first)
        return self.api_queue[0].remaining_time

    def refresh(self):
        """Refresh all api block time"""
        for api in self.api_queue:
            api.update()

    def start(self):
        """Start crawling"""
        assert self.start is not None
        assert len(self.api_queue) >= 1
        nodes_in_search = [self.start]
        while self.graph.number_of_nodes() < self.max_nodes:
            index = 0
            new_nodes_in_search = []
            while index < len(nodes_in_search):
                nodeid = nodes_in_search[index]
                print("Currently looking at id={}".format(nodeid))
                try:
                    follower_ids = self.api_queue[0].api.followers_ids(user_id=nodeid)
                    friends_ids = self.api_queue[0].api.friends_ids(user_id=nodeid)
                except tweepy.RateLimitError:
                    self.refresh()
                    self.api_queue[0].block() # block current api
                    remaining = self.recycle_apis() # recycle apis
                    if(remaining > 0): # if all apis are blocked, then wait
                        print("All apis are blocked, sleeping for {}s".format(remaining))
                        time.sleep(remaining + 1)
                else:
                    for followerid in follower_ids:
                        if not self.graph.has_node(followerid):
                            new_nodes_in_search.append(followerid)
                        self.graph.add_edge(nodeid, followerid)
                    for friendid in friends_ids:
                        if not self.graph.has_node(friendid):
                            new_nodes_in_search.append(friendid)
                        self.graph.add_edge(nodeid, friendid)
                    index += 1
                    print("Retrieve complete - Current graph size: {}".format(self.graph.number_of_nodes()))
                    time.sleep(1)
            nodes_in_search = new_nodes_in_search
            time.sleep(1)

if __name__ == "__main__":
    app = Crawler(auth_path=os.path.join("auth.json"))
    app.load_auths()
    app.set_starting_user()