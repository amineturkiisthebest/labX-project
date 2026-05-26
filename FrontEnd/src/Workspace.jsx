import { useState, useEffect, useRef, useCallback } from "react";
import "./workspace.css";
import { useNavigate, useParams } from "react-router-dom";

function Workspace() {
  const navigate = useNavigate();
  const canvasRef = useRef(null);
  const ref_nodes = useRef([]);
  const [nodes, setNodes] = useState([]);
  const [saved_nodes, setSavedNodes] = useState([]);
  const [isSaved, setIsSaved] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [configNodeId, setConfigNodeId] = useState(null);
  const [nodeConfigs, setNodeConfigs] = useState({});
  const [ip, setIp] = useState("");
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState("");
  const [modalMessage, setModalMessage] = useState("");
  const [modalConnections, setModalConnections] = useState([]);
  const matchingNodeIds = useRef([]);
  const rootNodeId = useRef("");
  const [connections, setConnections] = useState([]);
  const [messages, setMessages] = useState([]);
  const [, setRenderTick] = useState(0);

  // Connection Messages State
  const [showMessagesModal, setShowMessagesModal] = useState(false);
  const [messageLabel, setMessageLabel] = useState("");
  const [messageSource, setMessageSource] = useState("");
  const [messageDestination, setMessageDestination] = useState("");
  const [messageInterface, setMessageInterface] = useState("");
  const [messageDescription, setMessageDescription] = useState("");
  const [messageContent, setMessageContent] = useState("");
  const [messageType, setMessageType] = useState("");
  const [messageProtocol, setMessageProtocol] = useState("");
  const [fromId, setFromId] = useState("");
  const [toId, setToId] = useState("");

  const token = localStorage.getItem("token");
  let workspace_id = useParams();

  const setAllNodes = async (e) => {
    const response = await fetch("http://localhost:8000/nodes", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });
    const nodes_data = await response.json();
    setNodes(nodes_data.nodes);
    ref_nodes.current.push(nodes_data.nodes);
  }
  const setNodeUnderTest = (nodeId) => {
    setNodeConfigs(prev => ({
      ...prev,

      [nodeId]: {
        ...prev[nodeId],
        isUnderTest: true
      }
    }));
  };
  const resetNodeUnderTest = (nodeId) => {
    setNodeConfigs(prev => ({
      ...prev,

      [nodeId]: {
        ...prev[nodeId],
        isUnderTest: false
      }
    }));
  };

  const loadWorkspace = async () => {
    const response = await fetch(`http://localhost:8000/load_workspace/${workspace_id.id}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });
    const data = await response.json();
    setSavedNodes(data.nodes);
    const configs = {};
    data.nodes.forEach(node => {
      configs[node.id] = {
        ip: node.ip,
        url: node.url,
        mode: node.mode,
        configured: node.configured,
        isUnderTest: node.isUnderTest
      };
    });

    setNodeConfigs(configs);

    if (data.connections) {
      const formattedConnections = data.connections.map(conn => ({
        from: conn.from_id,
        to: conn.to_id,
        interface_name: conn.name
      }));
      setConnections(formattedConnections);
    }

  }

  // Draw connections or background (optional)
  useEffect(() => {
    if (!token) {
      navigate("/");

    }
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    // Simple grid background
    ctx.strokeStyle = "rgba(255,255,255,0.1)";
    for (let x = 0; x <= canvas.width; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y <= canvas.height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }
    loadWorkspace();
    setAllNodes();
  }, [token, navigate]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !saved_nodes || saved_nodes.length === 0) return;

    saved_nodes.forEach(node => {
      // Avoid creating duplicates if they are already placed
      if (document.getElementById(node.id)) return;

      const nodeEl = document.createElement('div');
      const uniqueId = node.id;
      nodeEl.id = uniqueId;
      nodeEl.className = 'canvas-node';
      nodeEl.style.left = `${node.position.x}px`;
      nodeEl.style.top = `${node.position.y}px`;
      nodeEl.draggable = true;
      nodeEl.innerHTML = `<button type="button" id="config_${uniqueId}" class="config-node-btn">⚙</button><button type="button" id="delete_${uniqueId}" class="delete-node-btn">x</button><button type="button" id="connection_${uniqueId}"
      class="connection-btn">+</button><button type="button" id="test_${uniqueId}" class="test-node-btn">▶</button><div class="dot" style="background-color:#1E5E74"></div><span>${node.name}</span>`;

      nodeEl.ondragstart = (dragEvent) => {
        const elRect = nodeEl.getBoundingClientRect();
        const ox = dragEvent.clientX - elRect.left;
        const oy = dragEvent.clientY - elRect.top;

        dragEvent.dataTransfer.setData("application/reactflow", JSON.stringify({
          name: node.name,
          isPlaced: true,
          elementId: uniqueId,
          offsetX: ox,
          offsetY: oy
        }));
        dragEvent.dataTransfer.effectAllowed = "move";
      };

      canvas.parentElement.appendChild(nodeEl);
      const connection = document.getElementById(`connection_${uniqueId}`);
      connection.addEventListener("click", () => {
        handleConnection(uniqueId);
      });
      const configBtn = document.getElementById(`config_${uniqueId}`);
      if (configBtn) {
        configBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          handleConfigNode(uniqueId);
        });
      }
      const deleteBtn = document.getElementById(`delete_${uniqueId}`);
      if (deleteBtn) {
        deleteBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          nodeEl.remove();
          setConnections(prev => prev.filter(c => c.from !== uniqueId && c.to !== uniqueId));
        });
      }
      const testBtn = document.getElementById(`test_${uniqueId}`);
      if (nodeConfigs[nodeEl.id].isUnderTest == true) {
        nodeEl.dataset.isTesting = "true";
        nodeEl.style.backgroundColor = "rgba(34, 197, 94, 0.2)";
        testBtn.style.backgroundColor = "#ef4444";
        testBtn.innerHTML = "■";
        testBtn.style.paddingLeft = "0";
      }
      if (testBtn) {
        testBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          const isTesting = nodeEl.dataset.isTesting === "true";
          if (isTesting) {
            resetNodeUnderTest(nodeEl.id);
            nodeEl.dataset.isTesting = "false";
            nodeEl.style.backgroundColor = "var(--glass-bg)";
            testBtn.style.backgroundColor = "#22c55e";
            testBtn.innerHTML = "▶";
            testBtn.style.paddingLeft = "1px";
          } else {
            setNodeUnderTest(nodeEl.id);
            nodeEl.dataset.isTesting = "true";
            nodeEl.style.backgroundColor = "rgba(34, 197, 94, 0.2)";
            testBtn.style.backgroundColor = "#ef4444";
            testBtn.innerHTML = "■";
            testBtn.style.paddingLeft = "0";
          }
        });
      }
    });
  }, [saved_nodes]);

  const saveWorkspace = async () => {
    const canvas = canvasRef.current;
    const placedNodes = canvas.parentElement.querySelectorAll('.canvas-node');
    const w_id = workspace_id.id;
    const existingConnections = Array.from(connections).map(conn => ({
      rootNodeName: document.getElementById(conn.from).querySelector('span').textContent,
      targetNodeName: document.getElementById(conn.to).querySelector('span').textContent,
      from_id: conn.from,
      to_id: conn.to,
      interface_name: conn.interface_name
    }));
    const nodesData = Array.from(placedNodes).map(node => ({
      id: node.id,
      name: node.querySelector('span').textContent,
      x: parseFloat(node.style.left),
      y: parseFloat(node.style.top),
      ip: nodeConfigs[node.id]?.ip || "",
      url: nodeConfigs[node.id]?.url || "",
      mode: nodeConfigs[node.id]?.mode || "",
      configured: nodeConfigs[node.id]?.configured || false,
      isUnderTest: nodeConfigs[node.id]?.isUnderTest || false
    }));
    const response = await fetch(`http://localhost:8000/save_workspace/${w_id}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ nodesData: nodesData, existingConnections: existingConnections, messages: messages }),
    });
    const data = await response.json();
    setIsSaved(true);
    setTimeout(() => {
      setIsSaved(false);
    }, 3000);
  }

  const handleConfigNode = (nodeId) => {
    setConfigNodeId(nodeId);
    setNodeConfigs(prev => {
      setIp(prev[nodeId]?.ip || "");
      setUrl(prev[nodeId]?.url || "");
      setMode(prev[nodeId]?.mode || "");
      return prev;
    });
    setShowConfigModal(true);
  };

  const saveNodeConfig = () => {
    if (configNodeId) {
      setNodeConfigs(prev => ({
        ...prev,
        [configNodeId]: { ip, url, mode, configured: true, isUnderTest: false }
      }));
    }
    console.log(nodeConfigs);
    setShowConfigModal(false);
  };

  const handleConnectionMessages = (fromId, toId) => {
    setFromId(fromId);
    setToId(toId);
    setShowMessagesModal(true);
  };

  const saveConnectionMessage = () => {
    const source = document.getElementById(fromId).querySelector('span').textContent;
    const destination = document.getElementById(toId).querySelector('span').textContent;
    const nodeDef = ref_nodes.current[0].find(n => n.name === source);
    let interfacesStr = "";
    if (nodeDef && nodeDef.Interfaces) {
      interfacesStr = nodeDef.Interfaces;
    }
    const interface_m = interfacesStr.split(";")
      .find(i => i.split("-")[1] === destination)
      .split("-")[0];
    setMessageSource(source);
    setMessageDestination(destination);
    setMessageInterface(interface_m);
    setMessages(prev => {

      const alreadyExists = prev.some(msg =>
        msg.label === messageLabel &&
        msg.source === messageSource &&
        msg.destination === messageDestination
      );

      if (alreadyExists) {
        return prev;
      }

      return [
        ...prev,
        {
          label: messageLabel,
          description: messageDescription,
          content: messageContent,
          type: messageType,
          protocol: messageProtocol,
          source: messageSource,
          destination: messageDestination,
          interface: messageInterface
        }
      ];
    });
    setShowMessagesModal(false);
  };

  const handleDragStart = (e, node) => {
    e.dataTransfer.setData("application/reactflow", JSON.stringify(node));
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const dataStr = e.dataTransfer.getData("application/reactflow");
    if (!dataStr) return;

    const nodeData = JSON.parse(dataStr);
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();

    const offsetX = nodeData.offsetX || 0;
    const offsetY = nodeData.offsetY || 0;
    const x = e.clientX - rect.left - offsetX;
    const y = e.clientY - rect.top - offsetY;

    const placedNodes = Array.from(canvas.parentElement.querySelectorAll('.canvas-node'));
    let finalName = nodeData.name;
    if (!nodeData.isPlaced) {
      const existingNames = placedNodes.map(node => node.querySelector('span')?.textContent);
      let counter = 1;
      while (existingNames.includes(finalName)) {
        finalName = `${nodeData.name}-${counter}`;
        counter++;
      }
      nodeData.name = finalName;
    }

    let currentWidth = 0;
    let currentHeight = 0;
    const existingEl = nodeData.elementId ? document.getElementById(nodeData.elementId) : null;

    if (existingEl) {
      currentWidth = existingEl.offsetWidth;
      currentHeight = existingEl.offsetHeight;
    } else {
      const tempEl = document.createElement('div');
      const uniqueId = 'placed-node-' + Math.random().toString(36).substr(2, 9);
      tempEl.id = uniqueId;
      tempEl.className = 'canvas-node';
      tempEl.style.visibility = 'hidden';
      tempEl.style.position = 'absolute';
      tempEl.innerHTML = `<button type="button" class="config-node-btn">⚙</button><button type="button" class="delete-node-btn">x</button><button type="button" 
       class="connection-btn">+</button><button type="button" class="test-node-btn">▶</button><div class="dot" style="background-color:#1E5E74"></div><span>${nodeData.name}</span>`;
      canvas.parentElement.appendChild(tempEl);
      currentWidth = tempEl.offsetWidth;
      currentHeight = tempEl.offsetHeight;
      canvas.parentElement.removeChild(tempEl);
    }
    const isOverlapping = placedNodes.some(node => {
      if (node.id === nodeData.elementId) return false;

      const nodeX = parseFloat(node.style.left);
      const nodeY = parseFloat(node.style.top);
      const nodeWidth = node.offsetWidth;
      const nodeHeight = node.offsetHeight;

      return (
        x < nodeX + nodeWidth &&
        x + currentWidth > nodeX &&
        y < nodeY + nodeHeight &&
        y + currentHeight > nodeY
      );
    });

    if (isOverlapping) {
      return; // Prevent placement if overlapping
    }

    // If the node is already placed, just move it
    if (nodeData.isPlaced && nodeData.elementId) {
      if (existingEl) {
        existingEl.style.left = `${x}px`;
        existingEl.style.top = `${y}px`;
        // Trigger re-render so SVG connection lines update
        setRenderTick(prev => prev + 1);
        return;
      }
    }

    // Create a draggable node element
    const nodeEl = document.createElement('div');
    const uniqueId = 'placed-node-' + Math.random().toString(36).substr(2, 9);
    nodeEl.id = uniqueId;
    nodeEl.className = 'canvas-node';
    nodeEl.style.left = `${x}px`;
    nodeEl.style.top = `${y}px`;
    nodeEl.draggable = true; // Make the new element draggable
    nodeEl.innerHTML = `<button type="button" id="config_${uniqueId}" class="config-node-btn">⚙</button><button type="button" id="delete_${uniqueId}" class="delete-node-btn">x</button><button type="button" id= "connection_${uniqueId}"
    class="connection-btn">+</button><button type="button" id="test_${uniqueId}" class="test-node-btn">▶</button><div class="dot" style="background-color:#1E5E74"></div><span>${nodeData.name}</span>`;


    // Attach drag start event to the placed node
    nodeEl.ondragstart = (dragEvent) => {
      const elRect = nodeEl.getBoundingClientRect();
      const ox = dragEvent.clientX - elRect.left;
      const oy = dragEvent.clientY - elRect.top;

      dragEvent.dataTransfer.setData("application/reactflow", JSON.stringify({
        ...nodeData,
        isPlaced: true,
        elementId: uniqueId,
        offsetX: ox,
        offsetY: oy
      }));
      dragEvent.dataTransfer.effectAllowed = "move";
    };

    // Append the node to the canvas container (parent of canvas)
    canvas.parentElement.appendChild(nodeEl);
    const connection = document.getElementById(`connection_${uniqueId}`);
    connection.addEventListener("click", () => {
      handleConnection(uniqueId);
    });
    const configBtn = document.getElementById(`config_${uniqueId}`);
    if (configBtn) {
      configBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        handleConfigNode(uniqueId);
      });
    }
    const deleteBtn = document.getElementById(`delete_${uniqueId}`);
    if (deleteBtn) {
      deleteBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        nodeEl.remove();
        setConnections(prev => prev.filter(c => c.from !== uniqueId && c.to !== uniqueId));
      });
    }
    const testBtn = document.getElementById(`test_${uniqueId}`);
    if (testBtn) {
      testBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const isTesting = nodeEl.dataset.isTesting === "true";
        if (isTesting) {
          resetNodeUnderTest(nodeEl.id);
          nodeEl.dataset.isTesting = "false";
          nodeEl.style.backgroundColor = "var(--glass-bg)";
          testBtn.style.backgroundColor = "#22c55e";
          testBtn.innerHTML = "▶";
          testBtn.style.paddingLeft = "1px";
        } else {
          setNodeUnderTest(nodeEl.id);
          nodeEl.dataset.isTesting = "true";
          nodeEl.style.backgroundColor = "rgba(34, 197, 94, 0.2)";
          testBtn.style.backgroundColor = "#ef4444";
          testBtn.innerHTML = "■";
          testBtn.style.paddingLeft = "0";
        }
      });
    }
    // Optionally store placed nodes
  };


  const handleDragOver = (e) => {
    e.preventDefault();
  };


  const handleConnection = (nodeId) => {
    const selectedNode = document.getElementById(nodeId);
    if (!selectedNode) {
      return;
    }
    rootNodeId.current = nodeId;
    const nodeName = selectedNode.querySelector("span").textContent.split("-")[0];
    const canvas = canvasRef.current;
    const parent = canvas.parentElement;
    const Allnodes = Array.from(parent.querySelectorAll('.canvas-node'));

    if (Allnodes.length <= 1) {
      setModalConnections([]);
      setModalMessage("add another node to make connections");
      setShowModal(true);
      return;
    }

    const nodeDef = ref_nodes.current[0].find(n => n.name === nodeName);
    let interfacesStr = "";

    if (nodeDef && nodeDef.Interfaces) {
      interfacesStr = nodeDef.Interfaces;
    }
    const connection_name = Allnodes.map((node) => {
      const testNodeName = node.querySelector("span").textContent;
      if (node.id != nodeId) {
        return interfacesStr.split(";")
          .filter(Boolean)
          .filter(i => i.split("-")[1] === testNodeName);
      }
      else return null;
    })

    const flatConnections = connection_name.filter(Boolean).flat();
    const matchingNodeIds2 = Allnodes.flatMap(node => {
      const nodeName = node.querySelector("span")?.textContent;

      return flatConnections
        .filter(connection => connection.split("-")[1] === nodeName)
        .map(connection => {
          const protocol = connection.split("-")[1];
          if (node.id != nodeId)
            return `${node.id}/${protocol}`;
          else
            return null;
        });
    });
    matchingNodeIds.current = matchingNodeIds2;
    if (flatConnections.length > 0) {
      setModalConnections(flatConnections);
      setModalMessage("Compatible connections:");
    } else {
      setModalConnections([]);
      setModalMessage("No compatible connections found for this node.");
    }
    setShowModal(true);
  }

  const createConnection = (targetNodeId, rootId, interface_name) => {
    console.log(interface_name);
    console.log(targetNodeId);
    console.log(rootId);
    // Prevent duplicate connections
    const exists = connections.some(
      c => (c.from === rootId && c.to === targetNodeId) ||
        (c.from === targetNodeId && c.to === rootId)
    );
    if (exists) {
      setConnections(prev =>
        prev.filter(
          conn =>
            !(
              conn.from === rootId &&
              conn.to === targetNodeId &&
              conn.interface_name === interface_name
            )
        )
      );
    } else if (!exists) {
      setConnections(prev => [...prev, { from: rootId, to: targetNodeId, interface_name }]);
      console.log(connections);
    }
    setShowModal(false);
  };

  // Helper to get the center of the connection-btn on a node (top-center of the node)
  const getNodeCenter = useCallback((nodeId) => {
    const el = document.getElementById(nodeId);
    if (!el) return null;
    const left = parseFloat(el.style.left) || 0;
    const top = parseFloat(el.style.top) || 0;
    const width = el.offsetWidth;
    // The connection-btn is 18px tall, positioned at top: -9px, centered horizontally.
    // Its center is at: x = node left + node width / 2, y = node top (top edge of the node)
    return {
      x: left + width / 2,
      y: top,
    };
  }, []);

  // Clear the canvas using clearRect
  const clearCanvas = () => {
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const parent = canvas.parentElement;
      if (parent) {
        const nodes = parent.querySelectorAll('.canvas-node');
        nodes.forEach(node => node.remove());
        setConnections([]);
      }
      ctx.strokeStyle = "rgba(255,255,255,0.1)";
      for (let x = 0; x <= canvas.width; x += 40) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
      }
      for (let y = 0; y <= canvas.height; y += 40) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
      }
    }
  }
  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("email");
    localStorage.removeItem("role");
    navigate("/");
  };

  return (
    <div className="workspace-wrapper">
      {/* Navbar */}
      <nav className="glass-nav">
        <div className="nav-logo">LabX</div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={() => navigate("/home")} className="logout-btn">
            <span>Return to Home</span>
          </button>
          <button onClick={handleLogout} className="logout-btn">
            <span>Log Out</span>
          </button>
        </div>
      </nav>

      <main className="workspace-main">
        {/* Canvas area */}
        <div className="canvas-area" onDrop={handleDrop} onDragOver={handleDragOver}>
          <button className="clear-btn" onClick={clearCanvas}>Clear Canvas</button>
          <canvas ref={canvasRef} width={1000} height={760} className="workspace-canvas" />
          {/* SVG overlay for connection lines */}
          <svg className="connections-svg" width={1000} height={760}>
            <defs>
              <linearGradient id="conn-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.9" />
                <stop offset="50%" stopColor="#a78bfa" stopOpacity="1" />
                <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.9" />
              </linearGradient>
            </defs>
            {connections.map((conn, idx) => {
              const fromPos = getNodeCenter(conn.from);
              const toPos = getNodeCenter(conn.to);
              if (!fromPos || !toPos) return null;

              const midX = (fromPos.x + toPos.x) / 2;
              const midY = (fromPos.y + toPos.y) / 2;

              return (
                <g key={idx}>
                  {/* Glow effect */}
                  <line
                    x1={fromPos.x} y1={fromPos.y}
                    x2={toPos.x} y2={toPos.y}
                    className="connection-line-glow"
                  />
                  {/* Main line */}
                  <line
                    x1={fromPos.x} y1={fromPos.y}
                    x2={toPos.x} y2={toPos.y}
                    className="connection-line"
                  />
                  {/* Start dot */}
                  <circle cx={fromPos.x} cy={fromPos.y} r={5} className="connection-dot" />
                  {/* End dot */}
                  <circle cx={toPos.x} cy={toPos.y} r={5} className="connection-dot" />
                  {/* Interface Name */}
                  {conn.interface_name && (
                    <foreignObject x={midX - 60} y={midY - 15} width={120} height={30} style={{ overflow: 'visible', pointerEvents: 'none' }}>
                      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', width: '100%', height: '100%' }}>
                        <button id={`${conn.from}+${conn.to}`} className="connection-label-btn" style={{ pointerEvents: 'auto' }} onClick={() => handleConnectionMessages(conn.from, conn.to)}>
                          {conn.interface_name}
                        </button>
                      </div>
                    </foreignObject>
                  )}
                </g>
              );
            })}
          </svg>
        </div>
        {/* Right Panel */}
        <div className="right-panel">
          <div className="save-card">
            <button className="save-workspace-btn" onClick={saveWorkspace}>
              Save Workspace
            </button>
            {isSaved && (
              <span className="save-label">
                Workspace saved successfully!
              </span>
            )}
          </div>
          {/* Nodes panel */}
          <div className="node-palette">
            {nodes.map((node, index) => (
              <div
                key={index}
                className="draggable-node"
                draggable
                onDragStart={(e) => handleDragStart(e, node)}
              >
                <div className="node-color" />
                <span>{node.name}</span>
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* Connection Modal */}
      {showModal && (
        <div className="modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.6)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999
        }} onClick={() => setShowModal(false)}>
          <div className="modal-content glass-panel" onClick={(e) => e.stopPropagation()} style={{
            background: 'var(--glass-bg)', padding: '24px', borderRadius: '16px',
            border: '1px solid var(--glass-border)', color: 'var(--text-main)',
            textAlign: 'center', minWidth: '320px', boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)'
          }}>
            <h3 style={{ marginBottom: '16px', fontSize: '1.2rem', color: 'var(--primary)' }}>Connection Info</h3>
            <p style={{ marginBottom: '24px', fontSize: '1rem', lineHeight: '1.5' }}>{modalMessage}</p>
            {modalConnections && modalConnections.length > 0 && (
              <div name="connections" style={{ display: 'flex', gap: '10px', justifyContent: 'center', flexWrap: 'wrap', marginBottom: '24px' }}>
                {modalConnections.map((conn, idx) => {
                  const match = matchingNodeIds.current.find(id => {
                    if (id != null) {
                      const protocol = id.split("/")[1].trim().toLowerCase();
                      const connValue = conn.split("-")[1].trim().toLowerCase();

                      if (id.split("/")[0] != rootNodeId.current) {
                        return protocol === connValue;
                      }
                      return null;
                    }
                    else return null;
                  });
                  const targetNodeId = match ? match.split("/")[0] : null;
                  const root_protocol = document.getElementById(rootNodeId.current).querySelector("span").textContent.split("-")[0].trim();
                  const target_protocol = document.getElementById(targetNodeId).querySelector("span").textContent.split("-")[0].trim();
                  const ref_nodes2 = ref_nodes.current[0].find(n => n.name?.trim() === root_protocol);
                  const interface_name = ref_nodes2.Interfaces
                    .split(";")
                    .find(i => i.split("-")[1]?.trim() === target_protocol?.trim())
                    .split("-")[0].trim();
                  return (
                    <button key={idx} onClick={() => {
                      if (targetNodeId) {
                        createConnection(targetNodeId, rootNodeId.current, interface_name);
                      }
                    }} className="save-workspace-btn" style={{ padding: '8px 16px', fontSize: '0.9rem' }}>
                      {conn}
                    </button>
                  );
                })}
              </div>
            )}
            <button className="save-workspace-btn" onClick={() => setShowModal(false)}>Close</button>
          </div>
        </div>
      )}

      {/* Config Modal */}
      {showConfigModal && (
        <div className="modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.6)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999
        }} onClick={() => setShowConfigModal(false)}>
          <div className="modal-content glass-panel" onClick={(e) => e.stopPropagation()} style={{
            background: 'var(--glass-bg)', padding: '24px', borderRadius: '16px',
            border: '1px solid var(--glass-border)', color: 'var(--text-main)',
            textAlign: 'center', minWidth: '320px', boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
            display: 'flex', flexDirection: 'column', gap: '15px'
          }}>
            <h3 style={{ fontSize: '1.2rem', color: 'var(--primary)', marginBottom: '10px' }}>Configure Node</h3>

            <div style={{ display: 'flex', flexDirection: 'column', textAlign: 'left', gap: '5px' }}>
              <label style={{ fontSize: '0.9rem', color: '#ccc' }}>IP Address</label>
              <input
                type="text"
                value={ip}
                onChange={(e) => setIp(e.target.value)}
                style={{ padding: '10px', borderRadius: '8px', border: '1px solid var(--glass-border)', background: 'rgba(255,255,255,0.05)', color: '#fff', outline: 'none' }}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', textAlign: 'left', gap: '5px' }}>
              <label style={{ fontSize: '0.9rem', color: '#ccc' }}>URL</label>
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                style={{ padding: '10px', borderRadius: '8px', border: '1px solid var(--glass-border)', background: 'rgba(255,255,255,0.05)', color: '#fff', outline: 'none' }}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', textAlign: 'left', gap: '5px' }}>
              <label style={{ fontSize: '0.9rem', color: '#ccc' }}>Mode</label>
              <input
                type="text"
                value={mode}
                onChange={(e) => setMode(e.target.value)}
                style={{ padding: '10px', borderRadius: '8px', border: '1px solid var(--glass-border)', background: 'rgba(255,255,255,0.05)', color: '#fff', outline: 'none' }}
              />
            </div>

            <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', marginTop: '15px' }}>
              <button className="save-workspace-btn" onClick={saveNodeConfig}>Save</button>
              <button className="save-workspace-btn" style={{ background: '#ef4444', boxShadow: '0 4px 10px rgba(239, 68, 68, 0.3)' }} onClick={() => setShowConfigModal(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* Connection Messages Modal */}
      {showMessagesModal && (
        <div className="modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.6)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999
        }} onClick={() => setShowMessagesModal(false)}>
          <div className="modal-content glass-panel" onClick={(e) => e.stopPropagation()} style={{
            background: 'var(--glass-bg)', padding: '24px', borderRadius: '16px',
            border: '1px solid var(--glass-border)', color: 'var(--text-main)',
            textAlign: 'center', minWidth: '320px', boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
            display: 'flex', flexDirection: 'column', gap: '15px'
          }}>
            <h3 style={{ fontSize: '1.2rem', color: 'var(--primary)', marginBottom: '10px' }}>Connection Message</h3>

            <div style={{ display: 'flex', flexDirection: 'column', textAlign: 'left', gap: '5px' }}>
              <label style={{ fontSize: '0.9rem', color: '#ccc' }}>Label</label>
              <input type="text" value={messageLabel} onChange={(e) => setMessageLabel(e.target.value)} style={{ padding: '10px', borderRadius: '8px', border: '1px solid var(--glass-border)', background: 'rgba(255,255,255,0.05)', color: '#fff', outline: 'none' }} />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', textAlign: 'left', gap: '5px' }}>
              <label style={{ fontSize: '0.9rem', color: '#ccc' }}>Description</label>
              <input type="text" value={messageDescription} onChange={(e) => setMessageDescription(e.target.value)} style={{ padding: '10px', borderRadius: '8px', border: '1px solid var(--glass-border)', background: 'rgba(255,255,255,0.05)', color: '#fff', outline: 'none' }} />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', textAlign: 'left', gap: '5px' }}>
              <label style={{ fontSize: '0.9rem', color: '#ccc' }}>Content</label>
              <textarea value={messageContent} onChange={(e) => setMessageContent(e.target.value)} style={{ padding: '10px', borderRadius: '8px', border: '1px solid var(--glass-border)', background: 'rgba(255,255,255,0.05)', color: '#fff', outline: 'none', minHeight: '60px', resize: 'vertical' }} />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', textAlign: 'left', gap: '5px' }}>
              <label style={{ fontSize: '0.9rem', color: '#ccc' }}>Type</label>
              <input type="text" value={messageType} onChange={(e) => setMessageType(e.target.value)} style={{ padding: '10px', borderRadius: '8px', border: '1px solid var(--glass-border)', background: 'rgba(255,255,255,0.05)', color: '#fff', outline: 'none' }} />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', textAlign: 'left', gap: '5px' }}>
              <label style={{ fontSize: '0.9rem', color: '#ccc' }}>Protocol</label>
              <input type="text" value={messageProtocol} onChange={(e) => setMessageProtocol(e.target.value)} style={{ padding: '10px', borderRadius: '8px', border: '1px solid var(--glass-border)', background: 'rgba(255,255,255,0.05)', color: '#fff', outline: 'none' }} />
            </div>

            <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', marginTop: '15px' }}>
              <button className="save-workspace-btn" onClick={saveConnectionMessage}>Save</button>
              <button className="save-workspace-btn" style={{ background: '#ef4444', boxShadow: '0 4px 10px rgba(239, 68, 68, 0.3)' }} onClick={() => setShowMessagesModal(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Workspace;
