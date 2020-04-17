# This file will build a database for each of the ids in crawled csv
# How it works
# For each of the ids, read through the tweets
# run Sentiment model and Topic model on them
# calculate a representative value for these features
# store the result into a database (could be a csv file)

from model import *

# define topic category map
#            0            1          2         3            4           5
# my_topics = ['computers', 'science', 'sports', 'religions', 'politics', 'others']
# topic_map = {
#     0: 5,
#     1: 0,
#     2: 0,
#     3: 0,
#     4: 0,
#     5: 0,
#     6: 5,
#     7: 2,
#     8: 2,
#     9: 2,
#     10: 2,
#     11: 1,
#     12: 1,
#     13: 1,
#     14: 1,
#     15: 3,
#     16: 4,
#     17: 4,
#     18: 4,
#     19: 3
# }

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
            user_topics = np.zeros(20)
            tweets = data.get_group(userid)["Tweet"].tolist()
            print("Current ID = {} - With {} tweets".format(userid, len(tweets)), end="")
            pos_neg = np.array(model_senti.run(tweets))
            print("\tPostive Negative decided", end="")
            topics = np.array(model_topic.run(tweets))
            print("\tTopic extracted")
            pos_neg = pos_neg * 2 - 1 # convert from range [0, 1] to range [-1, 1]
            topics = topics * 100 # convert probability from [0, 1] to [0, 100]
            for sign, dist in zip(pos_neg, topics):
                user_topics += sign * dist
            user_topics /= len(tweets) # take average
            # # process postive or negatives
            # for sign, topic in zip(pos_neg, topics):
            #     # if not strong, then ignore
            #     # if sign > 0.6 and sign < 0.7:
            #     #     continue
            #     # else decide the sign
            #     sign = -1 if sign <= 0.65 else 1
            #     topic = topic_map[topic] # find target index
            #     user_topics[topic] += sign
            # # average the topics
            # user_topics = [x / len(tweets) for x in user_topics]
            user_topics = user_topics.tolist()
            output.append([userid] + user_topics) # store the data
            print("Processed - {} IDs left".format(len(userids) - i - 1))
        df = pd.DataFrame(output, columns=['ID',
                                           'alt.atheism',
                                           'comp.graphics',
                                           'comp.os.ms-windows.misc',
                                           'comp.sys.ibm.pc.hardware',
                                           'comp.sys.mac.hardware',
                                           'comp.windows.x',
                                           'misc.forsale',
                                           'rec.autos',
                                           'rec.motorcycles',
                                           'rec.sport.baseball',
                                           'rec.sport.hockey',
                                           'sci.crypt',
                                           'sci.electronics',
                                           'sci.med',
                                           'sci.space',
                                           'soc.religion.christian',
                                           'talk.politics.guns',
                                           'talk.politics.mideast',
                                           'talk.politics.misc',
                                           'talk.religion.misc'])
        df.to_csv("data.csv", index=False)
        print("Complete")