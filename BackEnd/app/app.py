from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import time
from pydantic import BaseModel
from app.database import users_collection,workspaces_collection,nodes_collection,messages_collection
from jose import jwt
from datetime import datetime, timedelta
from bson import ObjectId
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from passlib.context import CryptContext
import scapy.all as scapy
from scapy.all import IP,UDP,TCP, Raw, send,wrpcap
import socket
import threading
import random
import struct
# pyrefly: ignore [missing-import]
import httpx

app = FastAPI()


class LoginData(BaseModel):
    email: str
    password: str

class SignupData(BaseModel):
    username: str
    email: str
    password: str
    role:str

class WorkspaceData2(BaseModel):
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
    ip: str
    mcc: str
    mnc: str
    url: str
    mode: str
    configured: bool = False
    isUnderTest: bool = False

class Connection(BaseModel):
    rootNodeName: str
    targetNodeName: str
    from_id: str
    to_id: str
    interface_name: str

class Message(BaseModel):
    id:str
    label: str
    description: str
    content: str
    type: str
    protocol: str
    source: str
    destination: str
    interface: str

class Messages(BaseModel):
    from_name: str
    to_name: str
    from_id: str
    to_id: str
    message: str

class Frequency(BaseModel):
    frequency: str

class DiameterMessage(BaseModel):
    diameter_message: str
    frequency: str

class MessageData(BaseModel):
    messages: list[Messages]

class WorkspaceData(BaseModel):
    nodesData: list[Node]
    existingConnections: list[Connection]
    messages: list[Message]

class TestNodesData(BaseModel):
    nodesData: list[Node]
    existingConnections: list[Connection]

class ConfigureService(BaseModel):
    service_name: str
GTP_MESSAGES = {

    "Create Session Request": {
        "message_type": 32
    },

    "Create Session Response": {
        "message_type": 33
    },

    "Modify Bearer Request": {
        "message_type": 34
    },

    "Modify Bearer Response": {
        "message_type": 35
    },

    "Delete Session Request": {
        "message_type": 36
    },

    "Delete Session Response": {
        "message_type": 37
    }
}
GTP_IE = {

    "IMSI": 1,

    "Cause": 2,

    "Recovery": 3,

    "APN": 71,

    "EPS Bearer ID": 73,

    "F-TEID": 87,

    "Bearer Context": 93,

    "PDN Address Allocation": 79,

    "Serving Network": 83,

    "RAT Type": 82
}

class GTPHeader:
    def __init__(
        self,
        message_type,
        teid,
        seq,
        payload_length=0
    ):
        self.version = 2
        self.pt = 1
        self.message_type = message_type
        self.teid = teid
        self.seq = seq
        self.payload_length = payload_length
    def encode(self, payload_length):
        flags = (
            (self.version << 5) |
            (self.pt << 4) |
            0x08      # TEID flag set
        )

        return (
            struct.pack("!B", flags) +
            struct.pack("!B", self.message_type) +
            struct.pack("!H", payload_length) +
            struct.pack("!I", self.teid) +
            struct.pack("!I", (self.seq << 8))
        )
class GTPInformationElement:

    def __init__(
        self,
        ie_type,
        instance,
        value
    ):
        self.ie_type = ie_type
        self.instance = instance
        self.value = value
    def encode(self):
        value = self.value
        ie = b""
        ie += struct.pack("!B", self.ie_type)
        ie += struct.pack("!H", len(value))
        ie += struct.pack("!B", self.instance)

        ie += value

        return ie

class DiameterHeader:

    def __init__(
        self,
        command_code,
        application_id,
        flags,
        hop_id,
        end_id
    ):
        self.version = 1
        self.command_code = command_code
        self.application_id = application_id
        self.flags = flags
        self.hop_id = hop_id
        self.end_id = end_id
    def encode(self, message_length):

        return struct.pack(
            "!B3sB3sIII",

            self.version,

            message_length.to_bytes(3, "big"),

            self.flags,

            self.command_code.to_bytes(3, "big"),

            self.application_id,

            self.hop_id,

            self.end_id
        )
class DiameterAVP:

    def __init__(
        self,
        code,
        value,
        mandatory=True,
        vendor_id=None
    ):
        self.code = code
        self.value = value
        self.mandatory = mandatory
        self.vendor_id = vendor_id
    def encode(self):
        flags = 0x40 if self.mandatory else 0x00

        if self.vendor_id is not None:
            flags |= 0x80

        header_size = 12 if self.vendor_id is not None else 8
        length = header_size + len(self.value)

        avp = b""

        # AVP Code
        avp += struct.pack("!I", self.code)

        # Flags + Length
        avp += struct.pack(
            "!B3s",
            flags,
            length.to_bytes(3, "big")
        )

        if self.vendor_id is not None:
            avp += struct.pack("!I", self.vendor_id)

        avp += self.value

        padding = (4 - (len(avp) % 4)) % 4
        avp += b"\x00" * padding
        return avp

#Origin-Host and Origin-Realm are UTF-8 encoded
def encode_utf8(value: str) -> bytes:
    return value.encode("utf-8")

#Vendor-Id
def encode_uint32(value: int) -> bytes:
    return struct.pack("!I", value)

