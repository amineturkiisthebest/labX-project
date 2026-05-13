from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")

db = client.LabXDatabase
users_collection = db.Users
workspaces_collection = db.Workspaces
nodes_collection = db.Nodes