import os
import itertools
import pandas as pd
import networkx as nx

graph = nx.from_pandas_edgelist(pd.read_csv(os.path.join("..", "NetworkData", "fetchcontent.csv")))
communities = pd.read_csv("community.csv")

centrality = []
counter = 0

for subgraphlist in communities["Members"]:
    subgraphnodes = [int(x) for x in subgraphlist.split(" | ")]
    subgraph = graph.subgraph(subgraphnodes)
    totalcentra = nx.degree_centrality(subgraph)
    totalcentra = [[k, v] for k, v in sorted(totalcentra.items(), key=lambda item: item[1])]
    result = list(reversed(totalcentra))[:5]
    result_str = " | ".join([str(x) for (x, y) in result])
    centrality.append(result_str)
    print("Community {} top 5: {}".format(counter, result))
    counter += 1

df = pd.DataFrame(centrality, columns=["Centers ID"])
df.index.rename("Commnuity Num", inplace=True)
df.to_csv("centrality.csv")