#for IPv4 address
def encode_ipv4(ip):
    return struct.pack("!H", 1) + socket.inet_aton(ip)
    
def encode_uint8(value):
    return struct.pack("!B", value)
ENCODERS = {
    "UTF8String": encode_utf8,
    "Unsigned32": encode_uint32,
    "Address": encode_ipv4,
}
AVP_DICTIONARY = {
    "Origin-Host": {
        "code": 264,
        "type": "UTF8String"
    },

    "Origin-Realm": {
        "code": 296,
        "type": "UTF8String"
    },

    "Vendor-Id": {
        "code": 266,
        "type": "Unsigned32"
    },

    "Host-IP-Address": {
        "code": 257,
        "type": "Address"
    }
}
DIAMETER_MESSAGES = {
    "CER": {
        "command_code": 257,
        "application_id": 0,
        "flags": 0x80,
    },
    "CEA": {
        "command_code": 257,
        "application_id": 0,
        "flags": 0x00,
    },
    "DWR": {
        "command_code": 280,
        "application_id": 0,
        "flags": 0x80,
    },
    "RAR": {
        "command_code": 258,
        "application_id": 0,
        "flags": 0x80,
    },
    "RAA": {
        "command_code": 258,
        "application_id": 0,
        "flags": 0x00,
    },
    "AIR": {
        "command_code": 318,
        "application_id": 16777251,
        "flags": 0xC0,
    },
}

running_tests = {}

running_tests_protocol = {}


created_nodes = set()
created_peers = {}

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

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token

def generate_report(workspace_name, results,total_nodes,total_connections,packets_sent,successful_tests,failed_tests,success_rate):
    pdf_file = f"reports/{workspace_name}.pdf"
    doc = SimpleDocTemplate(pdf_file)
    styles = getSampleStyleSheet()
    elements = []
    elements.append(
        Paragraph(
            f"LabX Test Report - {workspace_name}",
            styles["Title"]
        )
    )
    elements.append(Spacer(1, 12))
    elements.append(
        Paragraph(
            f"Workspace: {workspace_name}",
            styles["Normal"]
        )
    )

    elements.append(
        Paragraph(
            f"Generated: {datetime.now()}",
            styles["Normal"]
        )
    )

    elements.append(Spacer(1, 20))
    elements.append(
        Paragraph(
            "Summary",
            styles["Heading2"]
        )
    )

    elements.append(
        Paragraph(
            f"Total Nodes Under Test: {total_nodes}",
            styles["Normal"]
        )
    )

    elements.append(
        Paragraph(
            f"Total Connections: {total_connections}",
            styles["Normal"]
        )
    )

    elements.append(
        Paragraph(
            f"Packets sent: {packets_sent}",
            styles["Normal"]
        )
    )

    elements.append(
        Paragraph(
            f"Successful Tests: {successful_tests}",
            styles["Normal"]
        )
    )

    elements.append(
        Paragraph(
            f"Failed Tests: {failed_tests}",
            styles["Normal"]
        )
    )

    elements.append(
        Paragraph(
            f"Success Rate: {success_rate:.2f}%",
            styles["Normal"]
        )
    )

    elements.append(Spacer(1, 20))

    elements.append(
        Paragraph(
            "Test Results",
            styles["Heading2"]
        )
    )
    for result in results:
        elements.append(
            Paragraph(
                f"{result['source']} → "
                f"{result['destination']} "
                f"({result['interface']}) : "
                f"{result['status']}",
                styles["Normal"]
            )
        )
    doc.build(elements)
    return pdf_file



@app.post("/login")
def login(data:LoginData):
    user = users_collection.find_one({"email": data.email})
    if not user:
       return {"emailError": "Email not found",
  "passwordError": ""}
    if not verify_password(
        data.password,
        user["password"]):
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
    hashed_password = hash_password(data.password)
    users_collection.insert_one({
        "username": data.username,
        "email": data.email,
        "password": hashed_password,
        "role":data.role
    })
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
def workspace(data:WorkspaceData2):
    Workspace = workspaces_collection.find_one({"name":data.newWorkspaceName})
    if Workspace:
        return {"messageError": "Workspace name already exists"}
    user = users_collection.find_one({"email": data.email})
    workspace = workspaces_collection.insert_one({"name":data.newWorkspaceName,"description":data.newWorkspaceDescription,"user":user["username"],
    "nodes": [],"connections": [],"messages": [],"is_ready":False})
    workspace_id = str(workspace.inserted_id)
    return {"workspace_id": workspace_id}

