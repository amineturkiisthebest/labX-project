from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import time
import json
from pydantic import BaseModel
from app.database import users_collection,workspaces_collection,nodes_collection,messages_collection
from jose import jwt
from datetime import datetime, timedelta
from bson import ObjectId
from reportlab.lib.styles import getSampleStyleSheet
from passlib.context import CryptContext
import scapy.all as scapy
from scapy.all import load_contrib
from scapy.all import IP,UDP,TCP, Raw, send,wrpcap,sr1,sniff
from scapy.contrib.gtp import GTP_U_Header
from scapy.layers.sctp import SCTP, SCTPChunkInit, SCTPChunkInitAck, SCTPChunkCookieEcho, SCTPChunkCookieAck, SCTPChunkData
from h2.connection import H2Connection
from h2.config import H2Configuration
from h2.events import RequestReceived, DataReceived, StreamEnded
import socket
import threading
import random
from app.open5gs.routes import router as open5gs_router
from app.open5gs.client import Open5GSClient
# pyrefly: ignore [missing-import]
from pycrate_asn1dir.S1AP import S1AP_PDU_Descriptions
from pycrate_asn1dir import S1AP
import struct
# pyrefly: ignore [missing-import]
import httpx

app = FastAPI()

#app.include_router(open5gs_router)

OPEN5GS_HOST = "192.168.0.175"
OPEN5GS_INFO_PORT = 9090
OPEN5GS_SBI_PORT = 7777

#open5gs = Open5GSClient(
 #   OPEN5GS_HOST,
  #  OPEN5GS_INFO_PORT
#)

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

class ProtocolMessage(BaseModel):
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

MME_IP = "127.0.0.1"
MME_PORT = 36412

running = True

# Keep a small amount of association state
associations = {}

def handle_init(packet):

    ip = packet[IP]
    sctp = packet[SCTP]
    init = packet[SCTPChunkInit]

    client_ip = ip.src
    client_port = sctp.sport

    print("\n[MME] ========================================")
    print("[MME] Received SCTP INIT")
    print(f"[MME] Client: {client_ip}:{client_port}")
    print(f"[MME] Client INIT tag: 0x{init.init_tag:08x}")

    # Generate MME's verification tag
    mme_init_tag = random.randint(1, 0xFFFFFFFF)

    # Save association state
    associations[(client_ip, client_port)] = {
        "client_tag": init.init_tag,
        "mme_tag": mme_init_tag,
        "client_tsn": init.init_tsn,
        "mme_tsn": random.randint(1, 0xFFFFFFFF)
    }

    print(f"[MME] MME INIT tag: 0x{mme_init_tag:08x}")

    # --------------------------------------------------------
    # Build INIT-ACK
    # --------------------------------------------------------

    init_ack = (
        IP(
            src=MME_IP,
            dst=client_ip
        )
        /
        SCTP(
            sport=MME_PORT,
            dport=client_port,
            tag=init.init_tag
        )
        /
        SCTPChunkInitAck(
            init_tag=mme_init_tag,
            a_rwnd=102400,
            n_out_streams=10,
            n_in_streams=10,
            init_tsn=associations[(client_ip, client_port)]["mme_tsn"]
        )
    )

    print("[MME] Sending SCTP INIT-ACK...")

    send(
        init_ack,
        verbose=False
    )

    print("[MME] INIT-ACK sent")

def handle_cookie_echo(packet):

    ip = packet[IP]
    sctp = packet[SCTP]

    client_ip = ip.src
    client_port = sctp.sport

    print("\n[MME] ========================================")
    print("[MME] Received COOKIE-ECHO")
    print(f"[MME] Client: {client_ip}:{client_port}")

    association = associations.get(
        (client_ip, client_port)
    )

    if association is None:
        print("[MME] Unknown association")
        return

    # --------------------------------------------------------
    # Build COOKIE-ACK
    # --------------------------------------------------------

    cookie_ack = (
        IP(
            src=MME_IP,
            dst=client_ip
        )
        /
        SCTP(
            sport=MME_PORT,
            dport=client_port,
            tag=association["client_tag"]
        )
        /
        SCTPChunkCookieAck()
    )

    print("[MME] Sending COOKIE-ACK...")

    send(
        cookie_ack,
        verbose=False
    )

    print("[MME] COOKIE-ACK sent")
    print("[MME] SCTP association established")

def handle_s1ap_data(packet):

    ip = packet[IP]
    sctp = packet[SCTP]
    data = packet[SCTPChunkData]

    client_ip = ip.src
    client_port = sctp.sport

    print("\n[MME] ========================================")
    print("[MME] Received SCTP DATA")
    print(f"[MME] Client: {client_ip}:{client_port}")

    print(f"[MME] Stream ID: {data.stream_id}")
    print(f"[MME] Stream sequence: {data.stream_seq}")
    print(f"[MME] PPID: {data.proto_id}")

    s1ap_bytes = bytes(data.data)

    print(f"[MME] S1AP length: {len(s1ap_bytes)} bytes")
    print(f"[MME] S1AP HEX:")
    print(s1ap_bytes.hex())

    # --------------------------------------------------------
    # Decode the S1AP message
    # --------------------------------------------------------

    try:
        pdu = S1AP.S1AP_PDU_Descriptions.S1AP_PDU()

        pdu.from_aper(
            s1ap_bytes
        )

        print("\n[MME] Decoded S1AP message:")
        print(pdu.show())

    except Exception as e:

        print("[MME] Could not decode S1AP:")
        print(e)

    # --------------------------------------------------------
    # For now send an SCTP response.
    #
    # We will replace this with a real S1SetupResponse
    # after confirming the transport works.
    # --------------------------------------------------------

    send_sctp_response(
        packet,
        s1ap_bytes
    )

def send_sctp_response(request_packet, request_s1ap):

    ip = request_packet[IP]
    sctp = request_packet[SCTP]
    data = request_packet[SCTPChunkData]

    client_ip = ip.src
    client_port = sctp.sport

    association = associations.get(
        (client_ip, client_port)
    )

    if association is None:
        print("[MME] Association not found")
        return

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # This is only a transport-level response for now.
    # It is NOT yet a valid S1SetupResponse.
    # --------------------------------------------------------

    response_payload = request_s1ap

    response = (
        IP(
            src=MME_IP,
            dst=client_ip
        )
        /
        SCTP(
            sport=MME_PORT,
            dport=client_port,
            tag=association["client_tag"]
        )
        /
        SCTPChunkData(
            tsn=association["mme_tsn"],
            stream_id=data.stream_id,
            stream_seq=data.stream_seq,
            proto_id=18,
            beginning=1,
            ending=1,
            data=response_payload
        )
    )

    print("\n[MME] Sending SCTP DATA response...")

    send(
        response,
        verbose=False
    )

    print("[MME] SCTP DATA response sent")

def process_packet(packet):

    if not packet.haslayer(SCTP):
        return

    if packet.haslayer(SCTPChunkInit):

        handle_init(packet)

    elif packet.haslayer(SCTPChunkCookieEcho):

        handle_cookie_echo(packet)

    elif packet.haslayer(SCTPChunkData):

        handle_s1ap_data(packet)

def start_mme_simulator():
    print("============================================")
    print("       LOCAL MME / S1AP SIMULATOR")
    print("============================================")
    print(f"MME IP   : {MME_IP}")
    print(f"MME Port : {MME_PORT}")
    print("")
    print("Waiting for SCTP packets...")

    sniff(
        filter="sctp",
        prn=process_packet,
        store=False
    )
