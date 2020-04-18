# This is the server file for the recommendation system

from model import *
import time
import json
import tweepy
from flask import Flask, render_template, url_for, redirect, request
app = Flask(__name__)

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

class WebApp:
    def __init__(self, auth_path="auth.json", data_path="data.csv"):
        self.api_queue = []
        self.auth_path = auth_path
        self._init_auths()
        self.data_path = data_path
        self._init_users()
        self.model_senti = ModelSentiment()
        self.model_topic = ModelTopic()
        self.clear()
        
    def clear(self):
        """Clear all attributes to default"""
        self.test_mode = False
        self.waiting = False
        self.senti_output_str = "None"
        self.topic_output_str = ["None" for _ in range(5)]
        self.username_str = ""
        self.userid_str = ""
        self.test_tweet_str = ""
        self.recommand_list = []

    def switch_mode(self):
        """Switch between normal mode and test mode"""
        self.test_mode = not self.test_mode
    
    def _init_auths(self):
        """Load auth apis from json"""
        if not os.path.exists(self.auth_path):
            print("Failed to init apis")
            return
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
        self._update_api_status()
    
    def _init_users(self):
        """Load target users from local disk"""
        if not os.path.exists(self.data_path):
            print("Failed to load users")
            return
        data = pd.read_csv(self.data_path)
        self.userdata = data
        self.topics = data.columns.tolist()[1:] # after ID column
        print("{} users loaded".format(len(data)))

    def recycle_apis(self):
        """Put the current api to the end of queue, and start using the next one"""
        assert len(self.api_queue) >= 1
        print("Recycling APIs")
        self._refresh()
        first = self.api_queue[0]
        self.api_queue = self.api_queue[1:] + [first]
        self._update_api_status()
        return self.api_queue[0].remaining_time

    def _refresh(self):
        """Refresh all api block time"""
        for api in self.api_queue:
            api.update()

    def _update_api_status(self):
        """Update api status string"""
        num_working = 0
        for api in self.api_queue:
            if api.remaining_time <= 0:
                num_working += 1
        if len(self.api_queue) == 0:
            string = "No API found"
        elif len(self.api_queue) == num_working:
            string = "Total {} APIs, all working".format(len(self.api_queue))
        elif num_working <= 0:
            string = "Total {} APIs, all blocked".format(len(self.api_queue))
        else:
            string = "Total {} APIs, {} working, {} blocked".format(len(self.api_queue), num_working, len(self.api_queue) - num_working)
        self.api_status_str = string

webapp = WebApp(os.path.join("..", "NetworkData", "auth.json"))

@app.route('/')
def main():
    global webapp
    return render_template('server.html', webapp=webapp)

# function for running the application
@app.route('/execute')
def run():
    global webapp
    return redirect(url_for('main'))

# function for handling button clicks
@app.route('/submit', methods=['POST'])
def button_click():
    global webapp
    if "SWITCH" in request.form: # if switch button clicked
        webapp.clear()
        webapp.switch_mode()
    elif "RUN" in request.form: # elif run button clicked
        pass
    return redirect(url_for('main'))

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5678)