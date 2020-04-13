# This folder contains all the settings for models

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' # disable tensorflow warnings
import re
import shutil
import pickle
import pandas as pd
import tensorflow as tf
from nltk.corpus import stopwords
from nltk.tokenize import RegexpTokenizer
from nltk.stem.snowball import SnowballStemmer
from nltk.stem.wordnet import WordNetLemmatizer
from gensim.models import Phrases
from gensim.models import LdaModel
from gensim.corpora import Dictionary
from gensim.models.callbacks import PerplexityMetric
from operator import itemgetter

tf.config.set_visible_devices([], 'GPU') # force use CPU, in case no GPU available

def preprocess(text):
    """General method for preprocessing tweet text"""
    # remove emojis
    text = re.sub(r"(\u00a9|\u00ae|[\u2000-\u3300]|\ud83c[\ud000-\udfff]|\ud83d[\ud000-\udfff]|\ud83e[\ud000-\udfff])", "", text)
    # remove non-ascii characters 
    text = re.sub(r"[^\x00-\x7f]", "", text)
    # remove @usernames or #tag
    text = re.sub(r"(@|#)([A-Z]|[a-z]|[0-9]|_)+", "", text)
    # remove urls
    text = re.sub(r"(http|https)://([A-Z]|[a-z]|[0-9]|/|\.)+", "", text)
    # remove spaces
    text = text.strip()
    # convert to lower format
    text = text.lower()
    # return
    return text

class ModelSentiment:
    def __init__(self):
        if not os.path.exists("model_sentiment.pkl") or not os.path.exists("model_sentiment.h5"):
            self._first_init()
        self.init()

    def init(self):
        """Load settings and model from disk"""
        with open("model_sentiment.pkl", "rb") as inFile:
            settings = pickle.load(inFile)
        self.pad_len = settings["PAD_MAXLEN"]
        self.chr_range = settings["CHR_RANGE"]
        self.stemmer = settings["STEMMER"]
        self.tokenizer = settings["TOKENIZER"]
        self.model = tf.keras.models.load_model("model_sentiment.h5")
        print("Sentiment Analysis Model Initialized")

    def run(self, data):
        """Run model on data, and return output"""
        islist = True
        if isinstance(data, str):
            data = [data] # put data in list if is string
            islist = False
        data = [self._process_str(x) for x in data] # preprocess
        data = self.tokenizer.texts_to_sequences(data) # convert to sequences
        data = tf.keras.preprocessing.sequence.pad_sequences(data, padding="post", maxlen=self.pad_len)
        result = self.model.predict(data)[0]
        result = ["positive" if x >= 0.5 else "negative" for x in result]
        #text_result = "positive" if result >= 0.5 else "negative"
        if not islist:
            result = result[0]
        return result

    def _first_init(self):
        """Initialize all required parts, and dump self"""
        with open(os.path.join("..", "SentimentAnalysis", "dataset", "sentiment140", "data.pickle"), "rb") as inFile:
            data = pickle.load(inFile)
        settings = {}
        settings["PAD_MAXLEN"] = 45
        settings["CHR_RANGE"] = list(range(97, 123)) + list(range(65, 91)) + [ord(' '), ord('\'')]
        settings["STEMMER"] = SnowballStemmer("english")
        settings["TOKENIZER"] = data[2] # load required tokenizer
        # dump
        with open("model_sentiment.pkl", "wb") as outFile:
            pickle.dump(settings, outFile)
        # move the saved model to current dir
        shutil.copyfile(os.path.join("..", "SentimentAnalysis", "models", "cnn.h5"), "model_sentiment.h5")

    def _process_str(self, raw_string):
        # first remove url, @username, etc
        raw_string = re.sub(r"(@|#)([A-Z]|[a-z]|[0-9]|_)+", "", raw_string)
        raw_string = re.sub(r"(http|https)://([A-Z]|[a-z]|[0-9]|/|\.)+", "", raw_string)
        # remove characters other than [a-z][A-Z][0-9]['!?] or empty space
        new_string = "".join([ch.lower() if ord(ch) in self.chr_range else ' ' for ch in list(raw_string)])
        # remove extra space, and also convert plural form to singular
        new_string = new_string.strip()
        new_string = " ".join([self.stemmer.stem(word) for word in new_string.split()])
        return new_string

