import os
import community
import pandas as pd
import networkx as nx

graphdf = pd.read_csv(os.path.join("..", "NetworkData", "fetchcontent.csv"))
G = nx.from_pandas_edgelist(graphdf)

partition = community.best_partition(G)

# following code comes from https://medium.com/@adityagandhi.7/network-analysis-and-community-structure-for-market-surveillance-using-python-networkx-65413e7b7fee

values=[partition.get(node) for node in G.nodes()]
list_com=partition.values()

# Creating a dictionary like {community_number:list_of_participants}
dict_nodes={}

# Populating the dictionary with items
for each_item in partition.items():
    community_num=each_item[1]
    community_node=str(each_item[0])
    if community_num in dict_nodes.keys():
        value=dict_nodes.get(community_num) + ' | ' + community_node
        dict_nodes.update({community_num:value})
    else:
        dict_nodes.update({community_num:community_node})

# Creating a dataframe from the diet, and getting the output into excel
community_df=pd.DataFrame.from_dict(dict_nodes, orient='index',columns=['Members'])
community_df.index.rename('Community Num' , inplace=True)
community_df.to_csv('community.csv')

print("Number of communities: {}".format(len(community_df.index)))