@app.put("/save_workspace/{workspace_id}")
def save_workspace(workspace_id:str,data:WorkspaceData):
    updated_nodes = []
    for node in data.nodesData:
        updated_nodes.append({
            "id": node.id,
            "name": node.name,
            "position": {
                "x": node.x,
                "y": node.y
            },
            "ip": node.ip,
            "url": node.url,
            "mcc": node.mcc,
            "mnc": node.mnc,
            "mode": node.mode,
            "configured":node.configured,
            "isUnderTest":node.isUnderTest
        })
    updated_connections = []
    for connection in data.existingConnections:
        updated_connections.append({
            "from_id": connection.from_id,
            "to_id": connection.to_id,
            "fromNodeName": connection.rootNodeName,
            "toNodeName": connection.targetNodeName,
            "name":connection.interface_name
        })
    updated_messages = []
    for message in data.messages:
        updated_messages.append({
            "id": message.id,
            "label": message.label,
            "description": message.description,
            "content": message.content,
            "type": message.type,
            "protocol": message.protocol,
            "source": message.source,
            "destination": message.destination,
            "interface": message.interface
        })

    result = workspaces_collection.update_one(
        {"_id": ObjectId(workspace_id)},
        {"$set": {"nodes": updated_nodes,
            "connections": updated_connections,"messages": updated_messages}}
    )
    return {"count": result.modified_count}

@app.post("/generate_pdf_report/{workspace_id}")
def generate_pdf_report(workspace_id:str,data:TestNodesData):
    workspace = workspaces_collection.find_one({"_id": ObjectId(workspace_id)})
    if (workspace):
        test_results = []
        source_node = None
        destination_node = None
        packets_sent = 0
        total_nodes_under_test=0
        total_connections=0
        if(data.existingConnections):
            for connection in data.existingConnections:
                total_connections= total_connections + 1
                for node in data.nodesData:
                    if node.id == connection.from_id:
                        source_node = node
                    if node.id == connection.to_id:
                        destination_node = node
                if source_node and destination_node:
                    if source_node.isUnderTest or destination_node.isUnderTest:
                        total_nodes_under_test = total_nodes_under_test + 1
                        if(source_node.ip or destination_node.ip):
                            packets_sent = packets_sent+1
                            test_results.append({
                                "source": source_node.name,
                                "destination": destination_node.name,
                                "interface": connection.interface_name,
                                "status": "PASS"
                        })
        else:
            return {
                "message": "No connections in the workspace"
            }
    successful_tests = len(
    [r for r in test_results if r["status"] == "PASS"]
    )
    failed_tests = len(
    [r for r in test_results if r["status"] == "FAIL"]
    )
    success_rate = (
    successful_tests / packets_sent * 100
    if packets_sent > 0
    else 0
)
    pdf_file_path = generate_report(workspace["name"], test_results,total_nodes_under_test,total_connections,
                                    packets_sent,successful_tests,failed_tests,success_rate)
    return {
        "message": "PDF report generated successfully",
        "pdf_path": pdf_file_path
    }

                    
@app.post("/load_call_flow_messages/{workspace_id}")
def load_call_flow_messages(workspace_id:str):
    found_messages = list(messages_collection.find({"workspace_id": workspace_id}))
    workspace = workspaces_collection.find_one({"_id": ObjectId(workspace_id)})
    if(workspace):
        workspaces_collection.update_one(
        {"_id": ObjectId(workspace_id)},
        {"$set": {"is_ready":True}}
    )
    if (found_messages):
        for msg in found_messages:
            msg["_id"] = str(msg["_id"])
        return {"call_flow_messages": found_messages}
    else:
        return {"call_flow_messages": ""}

                
@app.post("/save_call_flow/{workspace_id}")
def save_call_flow(workspace_id:str,data:MessageData):
    workspace = workspaces_collection.find_one({"_id": ObjectId(workspace_id)})
    if (workspace):
        call_flow_messages = []
        for data in data.messages:
            workspace_messages = next(
            (
            msg for msg in workspace["messages"]
                if msg["id"] == f"{data.from_id}/{data.to_id}" or msg["id"] == f"{data.to_id}/{data.from_id}"
                ),
                None
            )
            node = next(
            (
                node for node in workspace["nodes"]
                if node["id"] == f"{data.to_id}"
            ),
            None
            )
            if (workspace_messages):
                if(node["mcc"] and node["mnc"]):
                    supi = f"imsi-{node["mcc"]}{node["mnc"]}000000001"
                else:
                    supi = "imsi-001010000000001"
                call_flow_messages.append({
                    "label": data.message,
                    "protocol":workspace_messages["protocol"],
                    "procedure":"",
                    "workspace_id":workspace_id,
                    "ip": node["ip"],
                    "message_type": "request",
                    "source": data.from_name,
                    "destination": data.to_name,
                    "interface": workspace_messages["interface"],
                    "MessageContents": {
                     "http": {},
                     "body": {"supi": supi,
                            "dnn": "internet"}
                    }
                })
            else:
                call_flow_messages.append({
                    "label": data.message,
                    "protocol":"",
                    "procedure":"",
                    "workspace_id":workspace_id,
                    "ip": node["ip"],
                    "message_type": "request",
                    "source": data.from_name,
                    "destination": data.to_name,
                    "interface": "",
                    "MessageContents": {
                     "http": {},
                     "body": {}
                    }
                })
    new_messages = []

    for msg in call_flow_messages:
        new_messages.append(msg)

    if new_messages:
        messages_collection.delete_many({
            "workspace_id": workspace_id
        })
        messages_collection.insert_many(new_messages)
        return {"count": len(new_messages)}
    else:
        return {"count": 0}