GTP_MESSAGES = {

    "CreateSessionRequest": {
        "message_type": 32
    },

    "CreateSessionResponse": {
        "message_type": 33
    },

    "ModifyBearerRequest": {
        "message_type": 34
    },

    "ModifyBearerResponse": {
        "message_type": 35
    },

    "DeleteSessionRequest": {
        "message_type": 36
    },

    "DeleteSessionResponse": {
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
        seq,
        payload_length=0,
        teid=None
    ):
        self.version = 2
        self.pt = 0
        self.message_type = message_type
        self.teid = teid
        self.seq = seq
        self.payload_length = payload_length
    def encode(self, payload_length):
        # 1. Calculate flags (Version 2, PT 1, and TEID flag if applicable)
        flags = (self.version << 5) | (self.pt << 4)
        if self.teid is not None:
            flags |= 0x08

        # 2. Extract individual bytes for the 3-byte Sequence Number safely
        seq_byte1 = (self.seq >> 16) & 0xFF
        seq_byte2 = (self.seq >> 8) & 0xFF
        seq_byte3 = self.seq & 0xFF
        
        # 3. Define the Spare byte (Octet 12) according to TS 29.274
        spare_byte = 0x00 

        if self.teid is not None:
            # Layout: Flags(1B), MsgType(1B), Length(2B), TEID(4B), Seq1(1B), Seq2(1B), Seq3(1B), Spare(1B)
            return struct.pack(
                "!BBHIBBBB",
                flags,
                self.message_type,
                payload_length,
                self.teid,
                seq_byte1,
                seq_byte2,
                seq_byte3,
                spare_byte
            )
        else:
            # If TEID is None (e.g., Echo requests), GTPv2 skips the 4-byte TEID field entirely.
            # Total header size drops to 8 bytes instead of 12.
            return struct.pack(
                "!BBHBBBB",
                flags,
                self.message_type,
                payload_length,
                seq_byte1,
                seq_byte2,
                seq_byte3,
                spare_byte
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

        return struct.pack(
        "!BHB",
        self.ie_type,
        len(value),
        self.instance & 0x0F
    ) + value

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

def encode_apn(apn: str) -> bytes:
    encoded = b""

    for label in apn.split("."):
        if len(label) > 63:
            raise ValueError("Each APN label must be at most 63 bytes")

        encoded += bytes([len(label)])
        encoded += label.encode("ascii")

    return encoded
def encode_recovery(restart_counter=0):
    return struct.pack("!B", restart_counter)

def encode_selection_mode(mode):
    return struct.pack("!B", mode)
def encode_pdn_type(pdn_type):
    return struct.pack("!B", pdn_type)
def encode_serving_network(mcc, mnc):
    digits = mcc + mnc

    if len(mnc) == 2:
        digits = mcc + mnc + "F"

    return bytes([
        (int(digits[1],16) << 4) | int(digits[0],16),
        (int(digits[5],16) << 4) | int(digits[2],16),
        (int(digits[4],16) << 4) | int(digits[3],16)
    ])
def encode_f_teid(teid, ipv4, interface_type=10):
    flags = 0x80 | (interface_type & 0x3F)

    return (
        struct.pack("!B", flags)
        + struct.pack("!I", teid)
        + socket.inet_aton(ipv4)
    )


def encode_tbcd(number: str) -> bytes:
    # Only digits are allowed
    if not number.isdigit():
        raise ValueError("TBCD encoder accepts digits only")

    encoded = bytearray()

    i = 0
    while i < len(number):
        low = int(number[i])

        if i + 1 < len(number):
            high = int(number[i + 1])
        else:
            high = 0xF  # Padding for odd number of digits

        encoded.append((high << 4) | low)
        i += 2

    return bytes(encoded)
def encode_ue_timezone(timezone_quarters=4, dst=0):
    """
    timezone_quarters:
        UTC offset in 15-minute units.
        UTC+1 = 4
        UTC+2 = 8
    dst:
        0 = no DST
        1 = +1 hour
        2 = +2 hours
    """
    return struct.pack("!BB", timezone_quarters, dst)
def encode_apn_restriction(value=0):
    return struct.pack("!B", value)
def encode_ambr(ul, dl):
    return (
        struct.pack("!I", ul) +
        struct.pack("!I", dl)
    )
def encode_indication():
    return bytes(8)

def send_s1ap_request(
    ip_address_source,
    ip_address_des,
    encoded,
    sport=50002,
    dport=36412
):
    try:
        # ==========================================================
        # 1. SCTP INIT
        # ==========================================================

        my_init_tag = 0xABCDE123

        init_pkt = (
            scapy.IP(
                src=ip_address_source,
                dst=ip_address_des
            )
            /
            scapy.SCTP(
                sport=sport,
                dport=dport,
                tag=0
            )
            /
            scapy.SCTPChunkInit(
                init_tag=my_init_tag,
                a_rwnd=102400,
                n_out_streams=10,
                n_in_streams=10,
                init_tsn=1000
            )
        )

        print("[*] Sending SCTP INIT...")

        init_ack_pkt = scapy.sr1(
            init_pkt,
            timeout=2,
            verbose=False
        )

        if not init_ack_pkt:
            print("[-] No SCTP INIT_ACK received")
            return None

        if init_ack_pkt:
            print("[+] Received packet:")
            init_ack_pkt.show()
            print("[+] Summary:")
            print(init_ack_pkt.summary())
        else:
            print("[-] No response received")
            return None

        # ==========================================================
        # 2. Extract INIT_ACK information
        # ==========================================================

        init_ack = init_ack_pkt[scapy.SCTPChunkInitAck]

        mme_init_tag = init_ack.init_tag
        mme_tsn = init_ack.init_tsn
        cookie = init_ack.params

        print(
            f"[+] Received INIT_ACK. "
            f"MME Tag: {hex(mme_init_tag)}"
        )

        # ==========================================================
        # 3. SCTP COOKIE-ECHO
        # ==========================================================

        cookie_echo_pkt = (
            scapy.IP(
                src=ip_address_source,
                dst=ip_address_des
            )
            /
            scapy.SCTP(
                sport=sport,
                dport=dport,
                tag=mme_init_tag
            )
            /
            scapy.SCTPChunkCookieEcho(
                cookie=cookie
            )
        )

        print("[*] Sending SCTP COOKIE_ECHO...")

        cookie_ack_pkt = scapy.sr1(
            cookie_echo_pkt,
            timeout=2,
            verbose=False
        )

        if not cookie_ack_pkt:
            print("[-] No SCTP COOKIE_ACK received")
            return None

        if not cookie_ack_pkt.haslayer(
            scapy.SCTPChunkCookieAck
        ):
            print("[-] Received packet is not COOKIE_ACK")
            return None

        print("[+] SCTP Association Established!")

        # ==========================================================
        # 4. Send S1AP DATA
        # ==========================================================

        data_pkt = (
            scapy.IP(
                src=ip_address_source,
                dst=ip_address_des
            )
            /
            scapy.SCTP(
                sport=sport,
                dport=dport,
                tag=mme_init_tag
            )
            /
            scapy.SCTPChunkData(
                tsn=1000,
                stream_id=0,
                stream_seq=0,
                proto_id=18,
                beginning=1,
                ending=1,
                data=encoded
            )
        )

        print("[*] Sending S1AP message...")

        # ==========================================================
        # 5. Receive S1AP response
        # ==========================================================

        response_pkt = scapy.sr1(
            data_pkt,
            timeout=2,
            verbose=False
        )

        if not response_pkt:
            print("[-] No S1AP response received")
            return None

        print("[+] S1AP response received!")

        # ==========================================================
        # 6. Extract S1AP payload
        # ==========================================================

        if response_pkt.haslayer(scapy.SCTPChunkData):

            response_data = response_pkt[
                scapy.SCTPChunkData
            ].data

            print(
                f"[+] S1AP response length: "
                f"{len(response_data)} bytes"
            )

            print(
                f"[+] S1AP response HEX: "
                f"{response_data.hex()}"
            )

            return response_data

        else:
            print(
                "[-] Response does not contain "
                "an SCTP DATA chunk"
            )

            return None

    except Exception as e:

        print(f"[!] S1AP error: {e}")

        return None
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
    },
        "Product-Name": {
        "code": 269
    },

    "Origin-State-Id": {
        "code": 278
    },

}
DIAMETER_MESSAGES = {
    "CapabilitiesExchangeRequest": {
        "command_code": 257,
        "application_id": 0,
        "flags": 0x80,
    },
    "DeviceWatchdogRequest": {
        "command_code": 280,
        "application_id": 0,
        "flags": 0x80,
    },
    "Re-AuthRequest": {
        "command_code": 258,
        "application_id": 0,
        "flags": 0x80,
    },
}

running_tests = {}

running_tests_gtpv2 = {}

running_tests_http2 = {}

running_tests_diameter = {}

diameter_responses = {}

def recv_exact(sock, size):

    data = b""

    while len(data) < size:

        chunk = sock.recv(
            size - len(data)
        )

        if not chunk:
            return None

        data += chunk

    return data
def diameter_simulator(port,des_ip,source_ip, workspace_id):
    try:
        server_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
        )

        server_socket.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
        )
        ip = "127.0.0.1"
        if des_ip == "127.0.0.1" and source_ip != "127.0.0.1":
            ip = source_ip
        if  des_ip != "127.0.0.1" and source_ip == "127.0.0.1":
            ip = des_ip
        server_socket.bind((ip, port))
        server_socket.listen(5)
        print(f"Diameter simulator listening on port {port}")
    except OSError as e:

        print(
        f"Socket error while starting server "
        f"on {ip}:{port}: {e}"
        )
        if server_socket is not None:
            server_socket.close()
        return


    try:

        while running_tests_diameter.get(workspace_id, False):

            print("Waiting for Diameter connection...")

            # Give accept() a timeout so that the thread can
            # periodically check running_tests_diameter.
            server_socket.settimeout(1.0)

            try:
                client_socket, client_address = server_socket.accept()

            except socket.timeout:
                continue

            print(
                f"Diameter connection from {client_address}"
            )

            thread = threading.Thread(
                target=handle_diameter_client,
                args=(
                    client_socket,
                    client_address,
                    workspace_id
                ),
                daemon=True
            )

            thread.start()

    except Exception as e:

        print(
            f"Diameter simulator error: {e}"
        )

    finally:

        server_socket.close()

        print(
            f"Diameter simulator closed for workspace {workspace_id}"
        )

