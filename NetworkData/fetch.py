# This file will collect a social network on Twitter
# It reads authentication information from auth.json
# and generates several api objects as workers
# It will start crawling from a given point of user

import os
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

class Crawler:
    def __init__(self, auth_path="auth.json", max_nodes=100000, max_leaves=10, keep_cache=False, limit_lan="en"):
        self.auth_path = auth_path
        self.api_queue = []
        self.start = None
        self.graph = nx.Graph()
        self.max_nodes = max_nodes
        # self.max_followers_per_user = max_followers_per_user
        # self.max_friends_per_user = max_friends_per_user
        # self.cursor_saved = -1 # for storing temp cursor
        self.nodes_in_search = []
        self.search_index = -1
        self.keep_cache = keep_cache
        assert max_leaves < 5000
        assert max_leaves > 0
        self.max_leaves = max_leaves
        self.limit_lan = limit_lan

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
        self.set_starting_user() # set default starting point
        print("Total number of auths: {}".format(len(self.api_queue)))
        print("Number of nodes to crawl: {}".format(self.max_nodes))
        print("Max number of leaves per node: {}".format(self.max_leaves))
        print("Maximum estimated time for running: {:.2f}hr".format(self.max_nodes / self.max_leaves / (15 * len(self.api_queue)) * 15 / 60))
    
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

    def run(self, savefile=True):
        """Start crawling"""
        assert self.start is not None
        assert len(self.api_queue) >= 1
        if not hasattr(self, "time_start") or self.time_start is None:
            self.time_start = time.time()
        self.nodes_in_search = [self.start] if len(self.nodes_in_search) <= 0 else self.nodes_in_search
        while self.graph.number_of_nodes() < self.max_nodes:
            if len(self.nodes_in_search) <= 0: break
            self.search_index = 0 if self.search_index <= 0 else self.search_index
            self.new_nodes_in_search = []
            while (self.search_index < len(self.nodes_in_search)) and (self.graph.number_of_nodes() < self.max_nodes):
                nodeid = self.nodes_in_search[self.search_index]
                print("Currently looking at id={}".format(nodeid))
                try:
                    follower_ids = self.api_queue[0].api.followers_ids(user_id=nodeid)
                    friends_ids = self.api_queue[0].api.friends_ids(user_id=nodeid)
                except tweepy.RateLimitError:
                    self.api_queue[0].block() # block current api
                    remaining = self.recycle_apis() # recycle apis
                    self._tmp_save()
                    if(remaining > 0): # if all apis are blocked, then wait
                        print("All APIs are blocked, sleeping for {:.2f}s".format(remaining))
                        time.sleep(remaining + 1)
                    continue
                except tweepy.TweepError as e:
                    print("Error: {}\nIgnore and continue".format(e))
                    self.search_index += 1
                    continue
                else:
                    if (hasattr(self, "tmp_result") and hasattr(self, "tmp_ids")) and (self.tmp_result is not None) and (self.tmp_ids is not None):
                        extracted_ids = self._extract_ids(nodeid, self.tmp_ids, self.tmp_result)
                    else:
                        extracted_ids = self._extract_ids(nodeid, list(set(follower_ids + friends_ids)))
                    for extractedid in extracted_ids:
                        if not self.graph.has_node(extractedid):
                            self.new_nodes_in_search.append(extractedid)
                        self.graph.add_edge(nodeid, extractedid)
                    self.search_index += 1
                    print("Retrieve complete - Current graph size: {} - Num of edges: {}".format(self.graph.number_of_nodes(), self.graph.number_of_edges()))
                    time.sleep(1)
            self.nodes_in_search = self.new_nodes_in_search
            self.search_index = -1
            time.sleep(1)
        print("Crawling Complete - Total Number of Nodes: {}".format(self.graph.number_of_nodes()))
        if savefile:
            print("Saving edge list")
            dataframe = nx.to_pandas_edgelist(self.graph)
            dataframe.to_csv("fetchcontent.csv", index=False)
        if not self.keep_cache:
            self._tmp_delete()
        print("Total Running Time: {:.2f}hr".format((time.time() - self.time_start) / 60 / 60))
        self.time_start = None

    def display_info(self, csv_file=None):
        graph = self.graph
        if csv_file:
            dataframe = pd.read_csv(csv_file)
            graph = nx.from_pandas_edgelist(dataframe)
        print("Number of nodes: {}".format(graph.number_of_nodes()))
        print("Number of edges: {}".format(graph.number_of_edges()))
        print("Radius: {}".format(nx.radius(graph)))
        print("Density: {}".format(nx.density(graph)))

    def _extract_ids(self, parentid, ids, result=[]):
        try:
            current_ids = []
            result_copy = result.copy()
            while len(ids) > 0:
                current_ids = ids[:100]
                ids = ids[100:]
                result_copy += [[u.id, u.followers_count + u.friends_count] 
                    for u in self.api_queue[0].api.lookup_users(user_ids=current_ids) 
                    if (not self.graph.has_edge(parentid, u.id)) and 
                    (hasattr(u, "status") and (u.status.lang is None or u.status.lang == self.limit_lan))] # either None or target language will be accepted
            self.tmp_result = None
            self.tmp_ids = None
            result_copy = [x[0] for x in sorted(result_copy, key=lambda m: m[1], reverse=True)][:self.max_leaves]
            return result_copy
        except tweepy.RateLimitError:
            self.api_queue[0].block()
            remaining = self.recycle_apis()
            if(remaining > 0): # if all apis are blocked, then wait
                print("All APIs are blocked, sleeping for {:.2f}s".format(remaining))
                self.tmp_result = result
                self.tmp_ids = current_ids + ids
                self._tmp_save()
                time.sleep(remaining + 1)
            return self._extract_ids(parentid, current_ids + ids, result)
        except tweepy.TweepError as e:
            print("Error: {}".format(e))
            return self._extract_ids(parentid, ids, result)

    # def _validate_user(self, userid):
    #     try:
    #         tweets = self.api_queue[0].api.user_timeline(user_id=userid, count=50)
    #         tweets = [x for x in tweets if x.lang==self.limit_lan]
    #         if len(tweets) >= 45:
    #             return True
    #         else:
    #             return False # not valid user with target language
    #     except tweepy.RateLimitError:
    #         self.api_queue[0].block()
    #         remaining = self.recycle_apis()
    #         if(remaining > 0): # if all apis are blocked, then wait
    #             print("All APIs are blocked, sleeping for {:.2f}s".format(remaining))
    #             self._tmp_save()
    #             time.sleep(remaining + 1)
    #         return self._validate_user(userid)
    #     except tweepy.TweepError as e:
    #         print("Tweet Error: {}".format(e))
    #         return False # default to False if error occurs

    def _tmp_save(self):
        with open("fetch.py.tmp.pickle", "wb") as outFile:
            pickle.dump(self, outFile)

    def _tmp_delete(self):
        if os.path.exists("fetch.py.tmp.pickle"):
            os.remove("fetch.py.tmp.pickle")

def recover():
    """Recover running app from temp pickle file"""
    if os.path.exists("fetch.py.tmp.pickle"):
        with open("fetch.py.tmp.pickle", "rb") as inFile:
            app = pickle.load(inFile)
        startid = app.start
        app.load_auths()
        app.set_starting_user(userid=startid)
        return app
    else:
        print("No tmp pickle found\nFailed to recover")
        sys.exit()

if __name__ == "__main__":
    app = Crawler(auth_path=os.path.join("auth.json"), max_nodes=10000, max_leaves=10, keep_cache=True)
    app.load_auths()
    app.set_starting_user(username="3blue1brown")
    app.run()
    app.display_info()
    # app = recover()
    # app.display_info()
    # dataframe = nx.to_pandas_edgelist(app.graph)
    # dataframe.to_csv("fetchcontent.csv", index=False)
    # app.display_info(csv_file="fetchcontent.csv")