def send_packets(workspace_id, interval):
    while running_tests.get(workspace_id, False):

        messages = list(
            messages_collection.find({"workspace_id": workspace_id})
        )

        for message in messages:
            destination_ip = message["ip"]

            if destination_ip:
                packet = scapy.IP(dst=destination_ip) / scapy.ICMP()
                print("Sending ICMP to", destination_ip)
                scapy.sr1(
                    packet,
                    timeout=2,
                    verbose=False
                )

        time.sleep(interval)



@app.post("/save_pcap/{workspace_id}")
def save_pcap(workspace_id:str):
    messages =list(messages_collection.find({"workspace_id":workspace_id}))
    if(messages):
        packets=[]
        for message in messages:
                destination_ip = message["ip"]
                packet = scapy.IP(dst=destination_ip) / scapy.ICMP()
                packets.append(packet)
        wrpcap(f"./pcap_files/{workspace_id}.pcap", packets)
        return {"message": "PCAP file saved successfully"}
    else:
        return {"message": "No messages found"}
    
@app.post("/test_flow/{workspace_id}")
def test_nodes(workspace_id:str,frequency:Frequency):
    if frequency.frequency == "once":
        messages =list(messages_collection.find({"workspace_id":workspace_id}))
        if (messages):
            responses = []
            for message in messages:
                destination_ip = message["ip"]

                if not destination_ip:
                    continue
                packet = scapy.IP(dst=destination_ip) / scapy.ICMP()
                packet_str = packet.summary()
                response = scapy.sr1(
                    packet,
                    timeout=2,
                    verbose=False
                )

                responses.append({
                    "message_id": str(message["_id"]),
                    "destination_ip": destination_ip,
                    "label": message.get("label"),
                    "packet": packet_str,
                    "response": response.summary() if response else None
                })
            return {"response": responses}
        else:
            return {"response": "No messages in the workspace"}
    else:
        interval = int(frequency.frequency[:-1])
        running_tests[workspace_id] = True
        thread = threading.Thread(
        target=send_packets,
        args=(workspace_id, interval),
        daemon=True
    )

        thread.start()
        return {"response": "Scheduled to run in background every " + str(interval) + " seconds"}

@app.post("/check_diameter_config/{workspace_id}")
def check_diameter_config(workspace_id:str):
    workspace = workspaces_collection.find_one({"_id": ObjectId(workspace_id)})
    test=False
    if(workspace):
        for message in workspace["messages"]:
            if(message["protocol"]=="diameter"):
                test=True
    if(test):
        return {"response": "Diameter configuration found"}
    else:
        return {"response": "Diameter configuration not found"}
                
    

def send_packets_with_protocol(workspace_id, interval,data):
    while running_tests_protocol.get(workspace_id, False):

        messages = list(
            messages_collection.find({"workspace_id": workspace_id})
        )

        for message in messages:
            destination_ip = message["ip"]

            if destination_ip:
                payload = message["MessageContents"]["body"]
                print("Sending http2 to", destination_ip)
                try:
                    with httpx.Client(http2=True) as client:
                        response = client.post(
                            f"https://{message['ip']}",
                            json=payload
                        )
                        print(response.http_version)
                except Exception as e:
                    print("Simulated node unreachable:", e)
        workspace = workspaces_collection.find_one({"_id": ObjectId(workspace_id)})
        if(workspace):
            for message in workspace["messages"]:
                if(message["protocol"]=="diameter"):
                    hop_id = random.randint(0, 0xFFFFFFFF)
                    end_id = random.randint(0, 0xFFFFFFFF)
                    diameter_header = DiameterHeader(
                        command_code=DIAMETER_MESSAGES[data.diameter_message.split("/")[0]]["command_code"],
                        application_id=DIAMETER_MESSAGES[data.diameter_message.split("/")[0]]["application_id"],
                        flags=DIAMETER_MESSAGES[data.diameter_message.split("/")[0]]["flags"],
                        hop_id=hop_id,
                        end_id=end_id
                            )
                    session_id = f'{message["destination"]}.labx.local;{random.randint(1720623456, 2720623456)};{random.randint(1, 10)}'
                    value0 = encode_utf8(session_id)
                    diameter_avp0 = DiameterAVP(
                        code=263,
                        value=value0,
                        mandatory=True,
                        vendor_id=None
                    )
                    value1 = encode_utf8(f'{message["destination"]}.labx.local')
                    padding = (4 - (len(value1) % 4)) % 4
                    value1 += b"\x00" * padding
                    diameter_avp1 = DiameterAVP(
                        code=AVP_DICTIONARY["Origin-Host"]["code"],
                        value=value1,
                        mandatory=True,
                        vendor_id=None
                    )
                    value2 = encode_utf8("labx.local")
                    padding = (4 - (len(value2) % 4)) % 4
                    value2 += b"\x00" * padding
                    diameter_avp2 = DiameterAVP(
                        code=AVP_DICTIONARY["Origin-Realm"]["code"],
                        value=value2,
                        mandatory=True,
                        vendor_id=None
                    )
                    value3 = encode_uint32(10415)
                    padding = (4 - (len(value3) % 4)) % 4
                    value3 += b"\x00" * padding
                    diameter_avp3 = DiameterAVP(
                        code=AVP_DICTIONARY["Vendor-Id"]["code"],
                        value=value3,
                        mandatory=True,
                        vendor_id=None
                    )
                    for node in workspace['nodes']:
                        if node["id"]==message["id"].split("/")[1]:
                            ip_address_des = node['ip']
                            break
                    value4 = encode_ipv4(ip_address_des)
                    diameter_avp4 = DiameterAVP(
                        code=AVP_DICTIONARY["Host-IP-Address"]["code"],
                        value=value4,
                        mandatory=True,
                        vendor_id=None
                    )
    
                    avp0 = diameter_avp0.encode()
                    avp1 = diameter_avp1.encode()
                    avp2 = diameter_avp2.encode()
                    avp3 = diameter_avp3.encode()
                    avp4 = diameter_avp4.encode()
                    message_length = (
                        20
                        + len(avp0)
                        + len(avp1)
                        + len(avp2)
                        + len(avp3)
                        + len(avp4)
                    )
                    header = diameter_header.encode(message_length)
                    diameter_message = (
                        header
                        + avp0
                        + avp1
                        + avp2
                        + avp3
                        + avp4
                    )
                    for node in workspace['nodes']:
                        if node["id"]==message["id"].split("/")[0]:
                            ip_address_source = node['ip']
                            break
                    packet = (
                        IP(src=ip_address_source, dst=ip_address_des)
                        /
                        TCP(sport=3868, dport=3868, flags="PA")
                        /
                        Raw(diameter_message)
                )
                    send(packet)
        time.sleep(interval)