def handle_diameter_client(
    client_socket,
    client_address,
    workspace_id
):

    try:

        client_socket.settimeout(5.0)

        while running_tests_diameter.get(
            workspace_id,
            False
        ):

            # ------------------------------------------------
            # Step 1: Receive Diameter header
            # ------------------------------------------------

            header = recv_exact(
                client_socket,
                20
            )

            if not header:

                print(
                    f"Diameter connection closed by "
                    f"{client_address}"
                )

                break

            # ------------------------------------------------
            # Step 2: Read Diameter Message Length
            # ------------------------------------------------

            message_length = int.from_bytes(
                header[1:4],
                byteorder="big"
            )

            print(
                f"Diameter message length: "
                f"{message_length}"
            )

            # Basic validation
            if message_length < 20:

                print(
                    f"Invalid Diameter message length: "
                    f"{message_length}"
                )

                break

            # ------------------------------------------------
            # Step 3: Receive remaining message
            # ------------------------------------------------

            remaining_length = message_length - 20

            body = recv_exact(
                client_socket,
                remaining_length
            )

            if body is None:

                print(
                    "Connection closed before complete "
                    "Diameter message was received"
                )

                break

            # Complete REQUEST
            request = header + body

            print(
                f"Received complete Diameter REQUEST "
                f"from {client_address}"
            )

            print(
                f"Request size: {len(request)} bytes"
            )


            # ------------------------------------------------
            # Step 4: Build Diameter RESPONSE
            # ------------------------------------------------

            response = build_diameter_response(
                request
            )

            print(
                "Diameter RESPONSE created"
            )

            print(
                f"Response size: {len(response)} bytes"
            )

            # ------------------------------------------------
            # Step 5: Store response
            # ------------------------------------------------

            diameter_responses[workspace_id] = response

            # ------------------------------------------------
            # Step 6: Send response to client
            # ------------------------------------------------

            client_socket.sendall(
                response
            )

            print(
                "Diameter response sent"
            )

            # ------------------------------------------------
            # Step 7: Stop listening for this test
            # ------------------------------------------------

            running_tests_diameter[workspace_id] = False

            break

    except socket.timeout:

        print(
            f"Diameter receive timeout from "
            f"{client_address}"
        )

    except Exception as e:

        print(
            f"Diameter client error "
            f"{client_address}: {e}"
        )

    finally:

        client_socket.close()

        print(
            f"Diameter connection closed: "
            f"{client_address}"
        )
def build_diameter_response(request):

    # ------------------------------------------------
    # Parse Diameter Header
    # ------------------------------------------------

    version = request[0]

    request_flags = request[4]

    # Clear Request bit
    # 0x80 = Request
    response_flags = request_flags & 0x7F

    command_code = int.from_bytes(
        request[5:8],
        byteorder="big"
    )

    application_id = request[8:12]

    hop_by_hop_id = request[12:16]

    end_to_end_id = request[16:20]

    print("----------------------------------------")
    print("Building Diameter Response")

    print(f"Version: {version}")
    print(f"Command-Code: {command_code}")
    print(
        f"Application-ID: "
        f"{int.from_bytes(application_id, 'big')}"
    )

    print(
        f"Hop-by-Hop ID: "
        f"{hop_by_hop_id.hex()}"
    )

    print(
        f"End-to-End ID: "
        f"{end_to_end_id.hex()}"
    )

    print(
        f"Request Flags: "
        f"0x{request_flags:02x}"
    )

    print(
        f"Response Flags: "
        f"0x{response_flags:02x}"
    )

    # ------------------------------------------------
    # Result-Code AVP
    # ------------------------------------------------

    result_code_avp = (
        struct.pack("!I", 268)      # AVP Code
        +
        bytes([0x40])               # Mandatory
        +
        bytes([0x00, 0x00, 0x0C])   # AVP Length = 12
        +
        struct.pack("!I", 2001)     # DIAMETER_SUCCESS
    )

    # ------------------------------------------------
    # Origin-Host AVP
    # ------------------------------------------------

    origin_host = b"labx.local"

    origin_host_avp = (
        struct.pack("!I", 264)       # Origin-Host
        +
        bytes([0x40])                # Mandatory
        +
        bytes([0x00, 0x00,
               8 + len(origin_host)])
        +
        origin_host
    )

    # Padding to 4-byte boundary
    origin_host_avp += (
        b"\x00" *
        ((4 - len(origin_host_avp) % 4) % 4)
    )

    # ------------------------------------------------
    # Origin-Realm AVP
    # ------------------------------------------------

    origin_realm = b"labx.local"

    origin_realm_avp = (
        struct.pack("!I", 296)       # Origin-Realm
        +
        bytes([0x40])                # Mandatory
        +
        bytes([0x00, 0x00,
               8 + len(origin_realm)])
        +
        origin_realm
    )

    # Padding
    origin_realm_avp += (
        b"\x00" *
        ((4 - len(origin_realm_avp) % 4) % 4)
    )

    # ------------------------------------------------
    # Build Payload
    # ------------------------------------------------

    payload = (
        result_code_avp
        +
        origin_host_avp
        +
        origin_realm_avp
    )

    # ------------------------------------------------
    # Diameter Message Length
    # ------------------------------------------------

    response_length = 20 + len(payload)

    # ------------------------------------------------
    # Build Diameter Header
    # ------------------------------------------------

    response_header = (
        bytes([version])
        +
        response_length.to_bytes(
            3,
            byteorder="big"
        )
        +
        bytes([response_flags])
        +
        command_code.to_bytes(
            3,
            byteorder="big"
        )
        +
        application_id
        +
        hop_by_hop_id
        +
        end_to_end_id
    )

    response = response_header + payload

    print(
        f"Response length: "
        f"{len(response)}"
    )

    print(
        f"Response HEX: "
        f"{response.hex()}"
    )

    print("----------------------------------------")

    return response
running_tests_gtpv1 = {}
def gtpv1_simulator(workspace_id):

    print("============================================")
    print("          GTP-U SIMULATOR")
    print("============================================")
    print("GTP-U IP   : 127.0.0.1")
    print("GTP-U Port : 2152")
    print("")
    print("Waiting for GTP-U packets...")

    sniff(
        filter="udp port 2152",
        prn=lambda packet: handle_gtpv1_client(
            packet,
            workspace_id
        ),
        store=False
    )

def handle_gtpv1_client(packet, workspace_id):

    if not packet.haslayer(GTP_U_Header):
        return

    print("[+] GTP-U packet received")

    gtp = packet[GTP_U_Header]

    response = (
        IP(
            src=packet[IP].dst,
            dst=packet[IP].src
        )
        /
        UDP(
            sport=2152,
            dport=2152
        )
        /
        GTP_U_Header(
            teid=gtp.teid,
            gtp_type=255
        )
        /
        Raw(
            bytes(packet[Raw])
        )
    )

    print("[+] Sending GTP-U response")

    send(response, verbose=False)

    print("[+] GTP-U response sent")
def send_h2c_request(host, port, body):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))

        config = H2Configuration(
        client_side=True,
        header_encoding="utf-8"
        )

        connection = H2Connection(config=config)
    except socket.timeout:
        
        print("HTTP2 response timeout")
        return 

    # Generate:
    # PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n
    # + SETTINGS frame
    connection.initiate_connection()

    sock.sendall(connection.data_to_send())

    # Create HTTP/2 request
    stream_id = connection.get_next_available_stream_id()

    headers = [
        (":method", "POST"),
        (":scheme", "http"),
        (":authority", f"{host}:{port}"),
        (":path", "/"),
        ("content-type", "application/json"),
    ]

    connection.send_headers(
        stream_id,
        headers,
        end_stream=False
    )

    connection.send_data(
        stream_id,
        body,
        end_stream=True
    )

    sock.sendall(connection.data_to_send())
    response_body = b""

    # Receive response
    while True:

        data = sock.recv(65535)

        if not data:
            break

        events = connection.receive_data(data)

        for event in events:

            if isinstance(event, DataReceived):

                response_body += event.data


                connection.acknowledge_received_data(
                    event.flow_controlled_length,
                    event.stream_id
                )

            elif isinstance(event, StreamEnded):

                sock.close()

                return response_body

        # Send any pending HTTP/2 frames
        output = connection.data_to_send()

        if output:
            sock.sendall(output)

    sock.close()

    return response_body
def http2_simulator(port,des_ip,source_ip,workspace_id):
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ip = "127.0.0.1"
        if des_ip == "127.0.0.1" and source_ip != "127.0.0.1":
            ip = source_ip
        if  des_ip != "127.0.0.1" and source_ip == "127.0.0.1":
            ip = des_ip
        server_socket.bind((ip, port))
        server_socket.listen(5)

        print(f"HTTP/2 simulator listening on port {port}")
    except OSError as e:

        print(
        f"Socket error while starting server "
        f"on {ip}:{port}: {e}"
        )
        if server_socket is not None:
            server_socket.close()
        return
        
    while running_tests_http2.get(workspace_id, False):

        print("Waiting for connection...")

        client_socket, client_address = server_socket.accept()

        print(f"HTTP/2 connection from {client_address}")

        thread = threading.Thread(
            target=handle_http2_client,
            args=(client_socket, client_address,workspace_id,),
            daemon=True
        )

        thread.start()
