# FILENAME: nearestNeighbors.py

# main file for running the HOMER algorithm

from node import *
import createSet
import numpy
import urllib.request
from bs4 import BeautifulSoup
import os
import geojson as geo
import pandas as pd
import csv
import random
global sqft_mult, metro_mult, price_delta, sqft_delta, metro_delta
global grid_dim
from sklearn.linear_model import LinearRegression
import time
from iterativeSearch import *
ctr_ = 0
num_results = 10

# print results of web scraping and geojson to a csv
def print_to_csv(nodes):
    with open('housingData.csv', 'w', newline='') as csvfile:
        fieldnames = ['parcel_id', 'address', 'price', 'sqft', 'metro_dist', 'grocery', 'kid_friendly', 'status',
                      'zipcode']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for node in nodes:
            kf = 'Y' if node.kidFriendly else 'N'
            gro = 'Y' if node.nearGrocery else 'N'
            stat = 'Vacant' if node.vacant else 'Built'
            writer.writerow({
                'parcel_id': node.id,
                'address': node.address,
                'price': node.price,
                'sqft': node.sqft,
                'metro_dist': node.distanceToMetro,
                'kid_friendly': kf,
                'grocery': gro,
                'status': stat
                # 'zipcode': node.zipcode
            })


# read data from a csv file to populate the list of nodes
def read_from_csv(file):
    nodes_list = []
    with open(file,encoding='utf8',errors='ignore') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        for row in reader:
            try:
                id = int(row[0])
                address = row[1]
                price = int(row[2])
                sqft = int(row[3])
                metro_dist = float(row[4])
                kf = True if row[5] is 'Y' else False
                groc = True if row[6] is 'Y' else False
                stat = True if row[7] is 'Y' else False
                node = LotNode(id, address, price, sqft, 0, 0, vacant=stat)
                node.setKidFriendly_known(kf)
                node.setNearGrocery_known(groc)
                node.setMetroDistance(metro_dist)
                nodes_list.append(node)
            except:
                print("Reading in file header")
    return nodes_list


# convert results of geojson and web scraping into a LotNode object
def convertToNode(data, schools, parks, metro, grocery, price_dict):
    try:
        url = "https://www.stlouis-mo.gov/government/departments/sldc/real-estate" \
              "/lra-owned-property-search.cfm?detail=1&parcelId=" \
              + str(data['properties']['ParcelID'])
        page = urllib.request.urlopen(url)
        soup = BeautifulSoup(page, "lxml")
        table = soup.find('table', class_='data vertical-table striped')
        info = dict()
        # table_body = table.find('tbody')
        for row in table.findAll('tr'):
            cells = row.findAll('td')
            states = row.findAll('th')
            info[states[0].find(text=True)] = cells[0].find(text=True)

        coords = data['geometry']['coordinates']

        loc = Location(coords[0], coords[1])

        # cosine(38.63*pi/180) * 69.172
        metroDist = findClosestLocation(loc, metro) * 69.172
        schoolDist = findClosestLocation(loc, schools) * 69.172
        groceryDist = findClosestLocation(loc, grocery) * 69.172
        parkDist = findClosestLocation(loc, parks) * 69.172

        price = info['Value (Standard or Appraised)']
        # when the price is not listed, we use the default price for the corresponding neighborhood
        try:
            price = int(price.replace('$', ''))
        except:
            neighborhood = info["Neighborhood"]
            line = '123456789()\n'
            for char in line:
                neighborhood = neighborhood.replace(char, '')
            try:
                price = price_dict[neighborhood.rstrip()]
            except:
                price = 1000
            if price == 0:
                price = 1000

        node = LotNode(int(info['Parcel ID']), info['Property Address'],
                       price,
                       int(info['Lot Square Feet']), loc.x, loc.y)

        node.setKidFriendly(schoolDist, parkDist)
        node.setMetroDistance(metroDist)
        node.setNearGrocery(groceryDist)
        #print(node)

        return node
    # if property is no longer for sale or is not on the LRA website
    except Exception as e:
        print(e)
        print(data['properties']['fullAddress'])
        print(url + '\n')


# find the closest metro stop / grocery store / etc
def findClosestLocation(house, set):
    min_dist = 99999999
    for loc in set:
        min_dist = min(min_dist, loc.getDistance(house))
    return min_dist

