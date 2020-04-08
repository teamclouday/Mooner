import os
import math
import itertools
import pandas as pd
import networkx as nx

graph = nx.from_pandas_edgelist(pd.read_csv(os.path.join("..", "NetworkData", "fetchcontent.csv")))
communities = pd.read_csv("community.csv")

centrality = []
counter = 0

ratio = 0.2

for subgraphlist in communities["Members"]:
    subgraphnodes = [int(x) for x in subgraphlist.split(" | ")]
    subgraph = graph.subgraph(subgraphnodes)
    totalcentra = nx.degree_centrality(subgraph)
    totalcentra = [[k, v] for k, v in sorted(totalcentra.items(), key=lambda item: item[1])]
    result_len = math.ceil(len(totalcentra) * ratio)
    result = list(reversed(totalcentra))[:result_len]
    result_str = " | ".join([str(x) for (x, y) in result])
    centrality.append(result_str)
    print("Community {}: {}".format(counter, result))
    counter += 1

df = pd.DataFrame(centrality, columns=["Centers ID"])
df.index.rename("Commnuity Num", inplace=True)
df.to_csv("centrality.csv")