def handle_http2_client(client_socket, client_address,workspace_id):

    try:

        config = H2Configuration(
            client_side=False,
            header_encoding="utf-8"
        )

        connection = H2Connection(config=config)

        # Send HTTP/2 server preface/settings
        connection.initiate_connection()

        client_socket.sendall(
            connection.data_to_send()
        )

        while running_tests_http2.get(workspace_id, False):

            data = client_socket.recv(65535)

            if not data:
                break

            print(
                f"Received {len(data)} bytes from {client_address}"
            )

            # Feed received HTTP/2 frames to h2
            events = connection.receive_data(data)

            for event in events:

                if isinstance(event, RequestReceived):

                    print("\nHTTP/2 REQUEST")

                    print("Stream ID:", event.stream_id)

                    print("Headers:")

                    for header in event.headers:
                        print("   ", header)

                elif isinstance(event, DataReceived):

                    print(
                        "Body:",
                        event.data
                    )

                    # Tell h2 that we consumed the data
                    connection.acknowledge_received_data(
                        event.flow_controlled_length,
                        event.stream_id
                    )

                elif isinstance(event, StreamEnded):

                    print(
                        f"Stream {event.stream_id} ended"
                    )

                    # Send HTTP/2 response
                    response_headers = [
                        (":status", "200"),
                        ("content-type", "application/json"),
                    ]

                    response_body = b'{"status":"success"}'

                    connection.send_headers(
                        event.stream_id,
                        response_headers
                    )

                    connection.send_data(
                        event.stream_id,
                        response_body,
                        end_stream=True
                    )

            output = connection.data_to_send()

            if output:
                client_socket.sendall(output)
            running_tests_http2[workspace_id] = False

    except Exception as e:

        print(
            f"HTTP/2 client error {client_address}: {e}"
        )

    finally:

        client_socket.close()

        print(
            f"HTTP/2 connection closed: {client_address}"
        )
running_tests_protocol = {}
def create_session_response(seq, teid):

    # =====================================================
    # 1. Cause IE
    # =====================================================

    # Cause value 16 = Request accepted
    #
    # Cause IE value:
    #   Cause = 16
    #   PCE   = 0
    #   BCE   = 0
    #   CS    = 0
    #
    cause_value = bytes([
        16,      # Cause: Request accepted
        0x00,    # PCE / BCE / CS + spare
        0x00,    # offending IE type
        0x00     # offending IE instance
    ])

    cause_ie = GTPInformationElement(
        ie_type=2,
        instance=0,
        value=cause_value
    )


    # =====================================================
    # 2. Recovery IE
    # =====================================================

    # Restart Counter = 0
    recovery_ie = GTPInformationElement(
        ie_type=3,
        instance=0,
        value=b"\x00"
    )


    # =====================================================
    # 3. Sender F-TEID for Control Plane
    # =====================================================

    # Example TEID for our simulated SGW/PGW
    control_teid = 0x87654321

    # F-TEID:
    #
    # Octet 1:
    #   V4 = 1
    #   V6 = 0
    #   Interface Type = 8
    #
    # Interface type 8 = S11/S4 SGW GTP-C
    #
    fteid_flags = 0x80 | 8

    fteid_value = (
        bytes([fteid_flags]) +
        control_teid.to_bytes(4, "big") +
        bytes([127, 0, 0, 1])
    )

    sender_fteid_ie = GTPInformationElement(
        ie_type=87,       # F-TEID
        instance=0,
        value=fteid_value
    )


    # =====================================================
    # 4. Bearer Context
    # =====================================================

    # -----------------------------------------------------
    # Bearer Cause
    # -----------------------------------------------------

    bearer_cause_value = bytes([
        16,      # Request accepted
        0x00,
        0x00,
        0x00
    ])

    bearer_cause_ie = GTPInformationElement(
        ie_type=2,        # Cause
        instance=0,
        value=bearer_cause_value
    )


    # -----------------------------------------------------
    # EPS Bearer ID
    # -----------------------------------------------------

    # Example EBI = 5
    ebi_ie = GTPInformationElement(
        ie_type=73,       # EPS Bearer ID
        instance=0,
        value=b"\x05"
    )


    # -----------------------------------------------------
    # F-TEID for User Plane
    # -----------------------------------------------------

    user_teid = 0x12345678

    # Example:
    # V4 = 1
    # Interface Type = 1
    #
    # Interface type 1 = S5/S8 SGW GTP-U
    #
    user_fteid_flags = 0x80 | 1

    user_fteid_value = (
        bytes([user_fteid_flags]) +
        user_teid.to_bytes(4, "big") +
        bytes([127, 0, 0, 1])
    )

    user_fteid_ie = GTPInformationElement(
        ie_type=87,       # F-TEID
        instance=2,       # S5/S8-U / user-plane F-TEID instance
        value=user_fteid_value
    )


    # -----------------------------------------------------
    # Build Bearer Context payload
    # -----------------------------------------------------

    bearer_payload = (
        bearer_cause_ie.encode() +
        ebi_ie.encode() +
        user_fteid_ie.encode()
    )


    bearer_context_ie = GTPInformationElement(
        ie_type=93,       # Bearer Context
        instance=0,
        value=bearer_payload
    )


    # =====================================================
    # 5. Complete GTPv2 Response Payload
    # =====================================================

    gtp_payload = (
        cause_ie.encode() +
        recovery_ie.encode() +
        sender_fteid_ie.encode() +
        bearer_context_ie.encode()
    )


    # =====================================================
    # 6. GTPv2 Header
    # =====================================================

    response_header = GTPHeader(
        message_type=33,      # Create Session Response
        seq=seq,
        teid=teid
    )


    # GTPv2 Length field:
    #
    # Everything after the first 4 bytes:
    #   TEID      = 4
    #   Seq/Spare = 4
    #   Payload   = len(gtp_payload)
    #
    payload_length = 8 + len(gtp_payload)

    response = (
        response_header.encode(payload_length)
        +
        gtp_payload
    )

    return response
def modify_bearer_response(seq, teid):

    # =====================================================
    # 1. Cause IE
    # =====================================================

    # Cause value 16 = Request accepted

    cause_value = bytes([
        16,      # Cause = Request accepted
        0x00,    # PCE / BCE / CS
        0x00,    # Offending IE Type
        0x00     # Offending IE Instance
    ])

    cause_ie = GTPInformationElement(
        ie_type=2,       # Cause
        instance=0,
        value=cause_value
    )


    # =====================================================
    # 2. Recovery IE
    # =====================================================

    recovery_ie = GTPInformationElement(
        ie_type=3,       # Recovery
        instance=0,
        value=b"\x00"
    )


    # =====================================================
    # 3. Bearer Context
    # =====================================================

    # -----------------------------------------------------
    # Bearer Cause
    # -----------------------------------------------------

    bearer_cause_value = bytes([
        16,      # Cause = Request accepted
        0x00,
        0x00,
        0x00
    ])

    bearer_cause_ie = GTPInformationElement(
        ie_type=2,       # Cause
        instance=0,
        value=bearer_cause_value
    )


    # -----------------------------------------------------
    # EPS Bearer ID
    # -----------------------------------------------------

    # Example EBI = 5

    ebi_ie = GTPInformationElement(
        ie_type=73,      # EPS Bearer ID
        instance=0,
        value=b"\x05"
    )


    # -----------------------------------------------------
    # User Plane F-TEID
    # -----------------------------------------------------

    user_teid = 0x12345678

    # V4 = 1
    # Interface Type = 1

    fteid_flags = 0x80 | 1

    fteid_value = (
        bytes([fteid_flags]) +
        user_teid.to_bytes(4, "big") +
        bytes([127, 0, 0, 1])
    )

    fteid_ie = GTPInformationElement(
        ie_type=87,       # F-TEID
        instance=2,
        value=fteid_value
    )


    # =====================================================
    # Build Bearer Context
    # =====================================================

    bearer_payload = (
        bearer_cause_ie.encode() +
        ebi_ie.encode() +
        fteid_ie.encode()
    )

    bearer_context_ie = GTPInformationElement(
        ie_type=93,       # Bearer Context
        instance=0,
        value=bearer_payload
    )


    # =====================================================
    # Complete Response Payload
    # =====================================================

    gtp_payload = (
        cause_ie.encode() +
        recovery_ie.encode() +
        bearer_context_ie.encode()
    )


    # =====================================================
    # GTPv2 Header
    # =====================================================

    response_header = GTPHeader(
        message_type=35,      # Modify Bearer Response
        seq=seq,
        teid=teid
    )


    # =====================================================
    # GTPv2 Length
    # =====================================================

    # 4 bytes TEID
    # 4 bytes Sequence Number + Spare
    # + IE payload

    payload_length = 8 + len(gtp_payload)

    response = (
        response_header.encode(payload_length)
        +
        gtp_payload
    )

    return response