class ModelTopic:
    def __init__(self, feed_data_path=os.path.join("..", "SentimentAnalysis", "dataset", "sentiment140", "processed.csv")):
        self.data_path = feed_data_path
        if not os.path.exists("model_topic_dict.txt") or not os.path.exists("model_topic.gensim"):
            self._first_init()
        self.init()

    def init(self):
        """load model and dictionary from disk"""
        self.dictionary = Dictionary.load_from_text("model_topic_dict.txt")
        self.model = LdaModel.load("model_topic.gensim")
        print("Topic Extraction Model Initialized")

    def run(self, data):
        """Run model on data, and return output"""
        islist = True
        if isinstance(data, str):
            data = [data]
            islist = False
        data = self._preprocessing_data(data)
        data = [self.dictionary.doc2bow(x) for x in data]
        result = [self.model[x] for x in data]
        result = [sorted(x, key=itemgetter(1), reverse=True) for x in result]
        result = [self.model.print_topic(x[0][0], 5) for x in result]
        if not islist:
            result = result[0]
        return result

    def _first_init(self):
        """train the model on data"""
        settings = {}
        print("First time init. Need to train model. Please wait")
        # Set training parameters
        num_topics = 20
        chunksize = 100
        passes = 50
        iterations = 400
        # read in file
        data = pd.read_csv(self.data_path)
        tweetslist = data['Text'].values
        tweetslist = self._preprocessing_data(tweetslist)
        # Create a dictionary representation of the documents.
        dictionary = Dictionary(tweetslist)
        # Save dict
        dictionary.save_as_text("model_topic_dict.txt")
        # Filter out words that occur less than 20 documents, or more than 50% of the documents.
        dictionary.filter_extremes(no_below=20, no_above=0.6)
        # Bag-of-words representation of the documents.
        corpus = [dictionary.doc2bow(doc) for doc in tweetslist]
        # Make a index to word dictionary.
        temp = dictionary[0]  # This is only to "load" the dictionary.
        id2word = dictionary.id2token
        # Get train model
        perplexity_logger = PerplexityMetric(corpus=corpus, logger='shell')
        model = LdaModel(corpus=corpus,
                         id2word=id2word,
                         chunksize=chunksize,
                         alpha="auto",
                         eta="auto",
                         iterations=iterations,
                         num_topics=num_topics,
                         passes=passes,
                         eval_every=None,
                         callbacks=[perplexity_logger])
        model.save("model_topic.gensim")

    def _preprocessing_data(self, data):
        """preprocess data for training"""
        # Split the documents into tokens.
        tokenizer = RegexpTokenizer(r'\w+')
        for idx in range(len(data)):
            data[idx] = data[idx].lower()  # Convert to lowercase.
            data[idx] = tokenizer.tokenize(data[idx])  # Split into words.

        # Remove pure numbers.
        data = [[token for token in doc if not token.isnumeric()] for doc in data]
        # Remove one character word.
        data = [[token for token in doc if len(token) > 1] for doc in data]
        # Remove stop words.
        stop_words = stopwords.words('english')
        data = [[word for word in doc if word not in stop_words] for doc in data]
        # Remove the words that i think is meaningless
        my_stop_words = ['rt','http','https','@']
        data = [[word for word in doc if word not in my_stop_words] for doc in data]
        # Lemmatize the documents.
        lemmatizer = WordNetLemmatizer()
        data = [[lemmatizer.lemmatize(token) for token in doc] for doc in data]

        # Compute bigrams.
        # Add bigrams and trigrams to docs (only ones that appear 20 times or more).
        bigram = Phrases(data, min_count=20)
        for idx in range(len(data)):
            for token in bigram[data[idx]]:
                if '_' in token:
                    # Token is a bigram, add to document.
                    data[idx].append(token)

        return data


if __name__ == "__main__":
    # test sentiment model
    # print("Testing Sentiment Model")
    # model_sent = ModelSentiment()
    # test_str = input("Enter test string:\n")
    # test_str = preprocess(text=test_str)
    # while test_str == "":
    #     test_str = input("Empty string. Try again:\n")
    # print(model_sent.run(test_str))
    # test topic model
    print("Testing Topic Model")
    model_topic = ModelTopic()
    test_str = input("Enter test string:\n")
    test_str = preprocess(text=test_str)
    while test_str == "":
        test_str = input("Empty string. Try again:\n")
    print(model_topic.run(test_str))