from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.database import users_collection,workspaces_collection,nodes_collection
from jose import jwt
from datetime import datetime, timedelta
from bson import ObjectId

app = FastAPI()


class LoginData(BaseModel):
    email: str
    password: str

class SignupData(BaseModel):
    username: str
    email: str
    password: str
    role:str

class WorkspaceData(BaseModel):
    newWorkspaceName: str
    newWorkspaceDescription: str
    email:str

class UserEmail(BaseModel):
    email:str

class EditUser(BaseModel):
    editUserId: str
    editUsername: str
    editEmail: str
    editRole: str
    editPassword: str

class DeleteUser(BaseModel):
    userId: str

class Node(BaseModel):
    id: str
    name: str
    x: float
    y: float

class NodesData(BaseModel):
    nodesData: list[Node]
    

origins = [
    "http://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = "a9f3c2b8d91f4e8a7c3d6f1a9b2c4d8e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token



@app.post("/login")
def login(data:LoginData):
    user = users_collection.find_one({"email": data.email})
    if not user:
       return {"emailError": "Email not found",
  "passwordError": ""}
    if user["password"] != data.password:
        return {"emailError": "",
  "passwordError": "Wrong password"}
    token = create_access_token(data={"sub": user["username"]})
    return {"access_token": token,"role": user["role"]}



@app.post("/signup")
def signup(data:SignupData):
    user = users_collection.find_one({"email": data.email})
    if user:
       return {"emailError": "Email already exists",
            "usernameError": ""}
    user2 = users_collection.find_one({"username": data.username})
    if user2:
       return {"emailError": "",
            "usernameError": "username already exists"}
    users_collection.insert_one(data.dict())
    return {"emailError": "",
    "usernameError": ""}

@app.post("/home")
def home(data:UserEmail):
    user = users_collection.find_one({"email": data.email})
    workspaces = workspaces_collection.find({"user":user["username"]})
    list_of_workspaces = []
    for workspace in workspaces:
        workspace["_id"] = str(workspace["_id"])
        list_of_workspaces.append(workspace)
    return {"workspaces": list_of_workspaces}

@app.post("/new_workspace")
def workspace(data:WorkspaceData):
    Workspace = workspaces_collection.find_one({"name":data.newWorkspaceName})
    if Workspace:
        return {"messageError": "Workspace name already exists"}
    user = users_collection.find_one({"email": data.email})
    workspace = workspaces_collection.insert_one({"name":data.newWorkspaceName,"description":data.newWorkspaceDescription,"user":user["username"],
    "nodes": [],"connections": [],"messages": []})
    workspace_id = str(workspace.inserted_id)
    return {"workspace_id": workspace_id}

@app.put("/save_workspace/{workspace_id}")
def save_workspace(workspace_id:str,data:NodesData):
    updated_nodes = []
    for node in data.nodesData:
        updated_nodes.append({
            "id": node.id,
            "name": node.name,
            "position": {
                "x": node.x,
                "y": node.y
            }
        })

    result = workspaces_collection.update_one(
        {"_id": ObjectId(workspace_id)},
        {"$set": {"nodes": updated_nodes}}
    )
    return {"count": result.modified_count}

@app.post("/load_workspace/{workspace_id}")
def load_workspace(workspace_id:str):
    workspace = workspaces_collection.find_one({"_id": ObjectId(workspace_id)})
    return {"nodes": workspace["nodes"]}

@app.post("/nodes")
def nodes():
    all_nodes = nodes_collection.find()
    nodes = []
    for node in all_nodes:
        node["_id"] = str(node["_id"])  # convert ObjectId to string
        nodes.append(node)
    return {"nodes": nodes}

@app.get("/manageusers")
def manageusers():
    users = users_collection.find()
    users_list = []
    for user in users:
        user["_id"] = str(user["_id"])  # convert ObjectId to string
        users_list.append(user)
    return {"users": users_list}

@app.post("/edit_user")
def edit_user(data:EditUser):
    user = users_collection.find_one({"_id": ObjectId(data.editUserId)})
    user1 = users_collection.find_one({"email": data.editEmail})
    user2 = users_collection.find_one({"username": data.editUsername})
    if user1 and str(user1["_id"]) != data.editUserId:
        return {"messageErrorEmail": "Email already exists"}
    if user2 and str(user2["_id"]) != data.editUserId:
        return {"messageErrorUsername": "username already exists"}
    
    user["username"] = data.editUsername
    user["email"] = data.editEmail
    user["role"] = data.editRole
    user["password"] = data.editPassword
    users_collection.update_one({"_id": ObjectId(data.editUserId) }, {"$set": user})
    return {"message": "User updated successfully"}

@app.delete("/delete_user")
def delete_user(data:DeleteUser):
    users_collection.delete_one({"_id": ObjectId(data.userId)})
    return {"message": "User deleted successfully"}