def delete_session_response(seq, teid):

    # Cause IE
    # Cause value 16 = Request accepted
    cause_value = bytes([16, 0x00, 0x00, 0x00])

    cause_ie = GTPInformationElement(
        ie_type=2,
        instance=0,
        value=cause_value
    )

    # Recovery IE
    recovery_ie = GTPInformationElement(
        ie_type=3,
        instance=0,
        value=b"\x00"
    )

    # Build GTPv2-C payload
    gtp_payload = (
        cause_ie.encode() +
        recovery_ie.encode()
    )

    # Delete Session Response = message type 37
    response_header = GTPHeader(
        message_type=37,
        seq=seq,
        teid=teid
    )

    # GTPv2 length:
    # TEID (4) + Sequence Number (3) + Spare (1) + payload
    payload_length = 8 + len(gtp_payload)

    response = (
        response_header.encode(payload_length)
        + gtp_payload
    )

    return response
def gtpv2_simulator(workspace_id):
    SERVER_IP = "0.0.0.0"
    SERVER_PORT = 2123

    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    )

    sock.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    sock.bind((SERVER_IP, SERVER_PORT))

    print(f"GTPv2 simulator listening on UDP {SERVER_PORT}")

    while running_tests_gtpv2.get(workspace_id, False):

        data, client_address = sock.recvfrom(65535)

        print(
            f"GTP simulator received "
            f"{len(data)} bytes from {client_address}"
        )
            # Parse received GTPv2 packet
        flags = data[0]
        message_type = data[1]
            # Check message type
        if message_type == 32:

            print("[+] Create Session Request received")

            # Check whether TEID is present
            teid_flag = flags & 0x08

            if teid_flag:

                teid = int.from_bytes(
                        data[4:8],
                        byteorder="big"
                    )

                seq = int.from_bytes(
                        data[8:11],
                        byteorder="big"
                    )

            else:

                teid = None

                seq = int.from_bytes(
                        data[4:7],
                        byteorder="big"
                    )

            print(f"[+] TEID: {teid:#x}")
            print(f"[+] Sequence Number: {seq}")
             # Create Session Response
            response_header = GTPHeader(
                    message_type=33,
                    seq=seq,
                    teid=teid
            )
            response_bytes = create_session_response(
            seq,
            teid
            )     

        # Echo the packet back
            sock.sendto(
            response_bytes,
            client_address
        )

            print("GTP response sent")
        if message_type == 34:

            print("[+] Modify Bearer Request received")

            # -----------------------------------------
            # Extract TEID
            # -----------------------------------------

            if flags & 0x08:

                teid = int.from_bytes(
                    data[4:8],
                    byteorder="big"
                )

                seq = int.from_bytes(
                    data[8:11],
                    byteorder="big"
                )

            else:

                teid = None

                seq = int.from_bytes(
                    data[4:7],
                    byteorder="big"
                )

            print(f"[+] Request TEID: {teid:#x}")
            print(f"[+] Request Sequence: {seq}")

    # -----------------------------------------
    # Build Modify Bearer Response
    # -----------------------------------------

            response = modify_bearer_response(
                seq,
                teid
            )

    # -----------------------------------------
    # Send response
    # -----------------------------------------

            sock.sendto(
            response,
            client_address
            )

            print( "[+] Modify Bearer Response sent")
        if message_type == 36:
            print("[+] Delete Session Request received")

            if flags & 0x08:
                teid = int.from_bytes(
                    data[4:8],
                    byteorder="big"
                )

                seq = int.from_bytes(
                data[8:11],
                byteorder="big"
                )

            else:
                teid = None

                seq = int.from_bytes(
                    data[4:7],
                    byteorder="big"
                )

            print(f"[+] Request TEID: {teid:#x}")
            print(f"[+] Request Sequence: {seq}")

            response = delete_session_response(
            seq,
            teid
            )

            sock.sendto(
                response,
                client_address
                )

            print("[+] Delete Session Response sent")
        running_tests_gtpv2[workspace_id] = False

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
    found_messages = list(messages_collection.find({"workspace_id": workspace_id}))
    existing_nodes = {node.name for node in data.nodesData}

    for message in found_messages:
        source_exists = message.get("source") in existing_nodes
        destination_exists = message.get("destination") in existing_nodes

        # Delete the message if one of its nodes was deleted
        if not source_exists or not destination_exists:
            messages_collection.delete_one({
                "_id": message["_id"]
            }) 
                

    result = workspaces_collection.update_one(
        {"_id": ObjectId(workspace_id)},
        {"$set": {"nodes": updated_nodes,
            "connections": updated_connections,"messages": updated_messages}}
    )
    return {"count": result.modified_count}


                    
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
                    "protocol": "",
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
                            command_code=DIAMETER_MESSAGES[message["label"].split("_")[1]]["command_code"],
                            application_id=DIAMETER_MESSAGES[message["label"].split("_")[1]]["application_id"],
                            flags=DIAMETER_MESSAGES[message["label"].split("_")[1]]["flags"],
                            hop_id=hop_id,
                            end_id=end_id
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
                                mnc = node['mnc']
                                mcc = node['mcc']
                                break
                        value4 = encode_ipv4(ip_address_des)
                        diameter_avp4 = DiameterAVP(
                        code=AVP_DICTIONARY["Host-IP-Address"]["code"],
                        value=value4,
                        mandatory=True,
                        vendor_id=None
                    )
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
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        try:
                            sock.connect((ip_address_des, 3868))
                            sock.sendall(diameter_message)
                            sock.settimeout(1) 
                            response = sock.recv(4096)
                        except socket.timeout:
                            response = None
                        #wrpcap(f"./pcap_files/{workspace_id}_diameter_test_scapy.pcap", packet)
            for message in messages:
                if(message["protocol"]== "GTPv2"):
                    label = message["label"].split("_")[1]
                    if "Request" in label:
                        teid = None
                    else:
                        teid = random.randint(0, 0xFFFFFFFF)
                    gtp_header = GTPHeader(
                        message_type=GTP_MESSAGES[label]["message_type"],
                        teid=teid,
                        seq=random.randint(0, 0xFFFFFF)
                    )
                    for node in workspace['nodes']:
                        if message["source"]==node["name"]:
                            ip_address_source = node['ip']
                        if message["destination"]==node["name"]:
                            ip_address_des = node['ip']
                    imsi_ie = GTPInformationElement(ie_type=1, instance=0, value=bytes.fromhex("01100121436587f9"))
                    apn_ie = GTPInformationElement(
                        ie_type=71,
                        instance=0,
                        value=encode_apn("internet")
                    )
                    rat_ie = GTPInformationElement(ie_type=82, instance=0, value=b"\x06")
                    pdn_ie = GTPInformationElement(ie_type=99, instance=0, value=b"\x01")
                    serving_network_ie = GTPInformationElement(ie_type=83, instance=0, value=bytes.fromhex("00f110"))
                            
                    fteid_ie = GTPInformationElement(
                        ie_type=87,
                        instance=0,
                        value=encode_f_teid(
                            teid=0x12345678,
                            ipv4=ip_address_source
                        )
                    )
                    ebi_ie = GTPInformationElement(
                        ie_type=73,
                        instance=0,
                        value=struct.pack("!B", 5)
                    )
                    bearer_fteid = GTPInformationElement(
                        ie_type=87,
                        instance=0,
                        value=encode_f_teid(
                            teid=0x87654321,
                            ipv4=ip_address_source
                        )
                    )
                    bearer_context_value = (
                        ebi_ie.encode() +
                        bearer_fteid.encode()
                    )

                    bearer_context_ie = GTPInformationElement(
                        ie_type=93,
                        instance=0,
                        value=bearer_context_value
                    )
                    ambr_ie = GTPInformationElement(
                        ie_type=72,
                        instance=0,
                        value=encode_ambr(
                            ul=100000,
                            dl=100000
                        )
                    )

                        
                    gtp_payload = (
                        imsi_ie.encode() + 
                        rat_ie.encode() + 
                        serving_network_ie.encode() + 
                        fteid_ie.encode() + 
                        apn_ie.encode() + 
                        pdn_ie.encode() + 
                        ambr_ie.encode() + 
                        bearer_context_ie.encode()
                    )

                    if gtp_header.teid is None:
                        message_length = 4 + len(gtp_payload)
                    else:
                        message_length = 8 + len(gtp_payload)

                    gtp_header = gtp_header.encode(message_length)
                    gtp_packet = gtp_header + gtp_payload

                    packet = (
                        IP(src=ip_address_source, dst=ip_address_des)
                        / UDP(sport=2123, dport=2123)
                        / Raw(gtp_packet)
                    )
                    response = sr1(packet, timeout=2, verbose=False)
                    print("GTP Create Session Request sent from " + ip_address_source + " to " + ip_address_des)
                    print(gtp_packet.hex())
                    wrpcap(f"./pcap_files/{workspace_id}_gtp_test_scapy.pcap", packet)
                if(message["protocol"]=="S1AP"):
                    for node in workspace['nodes']:
                        if node["name"]=="MME":
                            ip_address_mme = node['ip']
                        if node["name"]=="eNB":
                            ip_address_enb = node['ip']
                    pdu = S1AP_PDU_Descriptions.S1AP_PDU
                    if(message["source"].split("-")[0]=="eNB"):
                        pdu.set_val((
    "initiatingMessage",
    {
        "procedureCode": 17,
        "criticality": "reject",
        "value": (
            "S1SetupRequest",
            {
                "protocolIEs": [
                    {
                        "id": 59,
                        "criticality": "reject",
                        "value": (
                            "Global-ENB-ID",
                            {
                                "pLMNidentity": b"\x00\xf1\x10",
                                "eNB-ID": (
                                    "macroENB-ID",
                                    (0x12345, 20)
                                )
                            }
                        )
                    },
                    {
                        "id": 64,
                        "criticality": "reject",
                        "value": (
                            "SupportedTAs",
                            [
                                {
                                    "tAC": b"\x00\x01",
                                    "broadcastPLMNs": [
                                        b"\x00\xf1\x10"
                                    ]
                                }
                            ]
                        )
                    }
                ]
            }
        )
    }
))

                        encoded = pdu.to_aper()
                        ip_address_source = ip_address_enb
                        ip_address_des = ip_address_mme
                        sport = 50002
                        dport = 36412
                        # 1. SEND INIT CHUNK
                        # Generate a unique Initial Tag for yourself
                        my_init_tag = 0xABCDE123 
                        init_pkt = scapy.IP(src=ip_address_source, dst=ip_address_des) / scapy.SCTP(sport=sport, dport=dport, tag=0) / scapy.SCTPChunkInit(init_tag=my_init_tag, a_rwnd=102400,n_out_streams=10, n_in_streams=10, init_tsn=1000)
                        init_ack_pkt = scapy.sr1(init_pkt, timeout=2, verbose=False)
                        mme_init_tag = None
                        cookie = None
                        if init_ack_pkt and init_ack_pkt.haslayer(scapy.SCTPChunkInitAck):
                            # Extract parameters required by the standard to proceed
                            mme_init_tag = init_ack_pkt[scapy.SCTPChunkInitAck].init_tag
                            mme_tsn = init_ack_pkt[scapy.SCTPChunkInitAck].init_tsn
                            cookie = init_ack_pkt[scapy.SCTPChunkInitAck].params
                            print(f"[*] Received INIT_ACK. MME Tag: {hex(mme_init_tag)}")
                        cookie_ack_pkt = None
                        if mme_init_tag and cookie:
                            cookie_echo_pkt = scapy.IP(src=ip_address_source, dst=ip_address_des) / scapy.SCTP(sport=sport, dport=dport, tag=mme_init_tag) / scapy.SCTPChunkCookieEcho(cookie=cookie)
                            print("[*] Sending SCTP COOKIE_ECHO...")
                            cookie_ack_pkt = scapy.sr1(cookie_echo_pkt, timeout=2, verbose=False)
                        if cookie_ack_pkt and cookie_ack_pkt.haslayer(SCTPChunkCookieAck):
                            print("[+] SCTP Association Established successfully!")
                        packet = (
                            IP(src=ip_address_source, dst=ip_address_des)
                            /
                            scapy.SCTP(
                                sport=sport,
                                dport=dport,
                                tag=mme_init_tag
                            )
                            /
                            scapy.SCTPChunkData(
                                tsn=1000,
                                stream_id=0,
                                stream_seq=0,
                                proto_id=18,
                                beginning=1,
                                ending=1,
                                data=encoded    # S1AP Payload Protocol Identifier (PPID)
                            )
                        )
                        response = sr1(packet, timeout=2, verbose=False)
                        s1ap_type = "S1SetupRequest"
                        print("S1AP S1SetupRequest sent from " + ip_address_source + " to " + ip_address_des)
                    else:
                        pdu.set_val((
    "successfulOutcome",
    {
        "procedureCode": 17,
        "criticality": "reject",
        "value": (
            "S1SetupResponse",
            {
                "protocolIEs": [

                    # -----------------------------------------
                    # MME Name
                    # -----------------------------------------
                    {
                        "id": 61,
                        "criticality": "ignore",
                        "value": (
                            "MMEname",
                            "MME"
                        )
                    },

                    # -----------------------------------------
                    # Served GUMMEIs
                    # -----------------------------------------
                    {
                        "id": 105,
                        "criticality": "reject",
                        "value": (
                            "ServedGUMMEIs",
                            [
                                {
                                    "servedGroupIDs": [
                                        b"\x00\x01"
                                    ],
                                    "servedMMECs": [
                                        b"\x01"
                                    ],
                                    "servedPLMNs": [
                                        b"\x00\xf1\x10"
                                    ]
                                }
                            ]
                        )
                    },

                    # -----------------------------------------
                    # Relative MME Capacity
                    # -----------------------------------------
                    {
                        "id": 87,
                        "criticality": "ignore",
                        "value": (
                            "RelativeMMECapacity",
                            255
                        )
                    }

                ]
            }
        )
    }
))
                        encoded = pdu.to_aper()
                        ip_address_source = ip_address_mme
                        ip_address_des = ip_address_enb
                        my_init_tag = 0xABCDE123 
                        packet = (
                            IP(src=ip_address_source, dst=ip_address_des)
                            /
                            SCTP(
                                sport=36412,
                                dport=36412,
                                tag=my_init_tag
                            )
                            /
                            SCTPChunkData(
                                tsn=1000,
                                stream_id=0,
                                stream_seq=0,
                                proto_id=18,
                                beginning=1,
                                ending=1,
                                data=encoded        # S1AP Payload Protocol Identifier (PPID)
                            )
                        )
                        response = sr1(packet, timeout=2, verbose=False)
                        s1ap_type = "S1SetupResponse"
                        print("S1AP S1SetupResponse sent from " + ip_address_source + " to " + ip_address_des)

                if(message["protocol"]=="GTPv1-U"):
                    for node in workspace['nodes']:
                        if message["source"]==node["name"]:
                            ip_address_source = node['ip']
                        if message["destination"]==node["name"]:
                            ip_address_des = node['ip']
                    teid = 0x12345678
                    inner_packet = (
                                        IP(
                                            src="10.10.10.1",
                                            dst="10.10.10.2"
                                           )
                                        /
                                        UDP(
                                            sport=5000,
                                            dport=5001
                                            )
                                        /
                                            b"Hello UE"
                                        )
                    packet = (
                            IP(
                                src="127.0.0.1",
                                dst="127.0.0.1"
                                )
                            /
                            UDP(
                                sport=2152,
                                dport=2152
                                )
                            /
                            GTP_U_Header(
                                teid=teid,
                                gtp_type=255
                                )
                            /
                            inner_packet
                        )
                    response = sr1(packet, timeout=2, verbose=False)



        time.sleep(interval)


