import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import re
import pickle
import numpy as np
import tensorflow as tf
from nltk.stem.snowball import SnowballStemmer

stemmer = SnowballStemmer("english")
ch_range = list(range(97, 123)) + list(range(65, 91)) + [ord(' '), ord('\'')]
def process_str(raw_string):
    global ch_range
    global stemmer
    # first remove url, @username, etc
    raw_string = re.sub(r"(@|#)([A-Z]|[a-z]|[0-9]|_)+", "", raw_string)
    raw_string = re.sub(r"(http|https)://([A-Z]|[a-z]|[0-9]|/|\.)+", "", raw_string)
    # remove characters other than [a-z][A-Z][0-9]['!?] or empty space
    new_string = "".join([ch.lower() if ord(ch) in ch_range else ' ' for ch in list(raw_string)])
    # remove extra space, and also convert plural form to singular
    new_string = new_string.strip()
    new_string = " ".join([stemmer.stem(word) for word in new_string.split()])
    return new_string

with open(os.path.join("dataset", "sentiment140", "data.pickle"), "rb") as inFile:
    data = pickle.load(inFile)
tokenizer = data[2]
PAD_MAXLEN = 45
model = tf.keras.models.load_model(os.path.join("models", "cnn.h5"))

while True:
    text = input("Enter the text you want to classify (enter \"exit\" to exit):\n>>> ")
    if text == "exit":
        break
    text_processed = process_str(text)
    text_processed = tokenizer.texts_to_sequences([text_processed])
    text_processed = tf.keras.preprocessing.sequence.pad_sequences(text_processed, padding="post", maxlen=PAD_MAXLEN)
    result = model.predict(text_processed)[0][0]
    text_result = "positive" if result >= 0.5 else "negative"
    print("Result: {} - Actual Output: {}\n".format(text_result, result))