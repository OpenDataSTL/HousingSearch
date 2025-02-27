# FILENAME: iterativeSearch.py

# used to run a brute-force iterative search

from node import *
import time
num_results = 10
ctr_ = 0

# iterative brute-force method
# go through all the nodes and find the ones with the smallest adjusted distance from the query node
def iterativeSearch(nodes, search_node, sqft_mult, metro_mult, k, argv):
    global ctr_
    ctr_ = 0
    nodes_and_distances = []
    for node in nodes:
        ctr_ += 1
        if node.matches_conditions(argv) == 0:
            nodes_and_distances.append((node, search_node.getDistance(node, sqft_mult, metro_mult)))
    nodes_and_distances.sort(key=(lambda x: x[1]))

    print('Iterative function calls: ' + str(ctr_))

    return nodes_and_distances[0:num_results]