# for a given coordinate in the price, metro, sqft dimension, find the associated anchor key
def get_anchor_code(i, j, k):
    i = min(i, 99)
    j = min(j, 99)
    k = min(k, 99)
    return i * 10000 + j * 100 + k

# populate anchor nodes
# populate database with existing houses using brute force
def warmupFill(lot_nodes, anchor_nodes, k, numInitialNodes, sample_size=10):
    global metro_mult, sqft_mult, sqft_delta, metro_delta, price_delta
    anchor_size_initial = 5

    # take random sample of lot nodes and perform regression
    # used for distance calculation

    # using this: https://towardsdatascience.com/simple-and-multiple-linear-regression-in-python-c928425168f9

    random_sample_nodes = numpy.random.choice(lot_nodes, size=sample_size, replace=False)
    sqft_vector = list(map(lambda x: x.sqft, random_sample_nodes))
    price_vector = list(map(lambda x: x.price, random_sample_nodes))
    metro_vector = list(map(lambda x: x.distanceToMetro, random_sample_nodes))
    X = numpy.array([sqft_vector, metro_vector]).transpose()

    regression = LinearRegression()  # sm.OLS(price_vector, metro_vector).fit()

    regression.fit(X, price_vector)

    # model_sqft = LinearRegression()#m.OLS(price_vector, sqft_vector).fit()
    # model_metro.fit(price_vector, metro_vector)
    # model_sqft.fit(price_vector, sqft_vector)

    metro_mult = regression.coef_[0]
    sqft_mult = regression.coef_[1]


    # populate anchor nodes
    price_delta = max(price_vector) / anchor_size_initial
    metro_delta = max(metro_vector) / anchor_size_initial
    sqft_delta = max(sqft_vector) / anchor_size_initial
    for i in range(anchor_size_initial):
        for j in range(anchor_size_initial):
            for k in range(anchor_size_initial):
                anchor_nodes[get_anchor_code(i, j, k)] = AnchorNode(get_anchor_code(i, j, k))

    # connect anchor nodes (up, down, left, right, AND diagonal)
    global grid_dim
    grid_dim = (anchor_size_initial, anchor_size_initial, anchor_size_initial)
    for i in range(anchor_size_initial):
        for j in range(anchor_size_initial):
            for k in range(anchor_size_initial):
                for i_ in range(i - 1, i + 2):
                    for j_ in range(j - 1, j + 2):
                        for k_ in range(k - 1, k + 2):
                            if (i_ < anchor_size_initial and j_ < anchor_size_initial and k_ < anchor_size_initial and
                                        i_ >= 0 and j_ >= 0 and k_ >= 0 and (i != i_ or j != j_ or k != k_)):
                                anchor_nodes[get_anchor_code(i, j, k)].addNeighbor(
                                    anchor_nodes[get_anchor_code(i_, j_, k_)])
                                # ... eww ^

    for node in lot_nodes:
        # assign it to its nearest anchor node
        node.setAnchor(findAnchorNode(node, anchor_nodes))
        findAnchorNode(node, anchor_nodes).addNeighbor(node)

    # calculate distances between nodes (note - let's not do it redundantly.  If we know a->b, we know b->a.
    # i.e. we should fill out an upper-triangular distance matrix and get the smallest (non-zero/None) distances
    # to determine our nearest-neighbors

    # idea: (probably need to use numpy)
    # A = distance matrix - generate by:
    # i:0->100
    #   j:0->100
    #       if(j<i): calculate distance (strictly < so diagonal is all 0's)
    # then do A + transpose(A), now we can find the min values on each row to find the k-n-n
    A = numpy.zeros((numInitialNodes, numInitialNodes))
    for i in range(numInitialNodes):
        for j in range(numInitialNodes):
            if j < i:
                A[i][j] = lot_nodes[i].getDistance(lot_nodes[j], sqft_mult, metro_mult)
    A = A + numpy.transpose(A)

    # now we find the smallest values in each row, return their indexes, and set those as the (initial) k-n-n
    for i in range(numInitialNodes):
        idx = numpy.argpartition(A[i], k)[0:k+2]  # get indexes of smallest values (closest distances)
        for n in idx:
            lot_nodes[i].addNeighbor((lot_nodes[n], lot_nodes[n].getDistance(lot_nodes[i], sqft_mult, metro_mult)))
        lot_nodes[i].neighbors.sort(key=(lambda x: x[1]))
        lot_nodes[i].neighbors.pop(0)  # get rid of itself
    return sqft_mult, metro_mult