def is_port_open(ip, port=443, timeout=1.0):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False

@app.post("/test_flow_with_protocol_all/{workspace_id}")
def test_nodes_with_protocol_all(workspace_id:str,data:ProtocolMessage):
    if data.frequency == "once":
        messages =list(messages_collection.find({"workspace_id":workspace_id}))
        workspace = workspaces_collection.find_one({"_id": ObjectId(workspace_id)})
        responses = []
        if (messages):
                for message in messages:
                    response = None
                    response2 = ""
                    if(message["protocol"] == "http2"):
                        mode="Simulated"
                        destination_ip = "127.0.0.1"
                        ip_address_source = "127.0.0.1"
                        ip_address_source2 ="127.0.0.1"
                        destination_ip2 = "127.0.0.1"
                        for node in workspace['nodes']:
                            if node["mode"] == "Available in Open5GS" and node["name"]==message["destination"]:
                                mode = "Available in Open5GS"
                            if node["isUnderTest"] and node["name"]==message["destination"]:
                                destination_ip = node['ip']
                            if node["isUnderTest"] and node["name"]==message["source"]:
                                ip_address_source = message["ip"]
                            if node["name"]==message["source"] and message["ip"]:
                                ip_address_source2 = message["ip"]
                            if node["name"]==message["destination"] and message["ip"]:
                                destination_ip2 = message["ip"]
                        running_tests_http2[workspace_id] = False
                        running_tests_http2[workspace_id] = True
                        thread = threading.Thread(
                                target=http2_simulator,
                                args=(443,destination_ip,ip_address_source, workspace_id,),
                                daemon=True
                            )
                        thread.start()
                        time.sleep(0.5)
                        if ip_address_source =="127.0.0.1":
                            payload = message["MessageContents"]["body"]
                            body = json.dumps(payload).encode("utf-8")
                            response=send_h2c_request(
                                        destination_ip,
                                        443,
                                        body
                            )
                            if (response):
                                response_body = response.decode("utf-8")
                        running_tests_http2[workspace_id] = False
                        if(response):
                            responses.append({
                            "message_id": str(message["_id"]),
                            "protocol": "http2",
                            "destination_ip": destination_ip2,
                            "label": message.get("label"),
                            "status_code": "success",
                            "http_version": "HTTP2",
                            "body": response_body
                        })
                        else:
                            responses.append({
                            "message_id": str(message["_id"]),
                            "protocol": "http2",
                            "destination_ip": destination_ip2,
                            "label": message.get("label"),
                            "status_code": "Error",
                            "http_version": "Error",
                            "body": "Simulated node unreachable"
                })
                    if(message["protocol"]=="diameter"):
                        destination_ip = "127.0.0.1"
                        ip_address_source = "127.0.0.1"
                        for node in workspace['nodes']:
                            if node["isUnderTest"] and node["name"]==message["destination"]:
                                destination_ip = node['ip']
                            if node["isUnderTest"] and node["name"]==message["source"]:
                                ip_address_source = message["ip"]
                            if destination_ip != "127.0.0.1" and ip_address_source != "127.0.0.1":
                                destination_ip = "127.0.0.1"
                                ip_address_source = "127.0.0.1"
                        running_tests_diameter[workspace_id] = False
                        running_tests_diameter[workspace_id] = True
                        diameter_responses[workspace_id] = None
                        thread = threading.Thread(
                                                target=diameter_simulator,
                                                args=(3868,destination_ip,ip_address_source, workspace_id),
                                                daemon=True
                                                )

                        thread.start()
                        hop_id = random.randint(0, 0xFFFFFFFF)
                        end_id = random.randint(0, 0xFFFFFFFF)
                        diameter_header = DiameterHeader(
                            command_code=DIAMETER_MESSAGES[message["label"].split("_")[1]]["command_code"],
                            application_id=DIAMETER_MESSAGES[message["label"].split("_")[1]]["application_id"],
                            flags=DIAMETER_MESSAGES[message["label"].split("_")[1]]["flags"],
                            hop_id=hop_id,
                            end_id=end_id
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
                            if node["name"]==message["destination"]:
                                ip_address_des = node['ip']
                                mnc = node['mnc']
                                mcc = node['mcc']
                                break
                        if not ip_address_des:
                            ip_address_des = "127.0.0.1"
                        value4 = encode_ipv4(ip_address_des)
                        diameter_avp4 = DiameterAVP(
                        code=AVP_DICTIONARY["Host-IP-Address"]["code"],
                        value=value4,
                        mandatory=True,
                        vendor_id=None
                    )
                        value5 = encode_utf8(
                        "LabX"
                                        )

                        diameter_avp5 = DiameterAVP(
                        code=AVP_DICTIONARY["Product-Name"]["code"],
                        value=value5,
                        mandatory=True,
                        vendor_id=None
                                                )



                        value6 = encode_uint32(
                        1
                    )

                        diameter_avp6 = DiameterAVP(
                        code=AVP_DICTIONARY["Origin-State-Id"]["code"],
                        value=value6,
                        mandatory=True,
                        vendor_id=None
                        )
                        avp1 = diameter_avp1.encode()
                        avp2 = diameter_avp2.encode()
                        avp3 = diameter_avp3.encode()
                        avp4 = diameter_avp4.encode()
                        avp5 = diameter_avp5.encode()
                        avp6 = diameter_avp6.encode()
                        message_length = (
                        20
                        + len(avp1)
                        + len(avp2)
                        + len(avp3)
                        + len(avp4)
                        + len(avp5)
                        + len(avp6)
                    )
                        header = diameter_header.encode(message_length)
                        diameter_message = (
                        header
                        + avp1
                        + avp2
                        + avp3
                        + avp4
                        + avp5
                        + avp6
                    )
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        try:
                            if ip_address_source == "127.0.0.1":
                                sock.connect((destination_ip, 3868))
                                sock.sendall(diameter_message)
                                sock.settimeout(2) 
                                header = recv_exact(sock, 20)
                            if header is None:
                                response = None
                            else:
                                # Diameter Message Length is bytes 1-3
                                message_length = int.from_bytes(
                                header[1:4],
                                byteorder="big"
                            )

                                # Remaining bytes after the 20-byte header
                                body_length = message_length - 20
                                body = recv_exact(sock, body_length)
                                if body is None:
                                    response = None
                                else:
                                    response = header + body
                            if response:
                                print("Diameter response received:")
                        except socket.timeout:
                            response = None
                            print("Diameter response timeout")
                        finally:
                            sock.close()
                        response1 = diameter_responses[workspace_id]
                        running_tests_diameter[workspace_id] = False
                        if(response1):
                            responses.append({
                            "protocol": "diameter",
                            "destination_ip": ip_address_des,
                            "diameter_message_version": message["label"].split("_")[1],
                            "source": ip_address_source,
                            "status": "success",
                            "body": f"response size : {len(response1)} bytes"
                        })
                        else:
                            responses.append({
                            "protocol": "diameter",
                            "destination_ip": ip_address_des,
                            "diameter_message_version": message["label"].split("_")[1],
                            "source": ip_address_source,
                            "status": "packets were not sent successfully",
                            "body": "Simulated node unreachable"
                })
                    if(message["protocol"]== "GTPv2"):
                        ip_address_source = "127.0.0.1"
                        running_tests_gtpv2[workspace_id] = False
                        running_tests_gtpv2[workspace_id] = True
                        thread = threading.Thread(
                            target=gtpv2_simulator,
                            args=(workspace_id,),
                            daemon=True
                        )
                        thread.start()
                        label = message["label"].split("_")[1]
                        if "Request" in label:
                            teid = random.randint(0, 0xFFFFFFFF)
                        else:
                            teid = None
                        gtp_header = GTPHeader(
                            message_type=GTP_MESSAGES[label]["message_type"],
                            teid=teid,
                            seq=random.randint(0, 0xFFFFFF)
                        )
                        for node in workspace['nodes']:
                            if message["source"]==node["name"]:
                                ip_address_source = node['ip']
                            if message["destination"]==node["name"]:
                                ip_address_des = node['ip']
                        imsi_ie = GTPInformationElement(ie_type=1, instance=0, value=bytes.fromhex("01100121436587f9"))
                        apn_ie = GTPInformationElement(
                            ie_type=71,
                            instance=0,
                            value=encode_apn("internet")
                        )
                        rat_ie = GTPInformationElement(ie_type=82, instance=0, value=b"\x06")
                        pdn_ie = GTPInformationElement(ie_type=99, instance=0, value=b"\x01")
                        serving_network_ie = GTPInformationElement(ie_type=83, instance=0, value=bytes.fromhex("00f110"))
                            
                        fteid_ie = GTPInformationElement(
                            ie_type=87,
                            instance=0,
                            value=encode_f_teid(
                                teid=0x12345678,
                                ipv4=ip_address_source
                            )
                        )
                        ebi_ie = GTPInformationElement(
                            ie_type=73,
                            instance=0,
                            value=struct.pack("!B", 5)
                        )
                        bearer_fteid = GTPInformationElement(
                            ie_type=87,
                            instance=0,
                            value=encode_f_teid(
                                teid=0x87654321,
                                ipv4=ip_address_source
                            )
                        )
                        bearer_context_value = (
                                ebi_ie.encode() +
                                bearer_fteid.encode()
                        )

                        bearer_context_ie = GTPInformationElement(
                            ie_type=93,
                            instance=0,
                            value=bearer_context_value
                        )
                        ambr_ie = GTPInformationElement(
                            ie_type=72,
                            instance=0,
                            value=encode_ambr(
                                ul=100000,
                                dl=100000
                            )
                        )
                        
                        gtp_payload = (
                            imsi_ie.encode() + 
                            rat_ie.encode() + 
                            serving_network_ie.encode() + 
                            fteid_ie.encode() + 
                            apn_ie.encode() + 
                            pdn_ie.encode() + 
                            ambr_ie.encode() + 
                            bearer_context_ie.encode()
                        )

                        if gtp_header.teid is None:
                            message_length = 4 + len(gtp_payload)
                        else:
                            message_length = 8 + len(gtp_payload)

                        gtp_header = gtp_header.encode(message_length)
                        gtp_packet = gtp_header + gtp_payload

                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

                        sock.bind(("127.0.0.1", 50000))

                        sock.sendto(
                                   gtp_packet,
                                   ("127.0.0.1", 2123)
                                    )

                        sock.settimeout(2)

                        try:
                            response, addr = sock.recvfrom(65535)

                            print(f"GTP response received from {addr}")
                            print(f"Response length: {len(response)} bytes")

                        except socket.timeout:
                            print("No GTP response received")

                        finally:
                            sock.close()
                        print("GTP Create Session Request sent from " + ip_address_source + " to " + ip_address_des)
                        if(response):
                            running_tests_gtpv2[workspace_id] = False
                            responses.append({
                            "protocol": "GTPv2",
                            "destination_ip": ip_address_des,
                            "source": ip_address_source,
                            "message": label,
                            "status": "success",
                            "body": f"Response  {len(response)} bytes"
                        })
                        else:
                            responses.append({
                            "protocol": "GTPv2",
                            "destination_ip": ip_address_des,
                            "source": ip_address_source,
                            "message": label,
                            "status": "packets sent successfully",
                            "body": "no response received"
                })
                    if(message["protocol"]=="S1AP"):
                        for node in workspace['nodes']:
                            if node["name"]=="MME":
                                ip_address_mme = node['ip']
                            if node["name"]=="eNB":
                                ip_address_enb = node['ip']
                            pdu = S1AP_PDU_Descriptions.S1AP_PDU
                        if(message["source"].split("-")[0]=="eNB"):
                            pdu.set_val((
    "initiatingMessage",
    {
        "procedureCode": 17,
        "criticality": "reject",
        "value": (
            "S1SetupRequest",
            {
                "protocolIEs": [
                    {
                        "id": 59,
                        "criticality": "reject",
                        "value": (
                            "Global-ENB-ID",
                            {
                                "pLMNidentity": b"\x00\xf1\x10",
                                "eNB-ID": (
                                    "macroENB-ID",
                                    (0x12345, 20)
                                )
                            }
                        )
                    },
                    {
                        "id": 64,
                        "criticality": "reject",
                        "value": (
                            "SupportedTAs",
                            [
                                {
                                    "tAC": b"\x00\x01",
                                    "broadcastPLMNs": [
                                        b"\x00\xf1\x10"
                                    ]
                                }
                            ]
                        )
                    }
                ]
            }
        )
    }
))

                            encoded = pdu.to_aper()
                            ip_address_source = ip_address_enb
                            ip_address_des = ip_address_mme
                            ip_address_source = "127.0.0.1"
                            ip_address_des = "127.0.0.1"
                            sport = 50002
                            dport = 36412
                        # 1. SEND INIT CHUNK
                        # Generate a unique Initial Tag for yourself
                            my_init_tag = 0xABCDE123 
                            init_pkt = scapy.IP(src=ip_address_source, dst=ip_address_des) / scapy.SCTP(sport=sport, dport=dport, tag=0) / scapy.SCTPChunkInit(init_tag=my_init_tag, a_rwnd=102400,n_out_streams=10, n_in_streams=10, init_tsn=1000)
                            init_ack_pkt = scapy.sr1(init_pkt, timeout=2, verbose=False)
                            mme_init_tag = None
                            cookie = None
                            print(init_ack_pkt)
                            if init_ack_pkt and init_ack_pkt.haslayer(scapy.SCTPChunkInitAck):
                            # Extract parameters required by the standard to proceed
                                mme_init_tag = init_ack_pkt[scapy.SCTPChunkInitAck].init_tag
                                mme_tsn = init_ack_pkt[scapy.SCTPChunkInitAck].init_tsn
                                cookie = init_ack_pkt[scapy.SCTPChunkInitAck].params
                                print(f"[*] Received INIT_ACK. MME Tag: {hex(mme_init_tag)}")
                            cookie_ack_pkt = None
                            if mme_init_tag and cookie:
                                cookie_echo_pkt = scapy.IP(src=ip_address_source, dst=ip_address_des) / scapy.SCTP(sport=sport, dport=dport, tag=mme_init_tag) / scapy.SCTPChunkCookieEcho(cookie=cookie)
                                print("[*] Sending SCTP COOKIE_ECHO...")
                                cookie_ack_pkt = scapy.sr1(cookie_echo_pkt, timeout=2, verbose=False)
                            if cookie_ack_pkt and cookie_ack_pkt.haslayer(SCTPChunkCookieAck):
                                print("[+] SCTP Association Established successfully!")
                            packet = (
                            IP(src=ip_address_source, dst=ip_address_des)
                            /
                            scapy.SCTP(
                                sport=sport,
                                dport=dport,
                                tag=mme_init_tag
                            )
                            /
                            scapy.SCTPChunkData(
                                tsn=1000,
                                stream_id=0,
                                stream_seq=0,
                                proto_id=18,
                                beginning=1,
                                ending=1,
                                data=encoded    # S1AP Payload Protocol Identifier (PPID)
                            )
                        )
                            response = sr1(packet, timeout=2, verbose=False)
                            s1ap_type = "S1SetupRequest"
                            print("S1AP S1SetupRequest sent from " + ip_address_source + " to " + ip_address_des)
                        else:
                            pdu.set_val((
    "successfulOutcome",
    {
        "procedureCode": 17,
        "criticality": "reject",
        "value": (
            "S1SetupResponse",
            {
                "protocolIEs": [

                    # -----------------------------------------
                    # MME Name
                    # -----------------------------------------
                    {
                        "id": 61,
                        "criticality": "ignore",
                        "value": (
                            "MMEname",
                            "MME"
                        )
                    },

                    # -----------------------------------------
                    # Served GUMMEIs
                    # -----------------------------------------
                    {
                        "id": 105,
                        "criticality": "reject",
                        "value": (
                            "ServedGUMMEIs",
                            [
                                {
                                    "servedGroupIDs": [
                                        b"\x00\x01"
                                    ],
                                    "servedMMECs": [
                                        b"\x01"
                                    ],
                                    "servedPLMNs": [
                                        b"\x00\xf1\x10"
                                    ]
                                }
                            ]
                        )
                    },

                    # -----------------------------------------
                    # Relative MME Capacity
                    # -----------------------------------------
                    {
                        "id": 87,
                        "criticality": "ignore",
                        "value": (
                            "RelativeMMECapacity",
                            255
                        )
                    }

                ]
            }
        )
    }
))
                            encoded = pdu.to_aper()
                            ip_address_source = ip_address_mme
                            ip_address_des = ip_address_enb
                            my_init_tag = 0xABCDE123 
                            packet = (
                            IP(src=ip_address_source, dst=ip_address_des)
                            /
                            SCTP(
                                sport=36412,
                                dport=36412,
                                tag=my_init_tag
                            )
                            /
                            SCTPChunkData(
                                tsn=1000,
                                stream_id=0,
                                stream_seq=0,
                                proto_id=18,
                                beginning=1,
                                ending=1,
                                data=encoded        # S1AP Payload Protocol Identifier (PPID)
                            )
                        )
                            response = sr1(packet, timeout=2, verbose=False)
                            s1ap_type = "S1SetupResponse"
                            print("S1AP S1SetupResponse sent from " + ip_address_source + " to " + ip_address_des)
                        if(response):
                            responses.append({
                            "protocol": "S1AP",
                            "destination_ip": ip_address_des,
                            "source": ip_address_source,
                            "type": s1ap_type,
                            "status": "handshake complete and response received",
                            "body": response.summary()
                        })
                        else:
                            responses.append({
                            "protocol": "S1AP",
                            "destination_ip": ip_address_des,
                            "source": ip_address_source,
                            "type": s1ap_type,
                            "status": "packets sent successfully",
                            "body": "no response received"
                })

                    if(message["protocol"]=="GTPv1-U"):
                        for node in workspace['nodes']:
                            if message["source"]==node["name"]:
                                ip_address_source = node['ip']
                            if message["destination"]==node["name"]:
                                ip_address_des = node['ip']
                        running_tests_gtpv1[workspace_id] = False
                        running_tests_gtpv1[workspace_id] = True
                        thread = threading.Thread(
                            target=gtpv1_simulator,
                            args=(workspace_id,),
                            daemon=True
                        )
                        thread.start()
                        teid = 0x12345678
                        inner_packet = (
                                        IP(
                                            src="10.10.10.1",
                                            dst="10.10.10.2"
                                           )
                                        /
                                        UDP(
                                            sport=5000,
                                            dport=5001
                                            )
                                        /
                                            b"Hello UE"
                                        )
                        packet = (
                            IP(
                                src="127.0.0.1",
                                dst="127.0.0.1"
                                )
                            /
                            UDP(
                                sport=2152,
                                dport=2152
                                )
                            /
                            GTP_U_Header(
                                teid=teid,
                                gtp_type=255
                                )
                            /
                            inner_packet
                        )
                        response = sr1(packet, timeout=2, verbose=False)
                        running_tests_gtpv1[workspace_id]=False
                        if(response):
                            responses.append({
                            "protocol": "GTPv1-U",
                            "destination_ip": ip_address_des,
                            "source": ip_address_source,
                            "type": "GTPv1-U",
                            "status": "response received",
                            "body": response.summary()
                        })
                        else:
                            responses.append({
                            "protocol": "GTPv1-U",
                            "destination_ip": ip_address_des,
                            "source": ip_address_source,
                            "type": "GTPv1-U",
                            "status": "packets sent successfully",
                            "body": "no response received"
                            })


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