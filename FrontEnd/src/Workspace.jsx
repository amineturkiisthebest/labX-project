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
  const [modalMessage, setModalMessage] = useState("");
  const [modalConnections, setModalConnections] = useState([]);
  const matchingNodeIds = useRef([]);
  const rootNodeId = useRef("");
  const [connections, setConnections] = useState([]);
  const [, setRenderTick] = useState(0);
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

  const loadWorkspace = async () => {
    const response = await fetch(`http://localhost:8000/load_workspace/${workspace_id.id}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });
    const data = await response.json();
    console.log(data.nodes);
    setSavedNodes(data.nodes);
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
      nodeEl.innerHTML = `<button type="button" id="connection_${uniqueId}"
      class="connection-btn">+</button><div class="dot" style="background-color:#1E5E74"></div><span>${node.name}</span>`;

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
    });
  }, [saved_nodes]);

  const saveWorkspace = async () => {
    const canvas = canvasRef.current;
    const placedNodes = canvas.parentElement.querySelectorAll('.canvas-node');
    const w_id = workspace_id.id;
    const nodesData = Array.from(placedNodes).map(node => ({
      id: node.id,
      name: node.querySelector('span').textContent,
      x: parseFloat(node.style.left),
      y: parseFloat(node.style.top)
    }));
    const response = await fetch(`http://localhost:8000/save_workspace/${w_id}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ nodesData: nodesData }),
    });
    const data = await response.json();
    console.log(data.count);
    setIsSaved(true);
    setTimeout(() => {
      setIsSaved(false);
    }, 3000);
  }


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
      tempEl.innerHTML = `<button type="button" 
       class="connection-btn">+</button><div class="dot" style="background-color:#1E5E74"></div><span>${nodeData.name}</span>`;
      canvas.parentElement.appendChild(tempEl);
      currentWidth = tempEl.offsetWidth;
      currentHeight = tempEl.offsetHeight;
      canvas.parentElement.removeChild(tempEl);
    }

    const placedNodes = Array.from(canvas.parentElement.querySelectorAll('.canvas-node'));
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
    nodeEl.innerHTML = `<button type="button" id= "connection_${uniqueId}"
    class="connection-btn">+</button><div class="dot" style="background-color:#1E5E74"></div><span>${nodeData.name}</span>`;


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
    const nodeName = selectedNode.querySelector("span").textContent;
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
      if (testNodeName === nodeName) return null;
      return interfacesStr.split(";")
        .filter(Boolean)
        .filter(i => i.split("-")[1] === testNodeName);
    })

    const flatConnections = connection_name.filter(Boolean).flat();
    const matchingNodeIds2 = Allnodes.flatMap(node => {
      const nodeName = node.querySelector("span")?.textContent;

      return flatConnections
        .filter(connection => connection.split("-")[1] === nodeName)
        .map(connection => {
          const protocol = connection.split("-")[1];
          return `${node.id}/${protocol}`;
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

  const createConnection = (targetNodeId, rootId) => {
    console.log(targetNodeId);
    console.log(rootId);
    // Prevent duplicate connections
    const exists = connections.some(
      c => (c.from === rootId && c.to === targetNodeId) ||
        (c.from === targetNodeId && c.to === rootId)
    );
    if (!exists) {
      setConnections(prev => [...prev, { from: rootId, to: targetNodeId }]);
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
                    const protocol = id.split("/")[1].trim().toLowerCase();
                    const connValue = conn.split("-")[1].trim().toLowerCase();
                    console.log("connValue", connValue);
                    console.log("protocol", protocol);
                    return protocol === connValue;
                  });

                  const targetNodeId = match ? match.split("/")[0] : null;
                  return (
                    <button key={idx} onClick={() => {
                      if (targetNodeId) {
                        createConnection(targetNodeId, rootNodeId.current);
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
    </div>
  );
}

export default Workspace;
