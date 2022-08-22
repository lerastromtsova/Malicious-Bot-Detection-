"""
Steps:
1. Collect user features - DONE:
    - FOAF XML ya:created
    - FOAF XML ya:created timezone
    - FOAF XML ya:subscribersCount
    - FOAF XML ya:subscribedToCount
    - comment rate: number of all comments by user in db
    - deactivated - not used as a feature but used in
      cluster analysis later on. Already present in the db.
2. Write user similarity function - DONE
   Different for:
    - nominal data type
    - real data type
3. Construct multi-attributed graph Gm
4. Convert to similarity graph Gs using (2)
5. Construct similarity matrix from Gs - DONE
6. Apply Markov clustering to the matrix - DONE:
    - expansion
    - inflation
7. Analyse each cluster one by one
"""
import pymongo  # type: ignore
from data_parser import get_foaf_data, get_activity_count
from typing import Tuple
from datetime import datetime
import pandas as pd
import itertools
import networkx as nx
import markov_clustering as mc
import json
import logging
from dotenv import dotenv_values

config = dotenv_values("../.env")
logging.basicConfig(
    filename='../log/training_graph_based_approach.log',
    encoding='utf-8',
    level=getattr(logging, config['LOG_LEVEL'].upper())
)


def enrich_users_data(
        db_client: pymongo.MongoClient,
) -> None:
    users = db_client.dataVKnodup.users.find({'enriched': {'$ne': True}})
    for i, user in enumerate(users):
        foaf = get_foaf_data(user['vk_id'])
        activity = get_activity_count(user['vk_id'], db_client)
        if foaf['created_at']:
            vk_age = (datetime(2022, 8, 1, 0, 0, 0) - foaf['created_at']).days
        else:
            vk_age = None
        db_client.dataVKnodup.users.update_one(
            {'_id': user['_id']},
            {'$set': {
                'created_at': foaf['created_at'],
                'vk_age': vk_age,
                'timezone': foaf['timezone'],
                'followee_rate': foaf['followee_rate'],
                'follower_rate': foaf['follower_rate'],
                'follower_to_followee': foaf['follower_to_followee'],
                'comment_rate': activity,
                'enriched': True
            }}
        )


def get_similarity(
        users: Tuple
) -> float:
    features = {
        'vk_age': 'real',
        'timezone': 'nominal',
        'followee_rate': 'real',
        'follower_rate': 'real',
        'follower_to_followee': 'real',
        'comment_rate': 'real'
    }
    similarities = []
    for feature, typ in features.items():
        if users[0][feature] and users[1][feature]:
            if typ == 'real':
                similarities.append(get_real_similarity((users[0][feature], users[1][feature])))
            elif typ == 'nominal':
                similarities.append(get_nominal_similarity((users[0][feature], users[1][feature])))
    avg_similarity = sum(similarities) / len(similarities)
    return avg_similarity


def get_nominal_similarity(
        values: Tuple
) -> bool:
    return values[0] == values[1]


def get_real_similarity(
        values: Tuple
) -> float:
    return 1 / (1 + abs(values[0] - values[1]))


class MarkovClusteringModel:
    def __init__(
            self,
            users,
            sim_threshold=0.6,
            inf_rate=1.1
    ):
        self.users = users
        self.sim_threshold = sim_threshold
        self.inflation_rate = inf_rate
        self.similarity_matrix = pd.DataFrame([])
        self.adjacency_matrix = pd.DataFrame([])
        self.clusters = []
        self.matrix = []
        self.raw_clusters = []
        self.modularity = 0

    def _construct_similarity_matrix(self):
        indices = [user['vk_id'] for user in self.users]
        result = pd.DataFrame(
            index=indices,
            columns=indices,
            dtype=int
        )
        for pair in itertools.product(self.users, repeat=2):
            if pair[0]['vk_id'] == pair[1]['vk_id']:
                result.at[pair[0]['vk_id'], pair[1]['vk_id']] = 0
            else:
                sim = get_similarity(pair)
                result.at[pair[0]['vk_id'], pair[1]['vk_id']] = sim
        self.similarity_matrix = result

    def _apply_similarity_threshold(self, sim):
        return int(sim * 10) if sim >= self.sim_threshold else 0

    def _get_adjacency_matrix(self):
        sim_mat = self.similarity_matrix
        self.adjacency_matrix = sim_mat.applymap(self._apply_similarity_threshold)

    def _get_clusters(self):
        self.clusters = []
        graph = nx.from_pandas_adjacency(self.adjacency_matrix)
        self.matrix = nx.to_scipy_sparse_array(graph)
        result = mc.run_mcl(self.matrix, inflation=self.inflation_rate)
        self.raw_clusters = mc.get_clusters(result)
        for cluster in self.raw_clusters:
            self.clusters.append(tuple(self.similarity_matrix.columns[i] for i in cluster))
        return result, self.raw_clusters

    def train(self, sim_thresholds, inflation_rates):
        logging.info("===TRAINING===")
        self._construct_similarity_matrix()
        modularities = {}
        for pair in itertools.product(sim_thresholds, inflation_rates):
            self.sim_threshold, self.inflation_rate = pair
            self._get_adjacency_matrix()
            result, clusters = self._get_clusters()
            modularity = mc.modularity(matrix=result, clusters=clusters)
            modularities[(self.sim_threshold, self.inflation_rate)] = modularity
        best_sim_threshold, best_infl_rate = max(modularities, key=modularities.get)
        best_modularity = max(modularities.values())
        logging.info(f"Found best params: "
                     f"{best_sim_threshold}, "
                     f"{best_infl_rate}, "
                     f"{best_modularity}")
        self.sim_threshold, self.inflation_rate = best_sim_threshold, best_infl_rate
        self.modularity = best_modularity
        self._get_adjacency_matrix()
        self._get_clusters()
        logging.info("===TRAINING END===")

    def draw_graph(self):
        mc.draw_graph(
            self.matrix,
            self.raw_clusters,
            node_size=50,
            with_labels=False,
            edge_color="silver"
        )

    def save(self, filepath):
        with open(filepath, 'w') as f:
            json.dump({
                'similarity_threshold': str(self.sim_threshold),
                'inflation_rate': str(self.inflation_rate),
                'modularity': str(self.modularity),
                'clusters': [
                    str(cluster) for cluster in self.clusters
                ]
            }, f)