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
        self.test_mode = False

    def clear(self):
        """Clear all attributes to default"""
        self.waiting = False
        self.senti_output_str = "None"
        self.topic_outputs = [["None", "0.0"] for _ in range(5)]
        self.username_str = ""
        self.userid_str = ""
        self.test_tweet_str = ""
        self.recommand_list = []
        self.current_user_data = None
        self.error_log = None

    def run(self):
        """Run application based on input"""
        if not hasattr(self, "api_queue") or len(self.api_queue) <= 0:
            print("No APIs, no output")
            self.error_log = "No APIs, no output"
            return
        if not hasattr(self, "userdata"):
            print("No user data loaded, no output")
            self.error_log = "No user data loaded, no output"
            return
        if self.test_mode: # if in test mode
            if self.test_tweet_str == "":
                print("No tweet string input, no output")
                self.error_log = "No tweet string input, no output"
                return
            string = preprocess(self.test_tweet_str)
            pos_neg = self.model_senti.run(string) # return data is a float number
            self.senti_output_str = "Positive" if pos_neg > 0.5 else "Negative"
            topics = self.model_topic.run(string) # return data is list of possibilities
            self.current_user_data = (pos_neg * 2 - 1) * np.array(topics) * 100 # get current user data
            topics = list(enumerate(topics)) # assign index
            topics.sort(key=lambda x:x[1], reverse=True) # descending order
            topics = [(self.topics[i], "{:.5f}".format(score)) for (i, score) in topics[:5]] # get topic name
            self.topic_outputs = topics
            self._find_similar_5()
        else: # else in normal mode
            if self.userid_str == "" and self.username_str == "":
                print("No userid nor username entered, no output")
                self.error_log = "No userid nor username entered, no output"
                return
            # get current user id
            if self.userid_str != "": # use userid by default
                try:
                    userid = int(self.userid_str)
                except Exception as e:
                    print("Error: {}".format(e))
                    print("No output")
                    self.error_log = "Error: {}. No output".format(e)
            else:
                userid = self._get_userid_by_name(self.username_str)
            if userid is None: return
            # get user tweets
            tweets = self._crawl_user_tweets(userid)
            if tweets is None: return
            if tweets == []:
                print("No accessible tweets found for current user")
                self.error_log = "No accessible tweets found for current user"
                return
            pos_neg = self.model_senti.run(tweets) # return data is a float number
            self.senti_output_str = " ".join(["Positive" if x > 0.5 else "Negative" for x in pos_neg[:5]])
            topics = self.model_topic.run(tweets) # return data is list of possibilities
            topic_processed = [np.argmax(x) for x in topics[:5]] # get index for each tweet
            self.topic_outputs = zip([self.topics[x] for x in topic_processed], ["{:.5f}".format(np.max(x)) for x in topics[:5]])
            topics = np.array(topics) * 100
            pos_neg = 2 * np.array(pos_neg) - 1
            self.current_user_data = np.zeros(20)
            for sign, dist in zip(pos_neg, topics):
                self.current_user_data += sign * dist
            self.current_user_data /= len(tweets)
            self._find_similar_5()

    def switch_mode(self):
        """Switch between normal mode and test mode"""
        self.test_mode = not self.test_mode
    
    def _init_auths(self):
        """Load auth apis from json"""
        if not os.path.exists(self.auth_path):
            print("Failed to init apis")
            self.error_log = "Failed to init apis"
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
            self.error_log = "Failed to load users"
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

    def _find_similar_5(self):
        """Most most similar 5 people from database"""
        if self.current_user_data is None:
            print("No current user data, no recommend")
            self.error_log = "No current user data, no recommend"
            return
        saved_data = self.userdata[self.topics].to_numpy() # get matrix
        # calculate euclidean distance
        # result = np.apply_along_axis(lambda x: np.linalg.norm(x-self.current_user_data), 1, saved_data) # return an array
        # calculate angle between two vectors
        result = np.apply_along_axis(lambda x: self._calc_angle(x, self.current_user_data), 1, saved_data)
        result = result.argsort()[:10] # top 10 nearest index
        result = self.userdata["ID"].iloc[result].tolist() # get ids
        self.recommand_list = self._get_user_profiles(result)

    # credit: https://kite.com/python/answers/how-to-get-the-angle-between-two-vectors-in-python
    def _calc_angle(self, vector1, vector2):
        assert len(vector1) == len(vector2)
        unit1 = vector1 / np.linalg.norm(vector1)
        unit2 = vector2 / np.linalg.norm(vector2)
        dot_product = np.dot(unit1, unit2)
        return np.arccos(dot_product)

    def _get_user_profiles(self, userid_list):
        """Get user profiles"""
        result = []
        try:
            users = self.api_queue[0].api.lookup_users(user_ids=userid_list)
            for user in users:
                userdata = {}
                userdata["img"] = "".join(user.profile_image_url_https.rsplit("_normal", 1)) # get high resolution image
                userdata["name"] = user.name
                userdata["screen_name"] = user.screen_name
                userdata["id"] = user.id
                result.append(userdata)
        except tweepy.RateLimitError:
            self.api_queue[0].block() # block current api
            remaining = self.recycle_apis() # recycle apis
            if(remaining > 0): # if all apis are blocked, then wait
                print("All APIs are blocked, sleeping for {:.2f}s".format(remaining))
                time.sleep(remaining + 1)
            return self._get_user_profiles(userid_list)
        except tweepy.TweepError as e:
            print("Tweepy error: {}".format(e))
            self.error_log = "Tweepy error: {}".format(e)
            return []
        else:
            return result

    def _get_userid_by_name(self, username):
        """Get userid by username"""
        try:
            u = self.api_queue[0].api.get_user(screen_name=username)
        except tweepy.RateLimitError:
            self.api_queue[0].block() # block current api
            remaining = self.recycle_apis() # recycle apis
            if(remaining > 0): # if all apis are blocked, then wait
                print("All APIs are blocked, sleeping for {:.2f}s".format(remaining))
                time.sleep(remaining + 1)
            return self._get_userid_by_name(username)
        except tweepy.TweepError as e:
            print("Tweepy error: {}".format(e))
            self.error_log = "Tweepy error: {}".format(e)
            return None
        else:
            return u.id

    def _crawl_user_tweets(self, userid):
        """Fetch user's recent 400 english tweets, by userid"""
        try:
            tweets = self.api_queue[0].api.user_timeline(user_id=userid, count=200, tweet_mode="extended", lang="en") # fetch recent 200 english tweets
            tweets = [preprocess(x.full_text) for x in tweets]
            # tweets.sort(key=len, reverse=True)
            # tweets = tweets[:5]
        except tweepy.RateLimitError:
            self.api_queue[0].block() # block current api
            remaining = self.recycle_apis() # recycle apis
            if(remaining > 0): # if all apis are blocked, then wait
                print("All APIs are blocked, sleeping for {:.2f}s".format(remaining))
                time.sleep(remaining + 1)
            return self._crawl_user_tweets(userid)
        except tweepy.TweepError as e:
            print("Tweepy error: {}".format(e))
            self.error_log = "Tweepy error: {}".format(e)
            return None
        else:
            return tweets

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
        if webapp.test_mode:
            webapp.test_tweet_str = request.form["tweet"]
        else:
            webapp.userid_str = request.form["userid"]
            webapp.username_str = request.form["username"]
        webapp.run()
    return redirect(url_for('main'))

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5678)