# if we encounter a lotnode has attributes placing it in a non-existent dimension of anchor nodes
# expand the anchor grid to be able to contain an anchor node which holds that lotnode
def expand_anchor_grid(anchor_nodes, new_dimensions):
    global grid_dim
    old_dimensions = grid_dim
    for i in range(0, int(new_dimensions[0]) + 1):
        for j in range(0, int(new_dimensions[1]) + 1):
            for k in range(0, int(new_dimensions[2]) + 1):
                if not get_anchor_code(i, j, k) in anchor_nodes:
                    anchor_nodes[get_anchor_code(i, j, k)] = AnchorNode(get_anchor_code(i, j, k))

    for i in range(0, int(new_dimensions[0]) + 1):
        for j in range(0, int(new_dimensions[1]) + 1):
            for k in range(0, int(new_dimensions[2]) + 1):
                for i_ in range(i - 1, i + 2):
                    for j_ in range(j - 1, j + 2):
                        for k_ in range(k - 1, k + 2):
                            if (i_ < new_dimensions[0] and j_ < new_dimensions[1] and k_ < new_dimensions[2]
                                and i_ > 0 and j_ > 0 and k_ > 0 and (i != i_ or j != j_ or k != k_)):
                                if not anchor_nodes[get_anchor_code(i, j, k)].hasNeighbor(
                                        anchor_nodes[get_anchor_code(i_, j_, k_)]):
                                    anchor_nodes[get_anchor_code(i, j, k)].addNeighbor(
                                        anchor_nodes[get_anchor_code(i_, j_, k_)])

    grid_dim = new_dimensions
    return anchor_nodes

# given a lotnode, find its associated anchor node
def findAnchorNode(lot_node, anchor_nodes):
    global price_delta, sqft_delta, metro_delta, grid_dim
    price_coord = lot_node.price // price_delta
    sqft_coord = lot_node.sqft // sqft_delta
    try:
        if metro_delta is not None:
            metro_coord = lot_node.distanceToMetro // metro_delta
            return anchor_nodes[get_anchor_code(price_coord, sqft_coord, metro_coord)]
        return anchor_nodes[get_anchor_code(price_coord, sqft_coord, 0)]
    except:
        if metro_delta is not None:
            metro_coord = lot_node.distanceToMetro // metro_delta
            # print(len(anchor_nodes.keys()))
            expand_anchor_grid(anchor_nodes, (
                max(price_coord, grid_dim[0]), max(sqft_coord, grid_dim[1]), max(metro_coord, grid_dim[2])))
            # print(len(anchor_nodes.keys()))
            return anchor_nodes[get_anchor_code(price_coord, sqft_coord, metro_coord)]
        expand_anchor_grid(anchor_nodes, (
            max(price_coord, grid_dim[0]), max(sqft_coord, grid_dim[1]), max(0, grid_dim[2])))
        return anchor_nodes[get_anchor_code(price_coord, sqft_coord, 0)]

