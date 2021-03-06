#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Fri Mar  9 11:31:28 2018

@author: Angelo Facchini IMT School for Advanced Studies Lucca
"""

from flask import Flask
from geopy.geocoders import Nominatim
import folium
import json
from collections import Counter
import numpy as np
from igraph import *
import requests
import pandas as pd


######### FUNCTIONS DECLARATION

def import_data_CRM():
    insightIP = 'http://178.62.229.16'
    insightPort = '8484'
    insightVersion = 'v1.0'
    insightSetting = insightIP + ':' + insightPort + '/api/' + insightVersion 
    
    page = 1
    users = []
    while(True):
        request = '/omn_crawler/get_om_user_profiles?' + 'page=' + str(page)+'&api_key=thisisinsightapikey'
        # send a request
        res = requests.get(insightSetting + request)
        
        if len(res.json()['users']) == 0:
            break
        
        users.extend(res.json()['users'])
        page += 1
    
        #Praticamente i tag sono dentro un dizionario di dizionari
    OM_data=[]
    #geolocator = Nominatim()
    #geolocator = GoogleV3()
    for u in users:
        uID=u['capsule_profile']['id']
        if u['capsule_profile']['fields']:
            for index in u['capsule_profile']['fields']:
                if index['definition']['name']=='CIty':
                    City=index['value']
        if 'extra_info' in u:
            if len(u['extra_info'])>0:
                loc=[u['extra_info']['latitude'],u['extra_info']['longitude']]
                #print loc
        else: City=[]
        if len(u['capsule_profile']['tags'])>0:
            Tags=[]
            for tag in u['capsule_profile']['tags']:
                Tags.append(tag['name'])
            
            OM_data.append([uID, City,Tags,loc])    
    OM_data_clean=clean_OM_data(OM_data)

    return OM_data_clean


def clean_OM_data(OM_data):
    for om in OM_data:
        for tag in om[2]:
            if 'MailChimp:unsubscribed' in tag:
                om[2].remove('MailChimp:unsubscribed')
            elif 'MailChimp:invalid' in tag:
                om[2].remove('MailChimp:invalid')
            elif 'Italy' in tag:
                om[2].remove('Italy')
            elif tag[-1]==u'_':
                om[2].remove(tag)
                om[2].append(tag[0:-1])   

    OM_data_clean=[]
    for om in OM_data:
        if len(om[1])!= 0 and len(om[2])!=0 and om[3][0]!=[]:
            OM_data_clean.append(om)
    return OM_data_clean



def build_OM_network():
    #Number of members to consider
    
    OM_data=import_data_CRM()
    k=len(OM_data)
    #Initialising Graph
    g=Graph()
    g.add_vertices(k)
    
    ID=[]
    lat=[]
    lon=[]
    city=[]
    tags=[]
        
    for om in OM_data:
        ID.append(om[0])
        city.append(om[1])
        tags.append(om[2])
        lat.append(om[3][0])
        lon.append(om[3][1])

    #Add features to nodes
    g.vs["ID"] = ID
    g.vs["lat"] = lat
    g.vs["lon"] = lon
    g.vs["city"] = city
    g.vs["tags"] = tags
    N_comm=2;
    g_aff=compute_aff_metrics(g,N_comm)
    return g
  
def compute_aff_metrics(g,N_comm):
    k=len(g.vs)
    for i in range (0,k):
        set1=g.vs[i]['tags']

   
        for j in range (i+1,k):     
            set2=g.vs[j]['tags']
#            if '' in set2:
 #               while '' in set2: set2.remove('')
            
            comm=list(set(set1) & set(set2))

            if (len(comm)>=N_comm):
                e1=i
                e2=j
                g.add_edge(e1,e2)
    return g



def find_communities_louvain(graph,n_vertex_limit):
    '''
    This function uses the Louvain method to find in graph
    communities larger than n_vertex_limit.
    Function returns a list of graphs
    '''
    cl_lo=graph.community_multilevel()
    # We now obtain the subgraphs of each community
    comm_sg=cl_lo.subgraphs()
    #filter out graphs
    comm_large=[]
    for comm in comm_sg:
        if len(comm.vs)>n_vertex_limit: comm_large.append(comm)

    comm_sg=comm_large
    return comm_sg



def show_network_metrics():
    '''
    Computes network metric as specified in 
    Deliverable D2.4 (Dec-17)
    '''
    g=build_OM_network()
    #number of nodes
    NN=len(g.vs)
    #number of links
    NL=len(g.es)
    #Network diameter
    diam=g.diameter()
    #Average Centrality
    AC=np.mean(g.eigenvector_centrality())
    
    metrics=[NN,NL,diam,AC]
    net_metrics=json.dumps(metrics)
    return net_metrics



def show_comm_ML_map():
    '''
    Given a set of communities (i.e. a list of graphs) plot them
    on multi-layer geo. network.
    '''
    
    #Import data and build graph
    sub_g=build_OM_network()
    
    #remove isolated nodes
    pruned_vs = sub_g.vs.select(_degree_gt=0)
    pruned_graph = sub_g.subgraph(pruned_vs)
    
    #Only return communities with at least a number of nodes >= n_vertex_limit
    n_vertex_limit=3
    comm_sg=find_communities_louvain(pruned_graph,n_vertex_limit)
    #comm_sg is a list of graphs containing the detected communities
    
    # Give a name to the communities, now is a dummy comm+number
    comm_name=[]
    for i in range(0,len(comm_sg)):
        comm_name.append('comm'+ str(i))

    #Initialising map, centered on Europe
    geolocator = Nominatim()
    Europe = geolocator.geocode('Europe')

    map_global= folium.Map(location=[Europe.latitude, Europe.longitude],
                     zoom_start=4)

   
    map_layers=[]
    for i in range(0,len(comm_sg)):
        map_comm = folium.Map(location=[Europe.latitude, Europe.longitude],
                     zoom_start=4)
        map_layers.append(map_comm)
    

    colors=['blue', 'green', 'purple', 'orange', 'darkred',
             'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue',
             'darkpurple', 'white', 'pink', 'lightblue', 'lightgreen',
             'gray', 'black', 'lightgray','red' ]


    col_i=0
    for sub_g in comm_sg:
    #fixed radius. Another posibility is to adjust the radius according to node degree.
    # In this case r= 1+sub_g.vs(i).degree()
        layer=folium.FeatureGroup(name=comm_name[col_i])
        for i in range(0,len(sub_g.vs)):
            marker=folium.CircleMarker(location=[sub_g.vs(i)["lat"][0],sub_g.vs(i)["lon"][0]], 
                             popup=str(sub_g.vs(i)["ID"][0]),
                             radius=10,
                             fill=True,
                             line_color=colors[col_i],
                             fill_color=colors[col_i],
                             fill_opacity=1.0,
                             clustered_marker = True).add_to(map_layers[col_i])
             #add layer with nodes to map
            layer.add_child(marker)
   
            neigh=sub_g.neighbors(i)
            location=[sub_g.vs(i)["lat"][0], sub_g.vs(i)["lon"][0]]
            for k in neigh:
                location2=[sub_g.vs(k)["lat"][0], sub_g.vs(k)["lon"][0]]
                points=(tuple(location),tuple(location2))
                line=folium.PolyLine(points, color=colors[col_i], weight=0.3,opacity=0.2).add_to(map_layers[col_i])
                #add layer with lines to map
                layer.add_child(line)
       
        #next colour      
        col_i=col_i+1
        #print str(col_i)+'/'+str(len(comm_sg))
        map_global.add_child(layer)
        
    map_global.add_child(folium.LayerControl())
    
    ####
    #### Uncomment this if Json output is needed
    ####
    #json_map=map_comm.get_root().to_json()
    #return json_map
    
    html_map = map_global.get_root().render()
    return html_map
    #return map_global


def show_comm_tags():
    '''
    In a specific community, or in a set of communities
    comm_sg, returns the most common n_comm tags with tag name
    and count.
    '''
    g=build_OM_network()
    comm_sg=find_communities_louvain(g,3)
    n_comm=5
    
    most_comm=[]
    for sub_g in comm_sg:
        tags_c=[]
        for i in sub_g.vs:
            t=i['tags']
            for j in t:
                tags_c.append(j)


        tags_count = Counter(tags_c)
        mc=tags_count.most_common()
        most_c=[]
            #print mc
        for i in range(0,n_comm):
            most_c.append(mc[i])
        most_comm.append(most_c)
        
        most_comm_json=json.dumps(most_comm)
    
    return most_comm_json


def show_map_network():
    # import data and build the graph according to
    # the similarity measure
    sub_g=build_OM_network()
    color='blue'
    
    #Initialising map, centered on Europe
    geolocator = Nominatim()
    Europe = geolocator.geocode('Europe')
    map_comm = folium.Map(location=[Europe.latitude, Europe.longitude],
                     zoom_start=4)

    #In the map we add a set of circles corresponding to the geo. position of the Explorer members
    #Circles have fixed radius. Another posibility is to adjust the radius according to node degree.
    # In this case r= 1+sub_g.vs(i).degree()
    for i in range(0,len(sub_g.vs)):
        folium.CircleMarker(location=[sub_g.vs(i)["lat"][0],sub_g.vs(i)["lon"][0]], 
                             popup=str(sub_g.vs(i)["ID"][0]),
                             radius=10,
                             fill=True,
                             line_color=color,
                             fill_color=color,
                             fill_opacity=1.0
                             #clustered_marker = True
                             ).add_to(map_comm)

        #We now draw lines connecting the affine members
        neigh=sub_g.neighbors(i)
        #neigh is the subgraph of all the nodes connected to node i
        location=[sub_g.vs(i)["lat"][0], sub_g.vs(i)["lon"][0]]
        for k in neigh:
            location2=[sub_g.vs(k)["lat"][0], sub_g.vs(k)["lon"][0]]
            points=(tuple(location),tuple(location2))
            folium.PolyLine(points, color="red", weight=0.3,opacity=0.2).add_to(map_comm)
    #map_comm.save('/Users/facchini/Documents/Openmaker/Network_An_API/map_OM_out.html')
    
    ####
    #### Uncomment this if Json output is needed
    ####
    #json_map=map_comm.get_root().to_json()
    #return json_map
    
    html_map = map_comm.get_root().render()
    return html_map

###################################
## ADVANCED ANALYTICS FUNCTIONS
###################################

def build_radius(cent_measure):
    meas=np.asarray(cent_measure)
    radius=np.divide(meas,np.amax(meas))
    return radius*10.0

###### SHOW MEMBER'S OWN COMMUNITY
def show_mID_community(mID):
    '''
    Shows the network structure of the community of
    the member mID (node in yellow)
    '''
    color='blue'
    
    #Build OM network
    sub_g=build_OM_network()
    
    #check if mID is isolated
    vs_ID=sub_g.vs.find(ID=mID)
    if vs_ID.degree()==0:
        #sys.exit("You have no connection with other OM members please improve your profile.")
        return "You have no connection with other OM members please improve your profile."
        
        
    #Compute communities
    #remove isolated nodes
    pruned_vs = sub_g.vs.select(_degree_gt=0)
    pruned_graph = sub_g.subgraph(pruned_vs)
    
    #Only return communities with at least a number of nodes >= n_vertex_limit
    n_vertex_limit=2
    comm_sg=find_communities_louvain(pruned_graph,n_vertex_limit)
    
    #search for mID in the communities
    
    vs_ID=[]
    for i in comm_sg:
        try: 
            vs_ID=i.vs.find(ID=mID)
            comm_ID=i
        except ValueError:
            pass
    
    #Radius proportional to betweenness
    betw=comm_ID.vs.betweenness()
    betw=build_radius(betw)
    
    #Initialising map, centered on Europe
    geolocator = Nominatim()
    Europe = geolocator.geocode('Europe')
    map_comm = folium.Map(location=[Europe.latitude, Europe.longitude],
                     zoom_start=4)
    i=[]
    #In the map we add a set of circles corresponding to the geo. position of the Explorer members
    for i in range(0,len(comm_ID.vs)):
        folium.CircleMarker(location=[comm_ID.vs(i)["lat"][0],comm_ID.vs(i)["lon"][0]], 
                             popup=str(sub_g.vs(i)["ID"][0]),
                             radius=betw[i],
                             fill=True,
                             line_color=color,
                             fill_color=color,
                             fill_opacity=1.0
                             #clustered_marker = True
                             ).add_to(map_comm)

        #We now draw lines connecting the affine members
    #i=neigh[0]
        #We now draw lines connecting the affine members
        neigh=comm_ID.neighbors(i)
        #neigh is the subgraph of all the nodes connected to node i
        location=[comm_ID.vs(i)["lat"][0], comm_ID.vs(i)["lon"][0]]
        for k in neigh:
            location2=[comm_ID.vs(k)["lat"][0], comm_ID.vs(k)["lon"][0]]
            points=(tuple(location),tuple(location2))
            folium.PolyLine(points, color="red", weight=0.3,opacity=0.2).add_to(map_comm)
        
    folium.CircleMarker(location=[vs_ID["lat"],vs_ID["lon"]], 
                             popup=str(vs_ID["ID"]),
                             radius=vs_ID.betweenness(),
                             fill=True,
                             line_color='yellow',
                             fill_color='yellow',
                             fill_opacity=1.0
                             #clustered_marker = True
                             ).add_to(map_comm)

    html_map = map_comm.get_root().render()
    return html_map

####### SHOW MEMBER'S POSITION IN THE NETWORK
    
def show_neigh_network(mID):
    color='blue'
    
    #Build OM network
    sub_g=build_OM_network()
    
    # find neighbour of mID
    vs_ID=sub_g.vs.find(ID=mID)
    neigh=sub_g.neighborhood(vs_ID)
    
    #Initialising map, centered on Europe
    geolocator = Nominatim()
    Europe = geolocator.geocode('Europe')
    map_comm = folium.Map(location=[Europe.latitude, Europe.longitude],
                     zoom_start=4)
    
    #In the map we add a set of circles corresponding to the geo. position of the Explorer members
    for i in neigh:
        folium.CircleMarker(location=[sub_g.vs(i)["lat"][0],sub_g.vs(i)["lon"][0]], 
                             popup=str(sub_g.vs(i)["ID"][0]),
                             radius=10,
                             fill=True,
                             line_color=color,
                             fill_color=color,
                             fill_opacity=1.0
                             #clustered_marker = True
                             ).add_to(map_comm)
    
    folium.CircleMarker(location=[vs_ID["lat"],vs_ID["lon"]], 
                             popup=str(vs_ID["ID"]),
                             radius=10,
                             fill=True,
                             line_color='yellow',
                             fill_color='yellow',
                             fill_opacity=1.0
                             #clustered_marker = True
                             ).add_to(map_comm)

        #We now draw lines connecting the affine members
    #i=neigh[0]
    location=[vs_ID["lat"],vs_ID["lon"]]
    for k in neigh:
        location2=[sub_g.vs(k)["lat"][0], sub_g.vs(k)["lon"][0]]
        points=(tuple(location),tuple(location2))
        folium.PolyLine(points, color="red", weight=0.4,opacity=1).add_to(map_comm)
    
    
    html_map = map_comm.get_root().render()
    return html_map

##########################################
####   BEGIN OF RECC. MODULE
##########################################
    
### Recc. according to communities
def recc_mID_comm(mID,cent_metric):
    
    allowed_cent=['betw','deg','clos','PR']
    if cent_metric not in allowed_cent:
        print "Please insert a valid centrality measure:'betw','deg','clos','PR'"
        return

    sub_g=build_OM_network()

    #check if mID is isolated
    vs_ID=sub_g.vs.find(ID=mID)
    if vs_ID.degree()==0:
        return "You have no connections with other OM members please improve your profile."

    #Compute communities
    #remove isolated nodes
    pruned_vs = sub_g.vs.select(_degree_gt=0)
    pruned_graph = sub_g.subgraph(pruned_vs)

    #Only return communities with at least a number of nodes >= n_vertex_limit
    n_vertex_limit=2
    comm_sg=find_communities_louvain(pruned_graph,n_vertex_limit)

    #find member community
    vs_ID=[]
    for i in comm_sg:
        try: 
            vs_ID=i.vs.find(ID=mID)
            comm_ID=i
        except ValueError:
            pass

    #compute centrality metrics
    if cent_metric == 'betw':
        metric=comm_ID.vs.betweenness()
    elif cent_metric == 'deg':
        metric=comm_ID.vs.degree()
    elif cent_metric == 'clos':
        metric=comm_ID.closeness()
    elif cent_metric == 'PR':
        metric=comm_ID.pagerank()

    ID=[]
    for i in range(0,len(comm_ID.vs)):
        ID.append(str(comm_ID.vs[i]['ID']))

    df = pd.DataFrame({ 
        'ID':ID,
        'met':metric
    })  

    s_df=df.sort_values(by=['met'],ascending=False)
    top_3=s_df.values[0:3];

    top_3=top_3.tolist()
    return json.dumps(top_3)

####### Rec. according to global network

def recc_mID_network(mID,cent_metric):

    allowed_cent=['betw','deg','clos','PR']
    if cent_metric not in allowed_cent:
        print "Please insert a valid centrality measure:'betw','deg','clos','PR'"
        return
    
    sub_g=build_OM_network()

    #compute centrality metrics
    if cent_metric == 'betw':
        metric=sub_g.vs.betweenness()
    elif cent_metric == 'deg':
        metric=sub_g.vs.degree()
    elif cent_metric == 'clos':
        metric=sub_g.closeness()
    elif cent_metric == 'PR':
        metric=sub_g.pagerank()

    ID=[]
    for i in range(0,len(sub_g.vs)):
        ID.append(str(sub_g.vs[i]['ID']))

    df = pd.DataFrame({ 
        'ID':ID,
        'met':metric
    })  

    s_df=df.sort_values(by=['met'],ascending=False)
    top_3=s_df.values[0:3];

    top_3=top_3.tolist()
    return json.dumps(top_3)

#### Recc. according to the member's neighbourhood
def recc_mID_neigh(mID,cent_metric):

    allowed_cent=['betw','deg','clos','PR']
    if cent_metric not in allowed_cent:
        print "Please insert a valid centrality measure:'betw','deg','clos','PR'"
        return
    
    sub_g=build_OM_network()
    
    # find neighbour of mID
    vs_ID=sub_g.vs.find(ID=mID)
    neigh=sub_g.neighborhood(vs_ID)
    nei_g=sub_g.subgraph(neigh)

    #compute centrality metrics
    if cent_metric == 'betw':
        metric=nei_g.vs.betweenness()
    elif cent_metric == 'deg':
        metric=nei_g.vs.degree()
    elif cent_metric == 'clos':
        metric=nei_g.closeness()
    elif cent_metric == 'PR':
        metric=nei_g.pagerank()

    ID=[]
    for i in range(0,len(nei_g.vs)):
        ID.append(str(nei_g.vs[i]['ID']))

    df = pd.DataFrame({ 
        'ID':ID,
        'met':metric
    })  

    s_df=df.sort_values(by=['met'],ascending=False)
    top_3=s_df.values[0:3];

    top_3=top_3.tolist()
    return json.dumps(top_3)



#####################################
### EMPTY MAP OF EUROPE, JUST TO TEST
#######################
def show_EU_map():
#Create empty map of Europe
    geolocator = Nominatim()
    Europe = geolocator.geocode('Europe')
    map_EU= folium.Map(location=[Europe.latitude, Europe.longitude],
                         zoom_start=4)
    
    #then convert it in html
    html_string = map_EU.get_root()
    map_EU_ht=html_string.render()
    
    #json_map=map_EU.get_root().to_json()
    #return json_map
    
    return map_EU_ht
    #return json_map

######################################### 
######### Begin of API INTERFACE ########
#########################################    
app = Flask(__name__)


# EU map is just to test purpose
@app.route('/EU_map')
def EU_map():
    return show_EU_map()

@app.route('/Network_map')
def Network_map():
    return show_map_network()
    
@app.route('/Network_metrics')
def Network_metrics():
    return show_network_metrics()

@app.route('/OM_communities_map')
def Network_comm():
    return show_comm_ML_map()
    
@app.route('/OM_comm_tags')
def Network_tags():
    return show_comm_tags()

@app.route('/show_mID_neigh/<name>')
def show_mID_neigh(name):
     mID='{}'.format(name)
     mID=int(mID)
     return show_neigh_network(mID)

@app.route('/show_mID_comm/<name>')
def show_mID_comm(name):
     mID='{}'.format(name)
     mID=int(mID)
     return show_mID_community(mID)

###################################
#####  Begin of API Recc. Module
###################################

@app.route('/rec_mID_neigh/<name>')
def reccom_mID_neigh(name):
    req='{}'.format(name)
    req=req.split("&") 
    mID=req[0]
    mID=int(mID)
    cent_metric=req[1]
    return recc_mID_neigh(mID,cent_metric)
 
@app.route('/rec_mID_network/<name>')
def reccom_mID_network(name):
    req='{}'.format(name)
    req=req.split("&") 
    mID=req[0]
    mID=int(mID)
    cent_metric=req[1]
    return recc_mID_network(mID,cent_metric)
 
@app.route('/rec_mID_comm/<name>')
def reccom_mID_comm(name):
    req='{}'.format(name)
    req=req.split("&") 
    mID=req[0]
    mID=int(mID)
    cent_metric=req[1]
    return recc_mID_comm(mID,cent_metric)
    


if __name__ == '__main__':
   app.run(port=5001)
