# This file will build a database for each of the ids in crawled csv
# How it works
# For each of the ids, read through the tweets
# run Sentiment model and Topic model on them
# calculate a representative value for these features
# store the result into a database (could be a csv file)

from model import *

# define topic category map
#            0            1          2         3            4           5
my_topics = ['computers', 'science', 'sports', 'religions', 'politics', 'others']
topic_map = {
    'alt.atheism': 5,
    'comp.graphics': 0,
    'comp.os.ms-windows.misc': 0,
    'comp.sys.ibm.pc.hardware': 0,
    'comp.sys.mac.hardware': 0,
    'comp.windows.x': 0,
    'misc.forsale': 5,
    'rec.autos': 2,
    'rec.motorcycles': 2,
    'rec.sport.baseball': 2,
    'rec.sport.hockey': 2,
    'sci.crypt': 1,
    'sci.electronics': 1,
    'sci.med': 1,
    'sci.space': 1,
    'soc.religion.christian': 3,
    'talk.politics.guns': 4,
    'talk.politics.mideast': 4,
    'talk.politics.misc': 4,
    'talk.religion.misc': 3
}

if __name__ == "__main__":
    if not os.path.exists("data.csv"):
        # load models
        model_senti = ModelSentiment()
        model_topic = ModelTopic()
        # load tweets dataframe
        tweets_data = pd.read_csv(os.path.join("..", "DataProcess", "tweets_200_processed.csv"))
        # preprocess all text
        tweets_data["Tweet"] = tweets_data["Tweet"].apply(preprocess)
        # setup output data
        output = []
        # get all user ids
        userids = tweets_data["User ID"].unique()
        # groupby ids
        data = tweets_data.groupby(["User ID"])
        print("Number of IDs = {}".format(len(userids)))
        for i, userid in enumerate(userids):
            user_topics = [0, 0, 0, 0, 0, 0]
            tweets = data.get_group(userid)["Tweet"].tolist()
            print("Current ID = {} - With {} tweets".format(userid, len(tweets)), end="")
            pos_neg = model_senti.run(tweets)
            print("\tPostive Negative decided", end="")
            topics = model_topic.run(tweets)
            print("\tTopic extracted")
            # process postive or negatives
            for sign, topic in zip(pos_neg, topics):
                # if not strong, then ignore
                # if sign > 0.6 and sign < 0.7:
                #     continue
                # else decide the sign
                sign = -1 if sign <= 0.65 else 1
                topic = topic_map[topic] # find target index
                user_topics[topic] += sign
            # average the topics
            user_topics = [x / len(tweets) for x in user_topics]
            output.append([userid] + user_topics) # store the data
            print("Processed - {} IDs left".format(len(userids) - i - 1))
        df = pd.DataFrame(output, columns=["ID", "computers", "science", "sports", "religions", "politics", "others"])
        df.to_csv("data.csv", index=False)
        print("Complete")