# recursive K-nearest neighbors search
def find_nearest_neighbors(starting_node, searching_node, k, neighbor_list, neighbor_counter, close_matches_list,
                           argv, first_search=True):

    global sqft_mult, metro_mult, ctr_
    ctr_ += 1


    # only proceed if the desired number of results has not already been found
    if neighbor_counter < num_results:
        possible_new_neighbors = []

        # first, add the nodes at this level of recursion
        # [print(n) for n in searching_node.neighbors]
        # print(searching_node.neighbors[0][0].neighbors)
        immediate_neighbors = []
        if first_search:
            immediate_neighbors.append(starting_node.anchor_node)

            for a_node in starting_node.anchor_node.neighbors:

                if type(a_node) is AnchorNode:
                    immediate_neighbors.append(a_node)
        else:
            immediate_neighbors.append(searching_node[0].anchor_node)

        # find possible nearest neighbors and append them to a list, sorted by distance

        for a_node in immediate_neighbors:
            for connected_node in a_node.neighbors:
                if type(connected_node) is LotNode and type(starting_node) is LotNode:
                    lot_tuple = connected_node, starting_node.getDistance(connected_node, sqft_mult,
                                                                                   metro_mult)
                    if lot_tuple not in starting_node.neighbors:
                        if argv == {}:

                            if len(connected_node.neighbors) < k or connected_node.getDistance(starting_node, sqft_mult, metro_mult) \
                                    < connected_node.neighbors[-1][1]:
                                # replace furthest neighbor of the searching node with this new node, then sort

                                connected_node.neighbors.insert(len(connected_node.neighbors)-1, (starting_node, connected_node.getDistance(starting_node, sqft_mult, metro_mult)))
                                connected_node.neighbors.sort(key=(lambda x: x[1]))

                            if lot_tuple not in possible_new_neighbors:
                                possible_new_neighbors.append(lot_tuple)
                                neighbor_counter += 1

                        else:
                            # check to see if the node matches all the conditions, or all but one
                            # otherwise it does not qualify as a valid result
                            if connected_node.matches_conditions(argv) == 0:
                                if lot_tuple not in possible_new_neighbors:
                                    possible_new_neighbors.append(lot_tuple)
                                    neighbor_counter += 1

                            elif connected_node.matches_conditions(argv) == 1:
                                if lot_tuple not in close_matches_list:
                                    close_matches_list.append(lot_tuple)
                elif type(connected_node) is AnchorNode and connected_node not in immediate_neighbors:
                    immediate_neighbors.append(connected_node)

        for next_node in possible_new_neighbors:
            find_nearest_neighbors(starting_node, next_node, k, neighbor_list, neighbor_counter, close_matches_list, argv, first_search=False)

        neighbor_list += possible_new_neighbors

        neighbor_list.sort(key=(lambda x: x[1]))
        if len(neighbor_list) > num_results:
            neighbor_list = neighbor_list[0:num_results]

        return neighbor_list

# add a node to the list of lotnodes
def add_node_to_database(node, k, anchor_nodes):
    # node.addNeighbor(findAnchorNode(node, anchor_nodes))  # add the anchor node
    node.setAnchor(findAnchorNode(node, anchor_nodes))
    findAnchorNode(node, anchor_nodes).addNeighbor(node)

    # add the neighbor nodes
    k_nearest_neighbors = find_nearest_neighbors(node, findAnchorNode(node, anchor_nodes), k, [], 0, [], {})
    for n in k_nearest_neighbors:
        node.addNeighbor(n)

# method for populating sets, and calling other methods to get the necessary nodes
def populate_database(lot_nodes):
    global sqft_mult, metro_mult

    # node lists (anchor nodes need to be Random access, lot nodes theoretically don't - this is only used for
    # initialization

    # create set of grocery stores
    grocery_stores = createSet.populateGroceryStoreList()

    # create set of metro stops
    metro_stops = createSet.populateMetroList()

    # create set of schools
    schools = createSet.populateSchoolList()

    # create set of parks
    parks_and_playgrounds = createSet.populateParksandPlaygroundsList()

    file_loc = "https://raw.githubusercontent.com/andrewsavino1/HousingSearch/master/Data/missing_price.csv"

    # list of default prices by neighborhood
    price_list = pd.read_csv(file_loc)
    price_dict = dict(zip(price_list.Neighborhood, price_list.Price))

    # call convertToNode on every row of the data file
    callstr = os.getcwd() + '\\Data\\lra.geojson'
    file = geo.load(open(callstr))
    index = 0
    for dataline in file['features']:
        index += 1
        if index > 9000:
            node = convertToNode(dataline, schools, parks_and_playgrounds, metro_stops, grocery_stores, price_dict)
            if node is not None:
                lot_nodes.append(node)

# used to populate data when csv data already exists
def create_graph_space(lot_nodes, anchor_nodes, k, sample_size, warmup_size):
    # run warmupFill to start populating the database (split the list into 2 sublists, warm-up and all else (or just
    # pick an index to be the cutoff

    global sqft_mult, metro_mult
    sqft_mult, metro_mult = warmupFill(lot_nodes[:warmup_size], anchor_nodes, k, warmup_size, sample_size)

    # do fill up everything else
    for node in lot_nodes[warmup_size:]:
        add_node_to_database(node, k, anchor_nodes)