def is_port_open(ip, port=443, timeout=1.0):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False

@app.post("/test_flow_with_protocol_diameter/{workspace_id}")
def test_nodes_with_protocol_diameter(workspace_id:str,data:DiameterMessage):
    if data.frequency == "once":
        messages =list(messages_collection.find({"workspace_id":workspace_id}))
        if (messages):
                responses = []
                response=""
                response2=""
                for message in messages:
                    if(message["protocol"] == "http2"):
                        destination_ip = message["ip"]
                        if not destination_ip:
                            continue
                        payload = message["MessageContents"]["body"]
                        try:
                            if (is_port_open(destination_ip)):
                                with httpx.Client(http2=True) as client:
                                    response = client.post(
                                        f"https://{message['ip']}",
                                    json=payload
                                )
                                print(response.http_version)
                            else:
                                response2 = "Simulated node unreachable: port 443 is not open"
                        except Exception as e:
                            print("Simulated node unreachable:", e)
                        if(response):
                            responses.append({
                            "message_id": str(message["_id"]),
                            "destination_ip": destination_ip,
                            "label": message.get("label"),
                            "status_code": response.status_code,
                            "http_version": response.http_version,
                            "body": response.text
                        })
                        else:
                            responses.append({
                            "message_id": str(message["_id"]),
                            "destination_ip": destination_ip,
                            "label": message.get("label"),
                            "status_code": "Error",
                            "http_version": "Error",
                            "body": response2
                })
        workspace = workspaces_collection.find_one({"_id": ObjectId(workspace_id)})
        if(workspace):
                for message in workspace["messages"]:
                    if(message["protocol"]=="diameter"):
                        hop_id = random.randint(0, 0xFFFFFFFF)
                        end_id = random.randint(0, 0xFFFFFFFF)
                        diameter_header = DiameterHeader(
                            command_code=DIAMETER_MESSAGES[data.diameter_message.split("/")[0]]["command_code"],
                            application_id=DIAMETER_MESSAGES[data.diameter_message.split("/")[0]]["application_id"],
                            flags=DIAMETER_MESSAGES[data.diameter_message.split("/")[0]]["flags"],
                            hop_id=hop_id,
                            end_id=end_id
                            )
                        session_id = f'{message["destination"]}.labx.local;{random.randint(1720623456, 2720623456)};{random.randint(1, 10)}'
                        value0 = encode_utf8(session_id)
                        diameter_avp0 = DiameterAVP(
                        code=263,
                        value=value0,
                        mandatory=True,
                        vendor_id=None
                    )
                        value1 = encode_utf8(f'{message["destination"]}.labx.local')
                        diameter_avp1 = DiameterAVP(
                        code=AVP_DICTIONARY["Origin-Host"]["code"],
                        value=value1,
                        mandatory=True,
                        vendor_id=None
                    )
                        value2 = encode_utf8("labx.local")
                        diameter_avp2 = DiameterAVP(
                        code=AVP_DICTIONARY["Origin-Realm"]["code"],
                        value=value2,
                        mandatory=True,
                        vendor_id=None
                    )
                        value3 = encode_uint32(10415)
                        diameter_avp3 = DiameterAVP(
                        code=AVP_DICTIONARY["Vendor-Id"]["code"],
                        value=value3,
                        mandatory=True,
                        vendor_id=None
                    )
                        for node in workspace['nodes']:
                            if node["id"]==message["id"].split("/")[1]:
                                ip_address_des = node['ip']
                                break
                        value4 = encode_ipv4(ip_address_des)
                        diameter_avp4 = DiameterAVP(
                        code=AVP_DICTIONARY["Host-IP-Address"]["code"],
                        value=value4,
                        mandatory=True,
                        vendor_id=None
                    )
                        avp0 = diameter_avp0.encode()
                        avp1 = diameter_avp1.encode()
                        avp2 = diameter_avp2.encode()
                        avp3 = diameter_avp3.encode()
                        avp4 = diameter_avp4.encode()
                        message_length = (
                        20
                        + len(avp0)
                        + len(avp1)
                        + len(avp2)
                        + len(avp3)
                        + len(avp4)
                    )
                        header = diameter_header.encode(message_length)
                        diameter_message = (
                        header
                        + avp0
                        + avp1
                        + avp2
                        + avp3
                        + avp4
                    )
                        for node in workspace['nodes']:
                            if node["id"]==message["id"].split("/")[0]:
                                ip_address_source = node['ip']
                                break
                        packet = (
                        IP(src=ip_address_source, dst=ip_address_des)
                        /
                        TCP(sport=3868, dport=3868, flags="PA")
                        /
                        Raw(diameter_message)
                )
                        send(packet)
                        wrpcap(f"./pcap_files/{workspace_id}_diameter_test_scapy.pcap", packet)
                        gtp_header = GTPHeader(
                            message_type=GTP_MESSAGES["Create Session Request"]["message_type"],
                            teid=random.randint(0, 0xFFFFFFFF),
                            seq=random.randint(0, 0xFFFFFF)
                        )
                        imsi_ie = GTPInformationElement(
                            ie_type=1,
                            instance=0,
                            value=encode_utf8("001010123456789")
                        )
                        apn_ie = GTPInformationElement(
                            ie_type=71,
                            instance=0,
                            value=encode_utf8("internet")
                        )
                        rat_ie = GTPInformationElement(
                            ie_type=82,
                            instance=0,
                            value=encode_uint8(6)
                        )
                        ie1 = imsi_ie.encode()
                        ie2 = apn_ie.encode()
                        ie3 = rat_ie.encode()
                        gtp_payload = ie1 + ie2 + ie3

                        message_length = 20 + len(gtp_payload)

                        gtp_header = gtp_header.encode(message_length)
                        gtp_packet = gtp_header + gtp_payload

                        packet = (
                            IP(src=ip_address_source, dst=ip_address_des)
                            / UDP(sport=2123, dport=2123)
                            / Raw(gtp_packet)
                        )

                        send(packet)
                        print("GTP Create Session Request sent to " + ip_address_des)



        return {"response": responses}
    else:
        interval = int(data.frequency[:-1])
        running_tests_protocol[workspace_id] = True
        thread = threading.Thread(
        target=send_packets_with_protocol,
        args=(workspace_id, interval,data),
        daemon=True
    )

        thread.start()
        return {"response": "Scheduled to run in background every " + str(interval) + " seconds"}
