from __future__ import division
from __future__ import print_function

from pathlib import Path
from random import random                         
import sys
project_path = Path(__file__).resolve().parents[1]
sys.path.append(str(project_path))

import tensorflow as tf
import os
import scipy.sparse as sp
import numpy as np
from core.GeometricAffinityPropagation import AffinityPropagation as GeometricAffinityPropagation
from sklearn.metrics import euclidean_distances
import mygene
from collections import defaultdict
import csv

# Settings
flags = tf.compat.v1.flags
FLAGS = flags.FLAGS
flags.DEFINE_string('dataset', 'brc_microarray_usa', 'Dataset string.')
flags.DEFINE_string('embeddings', 'embeddings.txt', 'Name of file that contains the latent node features.')
flags.DEFINE_string('embedding_method', 'gcn', 'Name of output folder for the embedding method.')

flags.DEFINE_integer('max_iter', 500, 'Maximum number of iterations.')
flags.DEFINE_integer('convergence_iter', 20, 'Number of iterations with no change in the number of estimated clusters that stops the convergence.')
flags.DEFINE_float('damp_factor', 0.9, 'Damping factor for AP message updates.')

flags.DEFINE_integer('distance_threshold', 2, 'Neighborhood threshold.')
flags.DEFINE_string('similarity_metric', 'shortest_path', 'Network similarity metric.')
flags.DEFINE_bool('save_mask', True, 'Whether to save the clustering mask or not.')
flags.DEFINE_string('saving_path', '{}/data/output/mask/'.format(project_path), 'Path for saving the mask.')

flags.DEFINE_float('quantile', 0.95, 'Quantile used to determine the preference value.')
flags.DEFINE_integer('desired_nb_clusters', 500, 'Desired number of clusters.')
flags.DEFINE_integer('tolerance_nb_clusters', 100, 'Tolerance level for the number of obtained clusters.')                                                                                        
flags.DEFINE_string('clustering_method', 'geometric_ap', 'Name of output folder for the clustering method.')
flags.DEFINE_string('clusters_output', 'clusters.txt', 'Name of desired output file of obtained clusters.')
flags.DEFINE_string('modularity', 'modularity.txt', 'Name of output file of resulting modularity metric.')

#Check data availability
if not os.path.isfile("{}/data/output/network/ppi.adjacency.npz".format(project_path)):
    sys.exit("Network adjacency file is not available under /data/output/network/")
    
if not os.path.isfile("{}/data/output/{}/embedding/{}/{}".format(project_path, FLAGS.dataset, FLAGS.embedding_method, FLAGS.embeddings)):
    sys.exit("{} file is not available under /data/output/{}/embedding/{}/".format(FLAGS.embeddings, FLAGS.dataset, FLAGS.embedding_method))

if not os.path.isdir("{}/data/output/{}/clustering/{}/{}".format(project_path, FLAGS.dataset, FLAGS.clustering_method, FLAGS.embedding_method)):
    os.makedirs("{}/data/output/{}/clustering/{}/{}".format(project_path, FLAGS.dataset, FLAGS.clustering_method, FLAGS.embedding_method))
    
if not os.path.isdir("{}/data/output/mask/{}".format(project_path, FLAGS.dataset)):
    os.makedirs("{}/data/output/mask/{}".format(project_path, FLAGS.dataset))    

print("----------------------------------------")
print("----------------------------------------")
print("Clustering configuration:")
print("Dataset: {}".format(FLAGS.dataset))
print("Embedding method: {}".format(FLAGS.embedding_method))
print("Clustering Method: {}".format(FLAGS.clustering_method))
print("Clustering radius: {}".format(FLAGS.distance_threshold))
print("----------------------------------------")
print("----------------------------------------")
    
adj = sp.load_npz("{}/data/output/network/ppi.adjacency.npz".format(project_path))
adj = adj.toarray()
distance_threshold = FLAGS.distance_threshold
similarity_metric = FLAGS.similarity_metric
max_iter = FLAGS.max_iter
convergence_iter = FLAGS.convergence_iter
damp_factor = FLAGS.damp_factor

def save_clusters(labels, cluster_centers_indices, modularity):
    clusters = defaultdict(list)
    for i in range(len(labels)):
        clusters["Exemplar_{}".format(cluster_centers_indices[labels[i]])].append(i)
    with open("{}/data/output/{}/clustering/{}/{}/{}".format(project_path, FLAGS.dataset, FLAGS.clustering_method, FLAGS.embedding_method, FLAGS.clusters_output), "w", newline='', encoding="utf-8") as f:
        w_clusters = csv.writer(f, delimiter ='\t')
        for key, val in clusters.items():
            line = []
            line.append(key)
            for item in val:
                line.append(item)
            w_clusters.writerow(line)
    
    modularity_dict = {}
    modularity_dict["Modularity metric:"] = modularity
    with open("{}/data/output/{}/clustering/{}/{}/{}".format(project_path, FLAGS.dataset, FLAGS.clustering_method, FLAGS.embedding_method, FLAGS.modularity), "w", newline='', encoding="utf-8") as f:
        w_modularity = csv.writer(f, delimiter ='\t')
        for key, val in modularity_dict.items():
            w_modularity.writerow([key, val])