# get user input for running a query
def get_search_parameters():
    price_min_input = input("Enter a price minimum (or 'N' if not applicable): ")
    while not checkInt(price_min_input):
        print("Error. Price minimum must be a integer value.")
        price_min_input = input("Enter a price minimum (or 'N' if not applicable): ")

    price_max_input = input("Enter a price maximum (or 'N' if not applicable): ")
    while not checkInt(price_max_input):
        print("Error. Price maximum must be a integer value.")
        price_max_input = input("Enter a price maximum (or 'N' if not applicable): ")

    metro_dist_input = input("Enter a maximum acceptable distance (in miles) to a metro stop (or 'N' if not applicable): ")
    while not checkInt(metro_dist_input):
        print("Error. Distance maximum must be a numerical value.")
        metro_dist_input = input("Enter a maximum acceptable distance to a metro stop (or 'N' if not applicable):")

    acreage_min_input = input("Enter a minimum acceptable square footage (or 'N' if not applicable): ")
    while not checkInt(acreage_min_input):
        print("Error. Square footage minimum must be an integer value.")
        acreage_min_input = input("Enter a minimum acceptable square footage (or 'N' if not applicable): ")

    grocery_input = input("Do you need to be within walking distance of a grocery store? Y/N: ")
    while not checkBin(grocery_input):
        print("Error. Entered value must be either 'Y' or 'N'.")
        grocery_input = input("Do you need to be within walking distance of a grocery store? Y/N: ")

    family_input = input("Do you require a family-friendly property? Y/N: ")
    while not checkBin(family_input):
        print("Error. Entered value must be either 'Y' or 'N'.")
        family_input = input("Do you require a family-friendly property? Y/N: ")

    property_input = input("Do you wish to search over empty lots? Y/N: ")
    while not checkBin(property_input):
        print("Error. Entered value must be either 'Y' or 'N'.")
        family_input = input("Do you ish to search over empty lots? Y/N:  ")

    price_min = 0 if price_min_input == 'N' else int(str(price_min_input))
    price_max = 99999999 if price_max_input == 'N' else int(str(price_max_input))
    metro_dist = 99999999 if metro_dist_input == 'N' else float(str(metro_dist_input))
    acreage_min = 0 if acreage_min_input == 'N' else int(str(acreage_min_input))

    grocery = True if str(grocery_input) == "Y" else False
    family = 0 if str(family_input) == "Y" else 99999
    property = True if str(property_input) == "Y" else False

    dummy_node = LotNode(0, '', price_min, acreage_min, 0, 0)
    dummy_node.setNearGrocery(grocery)
    dummy_node.setMetroDistance(metro_dist)
    dummy_node.setKidFriendly(family, family)

    argv = {
        'minPrice': price_min,
        'maxPrice': price_max,
        'vacant': property,
        'minSqft': acreage_min,
        'kidFriendly': family,
        'distanceToMetro': metro_dist,
        'grocery': grocery
    }

    return dummy_node, argv


# check that user argument is a valid integer
def checkInt(s):
    try:
        float(str(s))
        return True
    except ValueError:
        if str(s) == 'N':
            return True
        return False


# check that user argument is valid binary value
def checkBin(s):
    if str(s) == 'N' or str(s) == 'Y':
        return True
    return False