@app.post("/test_flow_with_protocol/{workspace_id}")
def test_nodes_with_protocol(workspace_id:str,frequency:Frequency):
    if frequency.frequency == "once":
        messages =list(messages_collection.find({"workspace_id":workspace_id}))
        if (messages):
                responses = []
                response=""
                response2=""
                for message in messages:
                    if(message["protocol"] == "http2"):
                        destination_ip = message["ip"]
                        if not destination_ip:
                            continue
                        payload = message["MessageContents"]["body"]
                        try:
                            if (is_port_open(destination_ip)):
                                with httpx.Client(http2=True) as client:
                                    response = client.post(
                                        f"https://{message['ip']}",
                                    json=payload
                                )
                                print(response.http_version)
                            else:
                                response2 = "Simulated node unreachable: port 443 is not open"
                        except Exception as e:
                            print("Simulated node unreachable:", e)
                        if(response):
                            responses.append({
                            "message_id": str(message["_id"]),
                            "destination_ip": destination_ip,
                            "label": message.get("label"),
                            "status_code": response.status_code,
                            "http_version": response.http_version,
                            "body": response.text
                        })
                        else:
                            responses.append({
                            "message_id": str(message["_id"]),
                            "destination_ip": destination_ip,
                            "label": message.get("label"),
                            "status_code": "Error",
                            "http_version": "Error",
                            "body": response2
                })
                return {"response": responses}
        else:
            return {"response": "No messages in the workspace"}
    else:
        interval = int(frequency.frequency[:-1])
        running_tests_protocol[workspace_id] = True
        thread = threading.Thread(
        target=send_packets_with_protocol,
        args=(workspace_id, interval),
        daemon=True
    )

        thread.start()
        return {"response": "Scheduled to run in background every " + str(interval) + " seconds"}


@app.post("/stop_packets/{workspace_id}")
def stop_test_flow(workspace_id: str):
    running_tests[workspace_id] = False
    running_tests_protocol[workspace_id] = False
    return {"response": "Stopped"}        

            
@app.post("/configure_service")
def configure_service(data:ConfigureService):
    template = MESSAGE_TEMPLATES.get(data.service_name)

    if not template:
        return {"error": "Unknown service"}

    return {
        "http": template["http"],
        "body": template["body"]
    }


@app.post("/load_workspace/{workspace_id}")
def load_workspace(workspace_id:str):
    workspace = workspaces_collection.find_one({"_id": ObjectId(workspace_id)})
    return {"nodes": workspace["nodes"],"connections": workspace["connections"],"messages":workspace["messages"]}

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

