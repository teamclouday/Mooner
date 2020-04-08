# Just found that the json file is difficult to view in vscode
# so convert it to a CSV

import os
import json
import pandas as pd

if __name__ == "__main__":
    name = "tweets_200"
    with open(name+".json", "r") as inFile:
        data = json.load(inFile)
    df = []
    for userid in data.keys():
        tweets = data[userid]
        for tweet in tweets:
            df.append([userid, tweet])
    df = pd.DataFrame(df, columns=["User ID", "Tweet"])
    df.to_csv(name+".csv", index=False)
    print("Converted")