# main method for running a search
def runIt():
    # parameters:
    k = 5
    anchor_nodes = {}

    files = ['housingData1500.csv', 'housingData3000.csv'] # , 'housingData4500csv', 'housingData6000csv', 'housingData7500csv', 'housingData9000csv', 'housingData11000csv']

    lot_nodes = []

    for file in files:
        lot_nodes.extend(read_from_csv(file))

    print('Populating database. This may take a moment.')

    # populate the data structures
    create_graph_space(lot_nodes, anchor_nodes, k, sample_size=200, warmup_size=len(lot_nodes))

    # continuously request user input and perform a query
    # return results and the runtime, and check that
    while True:
        neighbor_list = []
        close_matches = []
        neighbor_counter = 0

        dummy_node, argv = get_search_parameters()
        dummy_node.setAnchor(findAnchorNode(dummy_node, anchor_nodes))

        neighbors = find_nearest_neighbors(dummy_node, findAnchorNode(dummy_node, anchor_nodes), k, neighbor_list,
                                           neighbor_counter, close_matches, argv)

        close_matches = close_matches[0:min(num_results, len(close_matches)-1)]

        if len(neighbors) != 0 and len(close_matches) != 0:
            print('SEARCH RESULTS: \n')
            for n in neighbors: print(n[0])
            print('\nCLOSE MATCHES: ')
            for n in close_matches: print(n[0])
        elif len(neighbors) != 0:
            print('SEARCH RESULTS: \n')
            for n in neighbors: print(n[0])
            print('\nNo close matches found.')
        elif len(close_matches) != 0:
            print('\nNo exact matches found.')
            print('CLOSE MATCHES: \n')
            for n in close_matches: print(n[0])
        else:
            print('Sorry, your search did not return any results. Please try again.')


# main method for running a test
def testIt():
    # parameters:
    k = 5
    anchor_nodes = {}

    files = ['housingData1500.csv', 'housingData3000.csv']#, 'housingData4500csv', 'housingData6000csv', 'housingData7500csv', 'housingData9000csv', 'housingData11000csv']

    lot_nodes = []

    for file in files:
        lot_nodes.extend(read_from_csv(file))

    create_graph_space(lot_nodes, anchor_nodes, k, sample_size=200, warmup_size=len(lot_nodes))

    nn_o = []
    iter_o = []
    seeding = [2, 3, 5, 6, 7, 8, 9, 10, 35, 13]

    # run 10 seeded tests
    # seeding ensures fair comparison between trials
    while len(nn_o) < 10:
        global ctr_
        ctr_ = 0
        neighbor_list = []
        close_matches = []
        neighbor_counter = 0
        random.seed(seeding[len(nn_o)])
        price_min = random.randint(100, 1000)
        price_max = random.randint(10, 1500) + price_min
        acreage_min = random.randint(0, 600)
        metro_dist = float(random.randint(10, 100))/40.0
        family = float(random.randint(0, 3))/10.0
        grocery = bool(random.getrandbits(1))
        property = bool(random.getrandbits(1))

        dummy_node = LotNode(0, '', price_min, acreage_min, 0, 0)
        dummy_node.setNearGrocery(grocery)
        dummy_node.setMetroDistance(metro_dist)
        dummy_node.setKidFriendly(family, family)

        argv = {
            'minPrice': price_min,
            'maxPrice': price_max,
            'vacant': property,
            'minSqft': acreage_min,
            'kidFriendly': family,
            'distanceToMetro': metro_dist,
            'grocery': grocery
        }
        dummy_node.setAnchor(findAnchorNode(dummy_node, anchor_nodes))

        neighbors = find_nearest_neighbors(dummy_node, findAnchorNode(dummy_node, anchor_nodes), k, neighbor_list,
                                           neighbor_counter, close_matches, argv)

        nn_o.append(ctr_)
        iter_o.append(len(lot_nodes))

        neighbors_2 = iterativeSearch(lot_nodes, dummy_node, sqft_mult, metro_mult, k, argv)

        try:
            assert set(neighbors) == set(neighbors_2)
            print('Success! The lists returned by the iterative search and the nearest-neighbors search are identical.')
            for n in neighbors: print(n[0])
        except:
            print('Error: The lists returned by the iterative search and the nearest-neighbors search are different.')
            print('Nearest neighbor search results:')
            for n in neighbors: print(n[0])
            print('\nIterative search results:')
            for n in neighbors_2: print(n[0])

    print('Average number of calls to nearest-neighbor: ' + str(float(sum(nn_o))/float(len(nn_o))))
    print('Average number of calls to iterative method: ' + str(float(sum(iter_o))/float(len(iter_o))))


# main method for making csv files using geojson and web scraping
def populate_csv():
    k = 5
    lot_nodes = []
    anchor_nodes = {}
    populate_database(lot_nodes)
    print_to_csv(lot_nodes)


# change runIt() to testIt() to perform tests, or populate_csv() to populate csv files
if __name__ == '__main__': runIt()