@app.delete("/delete_workspace/{workspace_id}")
def delete_workspace(workspace_id:str):
    workspaces_collection.delete_one({"_id": ObjectId(workspace_id)})
    return {"message": "Workspace deleted successfully"}



MESSAGE_TEMPLATES = {

    # =======================
    # AMF SERVICES
    # =======================

    "Namf_Communication": {
        "http": {
            ":method": "POST",
            ":path": "/namf-comm/v1/ue-contexts",
            "content-type": "application/json"
        },
        "body": {
            "supi": "",
            "pei": "",
            "guti": "",
            "accessType": "3GPP_ACCESS"
        }
    },

    "Namf_EventExposure": {
        "http": {
            ":method": "POST",
            ":path": "/namf-evts/v1/subscriptions"
        },
        "body": {
            "event": "LOCATION_REPORT",
            "supi": ""
        }
    },

    "Namf_Location": {
        "http": {
            ":method": "GET",
            ":path": "/namf-loc/v1/location"
        },
        "body": {
            "supi": ""
        }
    },

    "Namf_MT": {
        "http": {
            ":method": "POST",
            ":path": "/namf-mt/v1/mt-data"
        },
        "body": {
            "supi": "",
            "payload": ""
        }
    },

    "Namf_EnergySaving": {
        "http": {
            ":method": "POST",
            ":path": "/namf-energy/v1/policies"
        },
        "body": {
            "cellId": "",
            "energyMode": "NORMAL"
        }
    },

    # =======================
    # SMF SERVICES
    # =======================

    "Nsmf_PDUSession": {
        "http": {
            ":method": "POST",
            ":path": "/nsmf-pdusession/v1/sessions"
        },
        "body": {
            "supi": "",
            "pduSessionId": 1,
            "dnn": "internet",
            "snssai": {
                "sst": 1,
                "sd": "010203"
            }
        }
    },

    "Nsmf_EventExposure": {
        "http": {
            ":method": "POST",
            ":path": "/nsmf-event-exposure/v1/subscriptions"
        },
        "body": {
            "event": "SESSION_RELEASE",
            "supi": ""
        }
    },

    "Nsmf_OAM": {
        "http": {
            ":method": "GET",
            ":path": "/nsmf-oam/v1/statistics"
        },
        "body": {}
    },

    # =======================
    # PCF SERVICES
    # =======================

    "Npcf_AMPolicyControl": {
        "http": {
            ":method": "POST",
            ":path": "/npcf-am-policy-control/v1/policies"
        },
        "body": {
            "supi": "",
            "accessType": "3GPP_ACCESS"
        }
    },

    "Npcf_SMPolicyControl": {
        "http": {
            ":method": "POST",
            ":path": "/npcf-smpolicycontrol/v1/sm-policies"
        },
        "body": {
            "supi": "",
            "pduSessionId": 1,
            "dnn": "internet",
            "snssai": {
                "sst": 1,
                "sd": "010203"
            }
        }
    },

    "Npcf_UEPolicyControl": {
        "http": {
            ":method": "POST",
            ":path": "/npcf-ue-policy-control/v1/policies"
        },
        "body": {
            "supi": ""
        }
    },

    "Npcf_BDTPolicyControl": {
        "http": {
            ":method": "POST",
            ":path": "/npcf-bdtpolicycontrol/v1/policies"
        },
        "body": {
            "applicationId": ""
        }
    },

    "Npcf_NIDDPolicyControl": {
        "http": {
            ":method": "POST",
            ":path": "/npcf-niddpolicycontrol/v1/policies"
        },
        "body": {
            "deviceId": ""
        }
    },

    "Npcf_EventExposure": {
        "http": {
            ":method": "POST",
            ":path": "/npcf-eventexposure/v1/subscriptions"
        },
        "body": {
            "event": "QOS_CHANGE"
        }
    },

    "Npcf_MPTCPControl": {
        "http": {
            ":method": "POST",
            ":path": "/npcf-mptcp-control/v1/policies"
        },
        "body": {
            "supi": ""
        }
    },

    "Npcf_RoutingPolicyControl": {
        "http": {
            ":method": "POST",
            ":path": "/npcf-routingpolicycontrol/v1/policies"
        },
        "body": {
            "routeId": ""
        }
    },

    # =======================
    # CHF
    # =======================

    "Nchf_ConvergedCharging": {
        "http": {
            ":method": "POST",
            ":path": "/nchf-convergedcharging/v1/chargingdata"
        },
        "body": {
            "supi": "",
            "volume": 0
        }
    },

    "Nchf_SpendingLimitControl": {
        "http": {
            ":method": "POST",
            ":path": "/nchf-spendinglimitcontrol/v1/limits"
        },
        "body": {
            "supi": "",
            "limit": 100
        }
    },

    # =======================
    # NSSF
    # =======================

    "Nnssf_NSSelection": {
        "http": {
            ":method": "POST",
            ":path": "/nnssf-nsselection/v1/network-slices"
        },
        "body": {
            "supi": "",
            "requestedNssai": []
        }
    },

    "Nnssf_NSSAIAvailability": {
        "http": {
            ":method": "GET",
            ":path": "/nnssf-nssaiavailability/v1"
        },
        "body": {}
    },

    # =======================
    # UDM
    # =======================

    "Nudm_UEAuthentication": {
        "http": {
            ":method": "POST",
            ":path": "/nudm-ueau/v1/security-information/generate-auth-data"
        },
        "body": {
            "supi": ""
        }
    },

    "Nudm_SDM": {
        "http": {
            ":method": "GET",
            ":path": "/nudm-sdm/v1/subscription-data"
        },
        "body": {
            "supi": ""
        }
    },

    "Nudm_UEContextManagement": {
        "http": {
            ":method": "GET",
            ":path": "/nudm-uecm/v1/registrations"
        },
        "body": {
            "supi": ""
        }
    },

    "Nudm_IdentityManagement": {
        "http": {
            ":method": "GET",
            ":path": "/nudm-idm/v1/identities"
        },
        "body": {
            "supi": ""
        }
    },

    "Nudm_SubscriberDataManagement": {
        "http": {
            ":method": "GET",
            ":path": "/nudm-sdm/v1/subscriber-data"
        },
        "body": {
            "supi": ""
        }
    },

    "Nudm_PP": {
        "http": {
            ":method": "GET",
            ":path": "/nudm-pp/v1/provisioning"
        },
        "body": {
            "supi": ""
        }
    },

    "Nudm_EEProfileManagement": {
        "http": {
            ":method": "POST",
            ":path": "/nudm-ee/v1/profiles"
        },
        "body": {
            "supi": ""
        }
    },

    "Nudr_DataRepositoryService": {
        "http": {
            ":method": "GET",
            ":path": "/nudr-dr/v1/subscription-data"
        },
        "body": {
            "resourceId": ""
        }
    },

    # =======================
    # NWDAF
    # =======================

    "Nnwdaf_AnalyticsInfo": {"http": {":method": "GET"}, "body": {"analyticsId": ""}},
    "Nnwdaf_AnalyticsSubscription": {"http": {":method": "POST"}, "body": {"analyticsId": ""}},
    "Nnwdaf_InsightsManagement": {"http": {":method": "POST"}, "body": {"insightId": ""}},
    "Nnwdaf_AIModelTraining": {"http": {":method": "POST"}, "body": {"modelName": ""}},
    "Nnwdaf_ModelDistribution": {"http": {":method": "POST"}, "body": {"modelId": ""}},
    "Nnwdaf_AdvancedPredictiveAnalytics": {"http": {":method": "POST"}, "body": {"predictionType": ""}},

    # =======================
    # EIR
    # =======================

    "Neirf_EquipmentIdentityCheck": {
        "http": {
            ":method": "POST",
            ":path": "/neir-eic/v1/check-imei"
        },
        "body": {
            "pei": ""
        }
    },

    # =======================
    # UDSF
    # =======================

    "Nudsf_DataManagement": {
        "http": {
            ":method": "POST",
            ":path": "/nudsf-dm/v1/data"
        },
        "body": {
            "dataId": ""
        }
    },

    # =======================
    # NRF
    # =======================

    "Nnrf_NFDiscovery": {
        "http": {
            ":method": "GET",
            ":path": "/nnrf-disc/v1/nf-instances"
        },
        "body": {
            "targetNfType": "SMF"
        }
    },

    "Nnrf_NFManagement": {
        "http": {
            ":method": "POST",
            ":path": "/nnrf-nfm/v1/nf-instances"
        },
        "body": {
            "nfType": "SMF"
        }
    },

    # =======================
    # SCP
    # =======================

    "Nscp_ServiceRouting": {"http": {":method": "POST"}, "body": {"targetNf": ""}},
    "Nscp_Interconnection": {"http": {":method": "POST"}, "body": {"partnerNetwork": ""}},

    # SMSF
    "Nsmsf_SMS": {"http": {":method": "POST"}, "body": {"supi": "", "sms": ""}},

    # NEF
    "Nnef_EventExposure": {"http": {":method": "POST"}, "body": {"event": ""}},
    "Nnef_PolicyNegotiation": {"http": {":method": "POST"}, "body": {"applicationId": ""}},
    "Nnef_TrafficInfluence": {"http": {":method": "POST"}, "body": {"flowId": ""}},
    "Nnef_NIDDOptimization": {"http": {":method": "POST"}, "body": {"deviceId": ""}},
    "Nnef_TimeSeriesDataExposure": {"http": {":method": "GET"}, "body": {"dataset": ""}},

    # AUSF
    "Nausf_UEAuthentication": {"http": {":method": "POST"}, "body": {"supi": ""}},
    "Nausf_SoRProtection": {"http": {":method": "POST"}, "body": {"supi": ""}},
    "Nausf_UPUProtection": {"http": {":method": "POST"}, "body": {"supi": ""}},

    # AF
    "Naf_EventExposure": {"http": {":method": "POST"}, "body": {"event": ""}},

    # BSF
    "Nbsf_Management": {"http": {":method": "POST"}, "body": {"bindingId": ""}},

    # SEPP
    "Nsepp_Security": {"http": {":method": "POST"}, "body": {"peerSepp": ""}},
    "Nsepp_Topology": {"http": {":method": "GET"}, "body": {"topologyId": ""}}
}