#===============================================================================
# def prepare_clusters_ensembl_symbols(clusters_file="clusters.txt"):
#     
#     Ids = np.genfromtxt("{}/data/output/network/ppi.ids.txt".format(project_path), dtype=np.dtype(str), delimiter="\t")
#     protein_ids = {}
#     ids_protein = {}
#     for i in range(Ids.shape[0]):
#         protein_ids[Ids[i,0]]=Ids[i,1]
#         ids_protein[Ids[i,1]]=Ids[i,0]
#             
#     mg = mygene.MyGeneInfo()
#     map_ensp_symbol={}
#     print("Request gene symbols by gene query web service...")
#     annotations = mg.querymany(protein_ids.keys(), scopes='ensembl.protein', fields='symbol', species='human')
#     #For each query map ENSPs to the gene symbol
#     for response in annotations:
#         ensp = response['query']
#         if('symbol' in response):
#             map_ensp_symbol[ensp] = response['symbol']
#         else:
#             map_ensp_symbol[ensp] = ensp
#                     
#     Clusters = open("{}/data/output/{}/clustering/{}/{}/{}".format(project_path, FLAGS.dataset, FLAGS.clustering_method, FLAGS.embedding_method, FLAGS.clusters_output), encoding="utf-8")
#     with open("{}/data/output/{}/clustering/{}/{}/{}".format(project_path, FLAGS.dataset, FLAGS.clustering_method, FLAGS.embedding_method, FLAGS.clusters_symbols), "w", newline='', encoding="utf-8") as f:
#         w_cluster = csv.writer(f, delimiter ='\t')
#         for line in Clusters:
#             line = line.strip()
#             columns = line.split("\t")
#             cl = []
#             for i in range(1, len(columns)): #Skip first column that contains the exemplar
#                 if(ids_protein[columns[i]] in map_ensp_symbol.keys()):
#                     cl.append(map_ensp_symbol[ids_protein[columns[i]]])
#             w_cluster.writerow(cl)
#     Clusters.close()
#===============================================================================
    
#===============================================================================
# Read the node embeddings                
#===============================================================================
embeddings = np.genfromtxt("{}/data/output/{}/embedding/{}/{}".format(project_path, FLAGS.dataset, FLAGS.embedding_method, FLAGS.embeddings), dtype=np.float32)

#===============================================================================
# Start the clustering by geometric affinity propagation
#===============================================================================
print("Clustering by Geometric Affinity Propagation ...")
print("Settings:")
print("Maximum iterations: {}".format(max_iter))
print("Convergence iterations: {}".format(convergence_iter))
print("Damping factor: {}".format(damp_factor))
print("Network neighborhood threshold: {}".format(distance_threshold))
print("------------------------------")

similarities = -euclidean_distances(embeddings, squared=True)

n_clusters = 0
wait_convergence = 10
quantile = FLAGS.quantile
Q = np.quantile(similarities, FLAGS.quantile)
n_clusters_list = []
preferences_list = []
if(Q==0):
    preference = np.median(similarities)
else:
    preference = np.median(similarities[np.where(similarities>Q)])
preferences_list.append(preference)
while( (np.absolute(FLAGS.desired_nb_clusters-n_clusters) > FLAGS.tolerance_nb_clusters) and wait_convergence>0):                                                                                                                 
    af = GeometricAffinityPropagation(damping=damp_factor, max_iter=max_iter, convergence_iter=convergence_iter, copy=False, preference=preference, 
                             affinity='euclidean', verbose=True, random_state=0, adjacency=adj, 
                             node_similarity_mode=similarity_metric, node_similarity_threshold=distance_threshold,
                             save_mask=FLAGS.save_mask, saving_path=FLAGS.saving_path, enable_label_smoothing=False, dataset=FLAGS.dataset).fit(embeddings)
    cluster_centers_indices = af.cluster_centers_indices_
    labels = af.labels_
    modularity = af.modularity_
    n_clusters = len(cluster_centers_indices)
    if(n_clusters>0):
        n_clusters_list.append(n_clusters)
    if (len(n_clusters_list)<2):
        if(n_clusters > FLAGS.desired_nb_clusters):
            quantile = quantile-0.15
        else:
            quantile = quantile+0.15
        
        if(quantile>=0 and quantile<=1):
            Q = np.quantile(similarities, quantile)
            if(Q==0):
                preference = preferences_list[-1]*2
            else:
                preference = np.median(similarities[np.where(similarities>Q)])
        elif(quantile<0):
            preference = preferences_list[-1]*2
        else:
            preference = preferences_list[-1]/2
        
    else:
        if (( (n_clusters_list[-2]> FLAGS.desired_nb_clusters) and (n_clusters_list[-1]> FLAGS.desired_nb_clusters) ) or ( (n_clusters_list[-2]< FLAGS.desired_nb_clusters) and (n_clusters_list[-1]< FLAGS.desired_nb_clusters) )):
            if(n_clusters > FLAGS.desired_nb_clusters):
                preference = preferences_list[-1]*2
            elif(n_clusters < FLAGS.desired_nb_clusters and n_clusters>0):
                preference = preferences_list[-1]/2
        else:
            preference = (preferences_list[-1]+preferences_list[-2])/2
        wait_convergence = wait_convergence-1
    preferences_list.append(preference)
    #This line of code is intended to ignore configurations after non-convergence
    if(set(labels)=={-1}):
        n_clusters = 0
    
print("Number of obtained clusters: {}".format(n_clusters))
print("Clustering modularity: {}".format(modularity))
if n_clusters==0:
    sys.exit("Geometric AP did not converge: Increase max_iter for convergence or tune other hyperparameters (i.e: damping factor, convergence iteration threshold)")
 
print("Save clustering results ...")
save_clusters(labels, cluster_centers_indices, modularity)
print("Clustering results saved")

#===============================================================================
# print("Preparing gene symbols for saved clusters ...")
# prepare_clusters_ensembl_symbols(clusters_file=FLAGS.clusters_output)
# print("Clusters with gene symbols saved")
#===============================================================================